"""
Flask API server for the Canadian small-cap momentum scanner.
Serves on port 5001 with CORS enabled for Vite dev server.
"""

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from scanner.price_screen import screen_universe, _conviction_score
from scanner.news_fetch import fetch_news_for_ticker
from scanner.catalyst_classify import classify_catalyst
from scanner.universe import UNIVERSE

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=["http://localhost:5173", "http://127.0.0.1:5173"])

DATA_DIR = Path(__file__).parent / "data"
WATCHLIST_PATH = DATA_DIR / "watchlist.json"
SIGNALS_LATEST_PATH = DATA_DIR / "signals_latest.json"
SCAN_HISTORY_PATH = DATA_DIR / "scan_history.json"


def _load_json(path, default=None):
    """Load JSON from a file, returning default if missing or corrupt."""
    if default is None:
        default = []
    if path.exists():
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return default
    return default


def _save_json(path, data):
    """Save data as JSON to a file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _normalize_signal(s):
    """Add flat fields for frontend consumption.

    The frontend expects:
      - news_headline, news_source, news_date (flat strings)
      - news_items (list of {title, summary, source, date, tags})
      - near_52w_high (bool)
      - pct_move_* as decimals (0.45 = 45%)
    """
    # Convert percentage numbers to decimals (e.g. 3.15 -> 0.0315, 45.2 -> 0.452)
    for key in ("pct_move_1d", "pct_move_5d", "pct_move_10d", "pct_move_30d", "primary_move"):
        val = s.get(key)
        if val is not None:
            s[key] = val / 100.0

    # 52-week high proximity -> bool
    s["near_52w_high"] = (s.get("high_52w_proximity") or 0) >= 85

    # Flatten news array into headline/source/date
    news = s.get("news", [])
    catalysts = s.get("catalysts", [])

    if news and len(news) > 0:
        first = news[0]
        s["news_headline"] = first.get("title", "")
        s["news_source"] = first.get("source", "")
        s["news_date"] = first.get("published", "")
    elif catalysts and len(catalysts) > 0:
        first = catalysts[0]
        s["news_headline"] = first.get("title", "")
        s["news_source"] = ""
        s["news_date"] = ""
    else:
        s["news_headline"] = ""
        s["news_source"] = ""
        s["news_date"] = ""

    # Build news_items for detail panel
    items = []
    for n in news:
        item = {
            "title": n.get("title", ""),
            "summary": n.get("summary", ""),
            "source": n.get("source", ""),
            "date": n.get("published", ""),
        }
        # Find matching catalyst classification
        for c in catalysts:
            if c.get("title") == n.get("title"):
                cls = c.get("classification", {})
                item["classification"] = cls.get("classification", "")
                item["tags"] = []
                if cls.get("third_party_committed"):
                    item["tags"].append("Third party committed")
                if cls.get("capital_committed"):
                    item["tags"].append("Capital committed")
                if cls.get("capital_amount_cad"):
                    item["tags"].append(str(cls["capital_amount_cad"]))
                break
        items.append(item)
    s["news_items"] = items


# ─── Signal Endpoints ─────────────────────────────────────────────

@app.route("/api/signals", methods=["GET"])
def get_signals():
    """Return latest signals data. Optionally filter by period and exclude sectors."""
    period = request.args.get("period", "today")
    exclude_sectors_param = request.args.get("exclude_sectors", "")

    signals = _load_json(SIGNALS_LATEST_PATH, [])

    if not signals:
        return jsonify({
            "status": "no_data",
            "message": "No scan data available. Run a scan first.",
            "signals": [],
            "summary": {"total": 0, "signals": 0, "green": 0, "yellow": 0, "red": 0},
        })

    # Compute conviction scores before normalization (raw % values needed)
    for s in signals:
        if "conviction_score" not in s:
            conv = _conviction_score(s)
            s["conviction_score"] = conv["conviction_score"]
            s["conviction_grade"] = conv["conviction_grade"]
            s["conviction_sub_scores"] = conv["sub_scores"]
        _normalize_signal(s)

    # Filter out excluded sectors
    if exclude_sectors_param:
        exclude_set = {sec.strip() for sec in exclude_sectors_param.split(",") if sec.strip()}
        signals = [s for s in signals if s.get("sector", "Unknown") not in exclude_set]

    # Count by classification
    green = sum(1 for s in signals if s.get("catalyst_classification") == "GREEN")
    yellow = sum(1 for s in signals if s.get("catalyst_classification") == "YELLOW")
    red = sum(1 for s in signals if s.get("catalyst_classification") == "RED")
    signal_count = sum(1 for s in signals if s.get("is_signal"))

    return jsonify({
        "status": "ok",
        "period": period,
        "signals": signals,
        "summary": {
            "total": len(signals),
            "signals": signal_count,
            "green": green,
            "yellow": yellow,
            "red": red,
        },
        "last_scan": signals[0].get("scan_time") if signals else None,
    })


@app.route("/api/signals/scan", methods=["GET"])
def trigger_scan():
    """Trigger a fresh scan. Runs synchronously for v1."""
    period = request.args.get("period", "today")

    logger.info(f"Starting manual scan (period={period})...")

    try:
        results = screen_universe(period=period)

        # Fetch news and classify for signal stocks
        for stock in results:
            if stock.get("is_signal"):
                news = fetch_news_for_ticker(stock["ticker"], stock["name"])
                stock["news"] = news
                stock["news_count"] = len(news)

                if news:
                    classifications = []
                    for article in news[:3]:
                        cls = classify_catalyst(
                            stock["ticker"],
                            article["title"],
                            article.get("summary", ""),
                        )
                        classifications.append({
                            "title": article["title"],
                            "classification": cls,
                        })
                    stock["catalysts"] = classifications

                    priority = {"GREEN": 0, "YELLOW": 1, "RED": 2}
                    best = min(
                        classifications,
                        key=lambda c: priority.get(
                            c["classification"].get("classification", "RED"), 2
                        ),
                    )
                    stock["catalyst_classification"] = best["classification"].get(
                        "classification", "RED"
                    )
                else:
                    stock["catalysts"] = []
                    stock["catalyst_classification"] = None
            else:
                stock["news"] = []
                stock["news_count"] = 0
                stock["catalysts"] = []
                stock["catalyst_classification"] = None

        # Compute conviction scores
        for stock in results:
            conv = _conviction_score(stock)
            stock["conviction_score"] = conv["conviction_score"]
            stock["conviction_grade"] = conv["conviction_grade"]
            stock["conviction_sub_scores"] = conv["sub_scores"]

        # Save results
        _save_json(SIGNALS_LATEST_PATH, results)

        today_str = datetime.now().strftime("%Y-%m-%d")
        _save_json(DATA_DIR / f"signals_{today_str}.json", results)

        return jsonify({
            "status": "ok",
            "message": f"Scan complete. {len(results)} stocks processed.",
            "signals_count": sum(1 for r in results if r.get("is_signal")),
        })

    except Exception as e:
        logger.error(f"Scan failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── Watchlist Endpoints ──────────────────────────────────────────

@app.route("/api/watchlist", methods=["GET"])
def get_watchlist():
    """Return the current watchlist."""
    watchlist = _load_json(WATCHLIST_PATH, [])
    return jsonify({"status": "ok", "watchlist": watchlist})


@app.route("/api/watchlist", methods=["POST"])
def add_to_watchlist():
    """Add a stock to the watchlist."""
    data = request.get_json()
    if not data or "ticker" not in data:
        return jsonify({"status": "error", "message": "ticker is required"}), 400

    watchlist = _load_json(WATCHLIST_PATH, [])

    # Check for duplicates
    if any(w["ticker"] == data["ticker"] for w in watchlist):
        return jsonify({"status": "error", "message": "Ticker already in watchlist"}), 409

    entry = {
        "ticker": data["ticker"],
        "entry_price": data.get("entry_price"),
        "trade_type": data.get("trade_type", "swing"),
        "notes": data.get("notes", ""),
        "added_at": datetime.now().isoformat(),
    }

    watchlist.append(entry)
    _save_json(WATCHLIST_PATH, watchlist)

    return jsonify({"status": "ok", "entry": entry}), 201


@app.route("/api/watchlist/<ticker>", methods=["PUT"])
def update_watchlist(ticker):
    """Update a watchlist entry."""
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Request body required"}), 400

    watchlist = _load_json(WATCHLIST_PATH, [])

    for entry in watchlist:
        if entry["ticker"] == ticker:
            if "entry_price" in data:
                entry["entry_price"] = data["entry_price"]
            if "trade_type" in data:
                entry["trade_type"] = data["trade_type"]
            if "notes" in data:
                entry["notes"] = data["notes"]
            entry["updated_at"] = datetime.now().isoformat()

            _save_json(WATCHLIST_PATH, watchlist)
            return jsonify({"status": "ok", "entry": entry})

    return jsonify({"status": "error", "message": "Ticker not found in watchlist"}), 404


@app.route("/api/watchlist/<ticker>", methods=["DELETE"])
def remove_from_watchlist(ticker):
    """Remove a stock from the watchlist."""
    watchlist = _load_json(WATCHLIST_PATH, [])
    original_len = len(watchlist)

    watchlist = [w for w in watchlist if w["ticker"] != ticker]

    if len(watchlist) == original_len:
        return jsonify({"status": "error", "message": "Ticker not found in watchlist"}), 404

    _save_json(WATCHLIST_PATH, watchlist)
    return jsonify({"status": "ok", "message": f"{ticker} removed from watchlist"})


# ─── Stock Detail Endpoint ────────────────────────────────────────

@app.route("/api/stock/<ticker>", methods=["GET"])
def get_stock_detail(ticker):
    """Return detailed info for a single stock."""
    # Find in universe
    stock_info = None
    for s in UNIVERSE:
        if s["ticker"] == ticker:
            stock_info = s
            break

    if not stock_info:
        return jsonify({"status": "error", "message": "Ticker not found in universe"}), 404

    # Check latest signals for cached data
    signals = _load_json(SIGNALS_LATEST_PATH, [])
    cached = next((s for s in signals if s["ticker"] == ticker), None)

    # Fetch fresh news
    news = fetch_news_for_ticker(ticker, stock_info["name"])

    # Classify top news item if available
    catalyst = None
    if news:
        catalyst = classify_catalyst(
            ticker,
            news[0]["title"],
            news[0].get("summary", ""),
        )

    result = {
        "ticker": ticker,
        "name": stock_info["name"],
        "exchange": stock_info["exchange"],
        "sector": stock_info.get("sector", "Unknown"),
        "price_data": cached if cached else {},
        "news": news,
        "catalyst": catalyst,
    }

    return jsonify({"status": "ok", "stock": result})


# ─── History Endpoints ───────────────────────────────────────────

@app.route("/api/history", methods=["GET"])
def get_history():
    """Return scan history index (list of all past scans with summary stats)."""
    history = _load_json(SCAN_HISTORY_PATH, {"scans": []})
    if isinstance(history, dict):
        scans = history.get("scans", [])
    else:
        scans = history
    return jsonify({"status": "ok", "scans": scans})


@app.route("/api/history/<date>", methods=["GET"])
def get_history_date(date):
    """Return signals data for a specific date."""
    signals_path = DATA_DIR / f"signals_{date}.json"
    if not signals_path.exists():
        return jsonify({"status": "error", "message": f"No scan data for {date}"}), 404

    signals = _load_json(signals_path, [])

    # Compute conviction scores and normalize (same as main signals endpoint)
    for s in signals:
        if "conviction_score" not in s:
            conv = _conviction_score(s)
            s["conviction_score"] = conv["conviction_score"]
            s["conviction_grade"] = conv["conviction_grade"]
            s["conviction_sub_scores"] = conv["sub_scores"]
        _normalize_signal(s)

    # Count by classification
    green = sum(1 for s in signals if s.get("catalyst_classification") == "GREEN")
    yellow = sum(1 for s in signals if s.get("catalyst_classification") == "YELLOW")
    red = sum(1 for s in signals if s.get("catalyst_classification") == "RED")
    signal_count = sum(1 for s in signals if s.get("is_signal"))

    return jsonify({
        "status": "ok",
        "date": date,
        "signals": signals,
        "summary": {
            "total": len(signals),
            "signals": signal_count,
            "green": green,
            "yellow": yellow,
            "red": red,
        },
        "last_scan": signals[0].get("scan_time") if signals else None,
    })


# ─── Health Check ─────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


if __name__ == "__main__":
    print("=" * 50)
    print("Momentum Scanner API")
    print("=" * 50)
    print(f"Server: http://localhost:5001")
    print(f"Docs:   GET /api/signals, /api/watchlist, /api/stock/<ticker>")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5001, debug=True)
