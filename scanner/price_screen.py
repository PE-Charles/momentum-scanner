"""
Main screening logic for Canadian small-cap momentum scanner.
Pulls price/volume data via yfinance batch download for speed,
then computes momentum metrics for all movers.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

from scanner.universe import UNIVERSE

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"

# CAD/USD conversion factor
USD_TO_CAD = 1.35

# Signal thresholds
SIGNAL_PCT_10D = 20.0
SIGNAL_PCT_5D = 10.0
SIGNAL_PCT_1D = 5.0
SIGNAL_MCAP_MIN = 5_000_000       # $5M CAD
SIGNAL_MCAP_MAX = 1_000_000_000   # $1B CAD
SIGNAL_PRICE_MIN = 0.01
SIGNAL_PRICE_MAX = 50.0

# How many tickers to process per yf.download batch
BATCH_SIZE = 50


def _load_full_universe():
    """Load the full TMX universe from data/universe_full.json, fall back to UNIVERSE."""
    full_path = DATA_DIR / "universe_full.json"
    if full_path.exists():
        try:
            with open(full_path) as f:
                tickers = json.load(f)
            logger.info(f"Loaded full universe: {len(tickers)} tickers")
            return tickers
        except Exception as e:
            logger.warning(f"Failed to load full universe: {e}")
    return UNIVERSE


def _safe_pct(current, previous):
    if previous is None or previous == 0:
        return 0.0
    return ((current - previous) / abs(previous)) * 100.0


def _compute_metrics_from_series(closes, volumes):
    """Compute metrics from pandas Series of closes and volumes."""
    if closes is None or len(closes) < 2:
        return None

    current_price = float(closes.iloc[-1])
    if current_price <= 0 or pd.isna(current_price):
        return None

    pct_1d = _safe_pct(current_price, float(closes.iloc[-2])) if len(closes) >= 2 else 0.0
    pct_5d = _safe_pct(current_price, float(closes.iloc[-6])) if len(closes) >= 6 else 0.0
    pct_10d = _safe_pct(current_price, float(closes.iloc[-11])) if len(closes) >= 11 else 0.0
    pct_30d = _safe_pct(current_price, float(closes.iloc[-31])) if len(closes) >= 31 else 0.0

    vol_5d = float(volumes.iloc[-5:].mean()) if len(volumes) >= 5 else float(volumes.mean())
    vol_30d = float(volumes.iloc[-30:].mean()) if len(volumes) >= 30 else float(volumes.mean())
    vol_ratio = vol_5d / vol_30d if vol_30d > 0 else 1.0

    hist_max = float(closes.max())
    high_52w_proximity = (current_price / hist_max) * 100.0 if hist_max > 0 else 0.0

    # Last 30 close prices for sparkline
    price_history = [float(x) for x in closes.iloc[-30:].tolist()]

    # Last 30 volumes with surge flag (surge = vol_ratio >= 3 for last 5 bars)
    vol_tail = volumes.iloc[-30:]
    vol_avg_30 = float(volumes.iloc[-30:].mean()) if len(volumes) >= 30 else float(volumes.mean())
    volume_history = []
    for i, v in enumerate(vol_tail):
        is_last_5 = i >= len(vol_tail) - 5
        bar_ratio = float(v) / vol_avg_30 if vol_avg_30 > 0 else 0
        volume_history.append({
            "vol": float(v),
            "surge": is_last_5 and bar_ratio >= 3,
        })

    return {
        "price": round(current_price, 4),
        "pct_move_1d": round(pct_1d, 2),
        "pct_move_5d": round(pct_5d, 2),
        "pct_move_10d": round(pct_10d, 2),
        "pct_move_30d": round(pct_30d, 2),
        "vol_ratio": round(vol_ratio, 2),
        "high_52w": round(hist_max, 4),
        "high_52w_proximity": round(high_52w_proximity, 2),
        "market_cap": 0,  # populated from universe data in screen_universe
        "price_history": price_history,
        "volume_history": volume_history,
    }


def _momentum_score(metrics):
    """Composite momentum score (0-99)."""
    price_score = min(abs(metrics["pct_move_10d"]), 100.0) / 100.0
    if metrics["pct_move_10d"] < 0:
        price_score = 0.0

    vol_score = min(max(metrics["vol_ratio"] - 1.0, 0.0), 19.0) / 19.0

    tf_positive = sum(1 for k in ["pct_move_1d", "pct_move_5d", "pct_move_10d"]
                      if metrics[k] > 0)
    consistency_score = tf_positive / 3.0

    high_prox_score = min(metrics.get("high_52w_proximity", 0), 100.0) / 100.0

    raw = (
        0.40 * price_score +
        0.30 * vol_score +
        0.20 * consistency_score +
        0.10 * high_prox_score
    )
    return min(int(raw * 99), 99)


def _conviction_score(stock):
    """Compute conviction score (0-100) with sub-scores for a fully-enriched stock dict."""

    EARNINGS_KEYWORDS = [
        "earnings", "revenue", "ebitda", "profit", "quarterly",
        "record", "beat", "exceeded", "growth",
    ]
    BEAT_KEYWORDS = ["beat", "exceeded", "record", "growth"]

    # --- Signal Strength (25%) ---
    pct_10d = stock.get("pct_move_10d", 0) or 0  # raw %, e.g. 30.36
    vol_ratio = stock.get("vol_ratio", 1) or 1

    price_s = min(pct_10d, 100.0) / 100.0
    if pct_10d < 0:
        price_s = 0.0
    if pct_10d >= 30:
        price_s = max(price_s, 0.6)

    vol_s = min(vol_ratio, 10.0) / 10.0
    if vol_ratio >= 5:
        vol_s = max(vol_s, 0.7)

    # Multi-session: count surge days in volume_history
    volume_history = stock.get("volume_history", [])
    surge_days = sum(1 for v in volume_history if isinstance(v, dict) and v.get("surge"))
    multi_session_bonus = min(surge_days / 5.0, 1.0) * 0.3

    signal_raw = 0.45 * price_s + 0.45 * vol_s + 0.10
    signal_strength = min(signal_raw * (1 + multi_session_bonus), 1.0)

    # --- Catalyst Quality (35%) ---
    catalyst_cls = (stock.get("catalyst_classification") or "").upper()
    if catalyst_cls == "GREEN":
        catalyst_base = 1.0
    elif catalyst_cls == "YELLOW":
        catalyst_base = 0.5
    else:
        catalyst_base = 0.0

    # Check for commitment flags in catalyst classifications
    catalysts = stock.get("catalysts", [])
    has_third_party = False
    has_capital = False
    for c in catalysts:
        cls_data = c.get("classification", {})
        if isinstance(cls_data, dict):
            if cls_data.get("third_party_committed"):
                has_third_party = True
            if cls_data.get("capital_committed"):
                has_capital = True

    catalyst_quality = catalyst_base
    if has_third_party:
        catalyst_quality += 0.15
    if has_capital:
        catalyst_quality += 0.10
    catalyst_quality = min(catalyst_quality, 1.0)

    # --- Setup Quality (20%) ---
    mcap = stock.get("market_cap", 0) or 0
    price = stock.get("price", 0) or 0
    high_prox = stock.get("high_52w_proximity", 0) or 0

    # Market cap sweet spot
    if 10_000_000 <= mcap <= 500_000_000:
        mcap_s = 1.0
    elif 5_000_000 <= mcap < 10_000_000:
        mcap_s = 0.6
    elif 500_000_000 < mcap <= 1_000_000_000:
        mcap_s = 0.5
    elif mcap > 1_000_000_000:
        mcap_s = 0.2
    elif mcap == 0:
        mcap_s = 0.3
    else:
        mcap_s = 0.3

    # Price range
    if 0.05 <= price <= 15:
        price_range_s = 1.0
    elif 0.01 <= price < 0.05:
        price_range_s = 0.4
    elif 15 < price <= 50:
        price_range_s = 0.6
    else:
        price_range_s = 0.2

    # 52-week high proximity
    if high_prox >= 90:
        high_prox_s = 1.0
    else:
        high_prox_s = high_prox / 100.0

    setup_quality = 0.40 * mcap_s + 0.25 * price_range_s + 0.35 * high_prox_s

    # --- Pattern Match (20%) ---
    # Gather all news titles
    news = stock.get("news", [])
    all_titles = " ".join(
        (n.get("title", "") for n in news) if isinstance(news, list) else []
    ).lower()

    has_earnings_kw = any(kw in all_titles for kw in EARNINGS_KEYWORDS)
    has_beat_kw = any(kw in all_titles for kw in BEAT_KEYWORDS)

    if has_earnings_kw:
        # Type B
        pattern_match = 0.9 if has_beat_kw else 0.5
    elif mcap > 0 and mcap < 100_000_000:
        # Type A
        if catalyst_cls == "GREEN":
            pattern_match = 1.0
        elif catalyst_cls == "YELLOW":
            pattern_match = 0.5
        else:
            pattern_match = 0.15
    else:
        pattern_match = 0.35

    if surge_days >= 3:
        pattern_match = min(pattern_match + 0.15, 1.0)

    # Macro trend bonus
    if stock.get("macro_trends"):
        pattern_match = min(pattern_match + 0.10, 1.0)

    # --- Composite ---
    composite = (
        0.25 * signal_strength +
        0.35 * catalyst_quality +
        0.20 * setup_quality +
        0.20 * pattern_match
    )
    conviction_score = min(int(composite * 100), 100)

    # Grade
    if conviction_score >= 90:
        grade = "A+"
    elif conviction_score >= 75:
        grade = "A"
    elif conviction_score >= 50:
        grade = "B"
    elif conviction_score >= 25:
        grade = "C"
    else:
        grade = "D"

    return {
        "conviction_score": conviction_score,
        "conviction_grade": grade,
        "sub_scores": {
            "signal_strength": round(signal_strength * 100),
            "catalyst_quality": round(catalyst_quality * 100),
            "setup_quality": round(setup_quality * 100),
            "pattern_match": round(pattern_match * 100),
        },
    }


def _macro_trend_tags(stock):
    """Return a list of macro trend tags based on sector, industry, name, and news."""
    tags = []
    sector = (stock.get("sector") or "").lower()
    industry = (stock.get("industry") or "").lower()
    name = (stock.get("name") or "").lower()

    # Gather news text
    news_items = stock.get("news", [])
    news_text = ""
    if isinstance(news_items, list):
        news_text = " ".join(n.get("title", "") for n in news_items).lower()

    combined = f"{industry} {name} {news_text}"

    # AI
    ai_industry_kw = ["software", "artificial", "machine learning", "data", "cloud"]
    ai_name_kw = ["ai", "artificial intelligence", "machine learning"]
    if any(kw in industry for kw in ai_industry_kw) or any(kw in f"{name} {news_text}" for kw in ai_name_kw):
        tags.append("AI")

    # Clean Energy
    ce_kw = ["solar", "wind", "renewable", "clean", "hydrogen", "graphene", "battery", "ev"]
    if sector == "utilities" or any(kw in industry for kw in ce_kw):
        tags.append("Clean Energy")

    # Defense
    def_industry_kw = ["defense", "aerospace", "security", "military", "surveillance"]
    def_name_kw = ["defense", "security"]
    if any(kw in industry for kw in def_industry_kw) or any(kw in name for kw in def_name_kw):
        tags.append("Defense")

    # Data Centres
    dc_kw = ["data cent", "datacent", "colocation", "cloud infrastructure", "hyperscale"]
    if any(kw in combined for kw in dc_kw):
        tags.append("Data Centres")

    # Power Infrastructure
    pi_industry_kw = ["power", "transformer", "electrical", "grid", "utility"]
    if any(kw in industry for kw in pi_industry_kw) or "power" in name:
        tags.append("Power Infrastructure")

    # SaaS
    saas_industry_kw = ["software", "saas", "cloud"]
    saas_name_kw = ["software", "platform"]
    if any(kw in industry for kw in saas_industry_kw) or any(kw in name for kw in saas_name_kw):
        tags.append("SaaS")

    # Quantum
    if "quantum" in combined:
        tags.append("Quantum")

    # Fintech
    ft_industry_kw = ["fintech", "payment", "lending"]
    if any(kw in industry for kw in ft_industry_kw) or "fintech" in name:
        tags.append("Fintech")

    return tags


def _check_signal(metrics):
    """Check if a stock meets signal thresholds."""
    price_ok = (
        metrics["pct_move_10d"] >= SIGNAL_PCT_10D or
        metrics["pct_move_5d"] >= SIGNAL_PCT_5D or
        metrics["pct_move_1d"] >= SIGNAL_PCT_1D
    )
    price_range_ok = SIGNAL_PRICE_MIN <= metrics["price"] <= SIGNAL_PRICE_MAX
    return price_ok and price_range_ok


def _batch_download(yf_tickers, period="3mo"):
    """Download history for a batch of tickers using yf.download."""
    try:
        data = yf.download(
            yf_tickers,
            period=period,
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )
        return data
    except Exception as e:
        logger.error(f"Batch download error: {e}")
        return None


def screen_universe(tickers=None, period="today", use_full_universe=True):
    """
    Screen the universe for momentum signals using batch downloads.

    Args:
        tickers: optional list of ticker dicts. If None, loads full universe.
        period: "today", "week", "month" — affects primary_move field.
        use_full_universe: if True and tickers is None, load full TMX universe.

    Returns:
        List of dicts sorted by momentum score descending.
        Only includes stocks with positive moves (movers).
    """
    if tickers is None:
        if use_full_universe:
            tickers = _load_full_universe()
        else:
            tickers = UNIVERSE

    # Build lookup: yf_ticker -> stock info
    ticker_map = {}
    for stock in tickers:
        yf_t = stock.get("yf_ticker", stock["ticker"])
        ticker_map[yf_t] = stock

    yf_tickers = list(ticker_map.keys())
    total = len(yf_tickers)
    logger.info(f"Screening {total} tickers...")
    print(f"Screening {total} tickers in batches of {BATCH_SIZE}...")

    all_results = []

    # Process in batches
    for batch_start in range(0, total, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total)
        batch = yf_tickers[batch_start:batch_end]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} tickers)...", end="", flush=True)

        try:
            data = _batch_download(batch)
            if data is None or data.empty:
                print(" no data")
                continue

            processed = 0
            for yf_t in batch:
                try:
                    # Extract this ticker's data from the multi-ticker DataFrame
                    if len(batch) == 1:
                        closes = data["Close"]
                        volumes = data["Volume"]
                    else:
                        if yf_t not in data.columns.get_level_values(0):
                            continue
                        closes = data[yf_t]["Close"].dropna()
                        volumes = data[yf_t]["Volume"].dropna()

                    if closes.empty or len(closes) < 5:
                        continue

                    metrics = _compute_metrics_from_series(closes, volumes)
                    if metrics is None:
                        continue

                    # Skip stocks with no meaningful positive move
                    if metrics["pct_move_5d"] <= 0 and metrics["pct_move_10d"] <= 0 and metrics["pct_move_1d"] <= 0:
                        continue

                    is_signal = _check_signal(metrics)
                    score = _momentum_score(metrics)

                    stock_info = ticker_map[yf_t]
                    # Use market_cap_cad from enriched universe data
                    metrics["market_cap"] = stock_info.get("market_cap_cad", 0)
                    result = {
                        "ticker": stock_info["ticker"],
                        "yf_ticker": yf_t,
                        "name": stock_info["name"],
                        "exchange": stock_info["exchange"],
                        "sector": stock_info.get("sector", "Unknown"),
                        "momentum_score": score,
                        "is_signal": is_signal,
                        "scan_time": datetime.now().isoformat(),
                        **metrics,
                    }

                    result["macro_trends"] = _macro_trend_tags(result)

                    if period == "today":
                        result["primary_move"] = metrics["pct_move_1d"]
                    elif period == "week":
                        result["primary_move"] = metrics["pct_move_5d"]
                    else:
                        result["primary_move"] = metrics["pct_move_30d"]

                    all_results.append(result)
                    processed += 1

                except Exception as e:
                    continue

            print(f" {processed} movers")

        except Exception as e:
            print(f" error: {e}")
            continue

        # Brief pause between batches
        time.sleep(0.5)

    # Sort by momentum score descending
    all_results.sort(key=lambda x: x["momentum_score"], reverse=True)

    signal_count = sum(1 for r in all_results if r["is_signal"])
    print(f"\nDone. {len(all_results)} movers found, {signal_count} triggered signals.")

    return all_results
