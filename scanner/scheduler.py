"""
Scheduler for the momentum scanner pipeline.
Uses Yahoo Finance screener API for instant movers (no full universe scan).

Usage:
    python -m scanner.scheduler          # Run immediately
    python -m scanner.scheduler --daemon  # Run daily at 5:00 PM ET
"""

import json
import logging
import sys
import time
import shutil
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"


def _ts():
    return datetime.now().strftime("%H:%M:%S")


def daily_run():
    """
    Fast daily scan pipeline:
    1. Query Yahoo Finance screener for Canadian gainers (1-2 sec)
    2. Enrich with multi-day price history (1-2 min)
    3. Fetch news for movers (1-2 min)
    4. Classify catalysts
    5. Compute scores
    6. Save to history + latest
    """
    from scanner.price_screen_v2 import (
        get_daily_movers, enrich_history, enrich_sectors,
        _momentum_score, _conviction_score, _macro_trend_tags,
    )
    from scanner.news_fetch import fetch_news_for_ticker
    from scanner.catalyst_classify import classify_catalyst

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    start_time = time.time()
    today_str = datetime.now().strftime("%Y-%m-%d")

    print("=" * 60)
    print(f"MOMENTUM SCANNER - Daily Run {today_str}")
    print(f"Started at {_ts()}")
    print("=" * 60)

    # ── Step 1: Get daily movers via screener ────────────────────
    print(f"\n[{_ts()}] Step 1/6: Querying Yahoo Finance screener...")
    try:
        movers = get_daily_movers(min_pct=3.0, max_results=250)
    except Exception as e:
        logger.error(f"Fatal: screener query failed: {e}")
        print(f"[{_ts()}] FATAL: Screener failed. Aborting.")
        return
    print(f"[{_ts()}]   {len(movers)} Canadian gainers found")

    # ── Step 2a: Enrich sectors ─────────────────────────────────
    print(f"\n[{_ts()}] Step 2/7: Enriching sectors...")
    try:
        enrich_sectors(movers)
    except Exception as e:
        logger.error(f"Sector enrichment failed: {e}")

    # ── Step 2b: Enrich with price history ────────────────────────
    print(f"\n[{_ts()}] Step 3/7: Enriching with price history...")
    try:
        enrich_history(movers)
    except Exception as e:
        logger.error(f"History enrichment failed: {e}")
    print(f"[{_ts()}]   Done")

    # ── Step 3: Add macro trend tags + momentum scores ───────────
    print(f"\n[{_ts()}] Step 3/6: Computing momentum scores + macro tags...")
    for stock in movers:
        stock['macro_trends'] = _macro_trend_tags(stock)
        stock['momentum_score'] = _momentum_score(stock)

    # ── Step 4: Fetch news for movers ────────────────────────────
    print(f"\n[{_ts()}] Step 4/6: Fetching news for {len(movers)} movers...")
    news_found = 0
    for i, stock in enumerate(movers, 1):
        try:
            news = fetch_news_for_ticker(stock['ticker'], stock['name'])
            stock['news'] = news
            stock['news_count'] = len(news)
            if news:
                news_found += 1
        except Exception as e:
            logger.debug(f"News fetch failed for {stock['ticker']}: {e}")
            stock['news'] = []
            stock['news_count'] = 0

        if i % 50 == 0 or i == len(movers):
            print(f"[{_ts()}]   {i}/{len(movers)} fetched, {news_found} with news")

    # ── Step 5: Classify catalysts ───────────────────────────────
    print(f"\n[{_ts()}] Step 5/6: Classifying catalysts...")
    classified = 0
    for stock in movers:
        if stock.get('news'):
            try:
                classifications = []
                for article in stock['news'][:2]:
                    cls = classify_catalyst(
                        stock['ticker'], article['title'],
                        article.get('summary', ''),
                    )
                    classifications.append({
                        'title': article['title'],
                        'classification': cls,
                    })
                stock['catalysts'] = classifications
                priority = {'GREEN': 0, 'YELLOW': 1, 'RED': 2}
                best = min(classifications,
                           key=lambda c: priority.get(
                               c['classification'].get('classification', 'RED'), 2))
                stock['catalyst_classification'] = best['classification'].get(
                    'classification', 'RED')
                classified += 1
            except Exception as e:
                logger.debug(f"Classification failed for {stock['ticker']}: {e}")
                stock['catalysts'] = []
                stock['catalyst_classification'] = None
        else:
            stock['catalysts'] = []
            stock['catalyst_classification'] = None

    print(f"[{_ts()}]   Classified {classified} movers")

    # ── Step 6: Compute conviction scores + save ─────────────────
    print(f"\n[{_ts()}] Step 6/6: Computing conviction scores + saving...")
    for stock in movers:
        try:
            conv = _conviction_score(stock)
            stock['conviction_score'] = conv['conviction_score']
            stock['conviction_grade'] = conv['conviction_grade']
            stock['conviction_sub_scores'] = conv['sub_scores']
        except Exception:
            stock['conviction_score'] = 0
            stock['conviction_grade'] = 'D'
            stock['conviction_sub_scores'] = {}

    # Sort by conviction score descending
    movers.sort(key=lambda s: s.get('conviction_score', 0), reverse=True)

    # Save dated file
    dated_path = DATA_DIR / f"signals_{today_str}.json"
    with open(dated_path, "w") as f:
        json.dump(movers, f, indent=2, default=str)

    # Copy to latest
    latest_path = DATA_DIR / "signals_latest.json"
    shutil.copy2(dated_path, latest_path)

    # Update history index
    runtime_seconds = round(time.time() - start_time)
    confirmed_count = sum(1 for s in movers if s.get('news'))
    top_stock = max(movers, key=lambda s: s.get('conviction_score', 0)) if movers else {}

    history_entry = {
        "date": today_str,
        "file": f"signals_{today_str}.json",
        "total_movers": len(movers),
        "signals": len(movers),
        "confirmed": confirmed_count,
        "top_conviction": {
            "ticker": top_stock.get("ticker", ""),
            "score": top_stock.get("conviction_score", 0),
            "grade": top_stock.get("conviction_grade", ""),
        },
        "runtime_seconds": runtime_seconds,
    }

    history_path = DATA_DIR / "scan_history.json"
    if history_path.exists():
        try:
            with open(history_path) as f:
                history = json.load(f)
        except Exception:
            history = {"scans": []}
    else:
        history = {"scans": []}

    history["scans"] = [s for s in history["scans"] if s["date"] != today_str]
    history["scans"].append(history_entry)
    history["scans"].sort(key=lambda s: s["date"], reverse=True)
    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)

    # Summary
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print("\n" + "=" * 60)
    print("SCAN COMPLETE")
    print(f"  Movers found:   {len(movers)}")
    print(f"  With news:      {confirmed_count}")
    print(f"  Top conviction: {top_stock.get('ticker', '?')} "
          f"({top_stock.get('conviction_grade', '?')} {top_stock.get('conviction_score', 0)})")
    print(f"  Runtime:        {minutes}m {seconds}s")
    print("=" * 60)

    return movers


if __name__ == "__main__":
    if "--daemon" in sys.argv:
        from apscheduler.schedulers.blocking import BlockingScheduler
        scheduler = BlockingScheduler()
        scheduler.add_job(daily_run, "cron", hour=17, minute=0, timezone="US/Eastern")
        print("Scheduler started. Will run daily at 5:00 PM ET.")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            print("Scheduler stopped.")
    else:
        daily_run()
