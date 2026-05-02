"""
Price screening v2 — uses yfinance EquityQuery screener to get
Canadian daily movers directly, instead of downloading all tickers.

This is 100x faster: one API call vs 2867 individual downloads.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

from yfinance.screener.screener import screen
from yfinance import EquityQuery
import yfinance as yf

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"


def _load_universe_lookup():
    """Load enriched universe as a ticker->info lookup dict."""
    path = DATA_DIR / "universe_full.json"
    if path.exists():
        try:
            with open(path) as f:
                universe = json.load(f)
            return {t['ticker']: t for t in universe}
        except Exception:
            pass
    return {}


def _build_query(min_pct=3.0):
    """Build a yfinance EquityQuery for Canadian gainers."""
    return EquityQuery('and', [
        EquityQuery('gt', ['percentchange', min_pct]),
        EquityQuery('or', [
            EquityQuery('eq', ['exchange', 'TOR']),   # TSX
            EquityQuery('eq', ['exchange', 'VAN']),   # TSXV
            EquityQuery('eq', ['exchange', 'CNQ']),   # CSE
            EquityQuery('eq', ['exchange', 'NEO']),   # NEO
        ])
    ])


EXCHANGE_MAP = {
    'TOR': 'TSX',
    'VAN': 'TSXV',
    'CNQ': 'CSE',
    'NEO': 'NEO',
}

EXCHANGE_SUFFIX = {
    'TOR': '.TO',
    'VAN': '.V',
    'CNQ': '.CN',
    'NEO': '.NE',
}


def get_daily_movers(min_pct=3.0, max_results=250):
    """
    Get today's Canadian stock movers using Yahoo Finance screener.

    Returns list of dicts with standardized fields, sorted by % change desc.
    Single API call — takes ~1-2 seconds.
    """
    print(f"  Querying Yahoo Finance for Canadian gainers > {min_pct}%...")
    q = _build_query(min_pct)
    result = screen(q, sortField='percentchange', sortAsc=False, size=max_results)
    quotes = result.get('quotes', [])
    print(f"  Found {len(quotes)} gainers")

    # Load enriched universe for sector/industry lookup
    universe_lookup = _load_universe_lookup()

    movers = []
    for q in quotes:
        symbol = q.get('symbol', '')
        exchange_raw = q.get('exchange', '')
        exchange = EXCHANGE_MAP.get(exchange_raw, exchange_raw)
        price = q.get('regularMarketPrice', 0)
        pct_1d = q.get('regularMarketChangePercent', 0)
        volume = q.get('regularMarketVolume', 0)
        avg_vol = q.get('averageDailyVolume3Month', 0)
        market_cap = q.get('marketCap', 0)
        high_52w = q.get('fiftyTwoWeekHigh', 0)
        name = q.get('shortName', '') or q.get('longName', '') or symbol

        # Volume ratio
        vol_ratio = volume / avg_vol if avg_vol > 0 else 1.0

        # 52-week high proximity
        high_52w_prox = (price / high_52w * 100) if high_52w > 0 else 0

        # Look up sector/industry from enriched universe
        uni = universe_lookup.get(symbol, {})
        sector = uni.get('sector', 'Unknown')
        industry = uni.get('industry', '')
        if sector in ('Unknown', 'Other', '') or not sector:
            sector = 'Unknown'
            industry = ''

        movers.append({
            'ticker': symbol,
            'yf_ticker': symbol,
            'name': name,
            'exchange': exchange,
            'sector': sector,
            'industry': industry,
            'price': round(price, 4),
            'pct_move_1d': round(pct_1d, 2),
            'pct_move_5d': 0,  # filled by enrich_history
            'pct_move_10d': 0,
            'pct_move_30d': 0,
            'vol_ratio': round(vol_ratio, 2),
            'volume': volume,
            'avg_volume': avg_vol,
            'market_cap': int(market_cap),
            'high_52w': round(high_52w, 4),
            'high_52w_proximity': round(high_52w_prox, 2),
            'shares_outstanding': q.get('sharesOutstanding', 0),
            'is_signal': True,
            'scan_time': datetime.now().isoformat(),
            'primary_move': round(pct_1d, 2),
        })

    return movers


def enrich_sectors(movers):
    """
    Fill in sector/industry for movers that have 'Unknown' sector.
    Uses yf.Ticker().info calls — only for unknowns.
    Also saves newly discovered sectors back to universe_full.json.
    """
    unknowns = [m for m in movers if m.get('sector') in ('Unknown', '', None)]
    if not unknowns:
        print(f"  All {len(movers)} movers have sector data")
        return

    print(f"  Enriching sectors for {len(unknowns)} stocks...")
    universe_lookup = _load_universe_lookup()
    updated_universe = False

    for i, m in enumerate(unknowns):
        try:
            info = yf.Ticker(m['yf_ticker']).info or {}
            sector = info.get('sector', '')
            industry = info.get('industry', '')
            if sector:
                m['sector'] = sector
                m['industry'] = industry
                # Save to universe for future lookups
                if m['ticker'] in universe_lookup:
                    universe_lookup[m['ticker']]['sector'] = sector
                    universe_lookup[m['ticker']]['industry'] = industry
                    if not universe_lookup[m['ticker']].get('market_cap_cad'):
                        universe_lookup[m['ticker']]['market_cap_cad'] = info.get('marketCap', 0)
                    updated_universe = True
            time.sleep(0.2)
        except Exception:
            pass

        if (i + 1) % 50 == 0:
            print(f"    {i+1}/{len(unknowns)} done")

    still_unknown = sum(1 for m in movers if m.get('sector') in ('Unknown', '', None))
    print(f"  Sector enrichment done. {len(movers) - still_unknown}/{len(movers)} have sectors")

    # Save updated universe
    if updated_universe:
        try:
            path = DATA_DIR / "universe_full.json"
            universe_list = list(universe_lookup.values())
            with open(path, 'w') as f:
                json.dump(universe_list, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save universe updates: {e}")


def enrich_history(movers, batch_size=50):
    """
    Enrich movers with multi-day price history (5d, 10d, 30d moves + sparkline).
    Downloads history in batches for speed.
    """
    if not movers:
        return

    tickers = [m['yf_ticker'] for m in movers]
    ticker_map = {m['yf_ticker']: m for m in movers}

    print(f"  Enriching {len(tickers)} movers with price history...")

    for batch_start in range(0, len(tickers), batch_size):
        batch = tickers[batch_start:batch_start + batch_size]
        try:
            data = yf.download(batch, period='3mo', progress=False, auto_adjust=True, threads=True)
            if data.empty:
                continue

            for ticker in batch:
                try:
                    if len(batch) == 1:
                        closes = data['Close'].dropna()
                        volumes = data['Volume'].dropna()
                    else:
                        if ticker not in data.columns.get_level_values(0):
                            continue
                        closes = data[ticker]['Close'].dropna()
                        volumes = data[ticker]['Volume'].dropna()

                    if len(closes) < 2:
                        continue

                    m = ticker_map[ticker]
                    current = float(closes.iloc[-1])

                    # Multi-day moves
                    if len(closes) >= 6:
                        m['pct_move_5d'] = round(((current / float(closes.iloc[-6])) - 1) * 100, 2)
                    if len(closes) >= 11:
                        m['pct_move_10d'] = round(((current / float(closes.iloc[-11])) - 1) * 100, 2)
                    if len(closes) >= 31:
                        m['pct_move_30d'] = round(((current / float(closes.iloc[-31])) - 1) * 100, 2)

                    # Price history for sparkline (last 30 closes)
                    m['price_history'] = [float(x) for x in closes.iloc[-30:].tolist()]

                    # Volume history for detail panel
                    vol_tail = volumes.iloc[-30:]
                    vol_avg = float(volumes.iloc[-30:].mean()) if len(volumes) >= 30 else float(volumes.mean())
                    m['volume_history'] = [
                        {'vol': float(v), 'surge': float(v) / vol_avg >= 3 if vol_avg > 0 else False}
                        for v in vol_tail
                    ]

                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"Batch history download failed: {e}")

        time.sleep(0.5)


def get_weekly_movers(min_pct=3.0, max_results=250):
    """
    Get weekly movers by querying daily gainers and enriching with 5d history.
    Also queries for stocks with >10% weekly move.
    """
    # Get daily movers first
    daily = get_daily_movers(min_pct=min_pct, max_results=max_results)

    # Enrich with history
    enrich_history(daily)

    return daily


# Re-export scoring functions from price_screen.py
from scanner.price_screen import _momentum_score, _conviction_score, _macro_trend_tags
