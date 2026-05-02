"""
Enrich universe_full.json with GICS sector, industry, market cap, and shares data from yfinance.

Usage:
    python scanner/enrich_sectors.py

Prioritizes tickers from signals_latest.json, then processes the rest.
Saves progress every 50 tickers.
"""

import json
import os
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
UNIVERSE_FILE = os.path.join(DATA_DIR, 'universe_full.json')
SIGNALS_FILE = os.path.join(DATA_DIR, 'signals_latest.json')

# CAD/USD conversion factor
USD_TO_CAD = 1.36

# Sectors that count as "not enriched"
UNKNOWN_SECTORS = {'Unknown', 'Other', ''}


def _needs_enrichment(entry):
    """Check if a ticker needs any enrichment work."""
    sector = entry.get('sector', 'Other')
    industry = entry.get('industry', '')
    market_cap_cad = entry.get('market_cap_cad', 0)

    sector_ok = sector not in UNKNOWN_SECTORS
    industry_ok = bool(industry)
    mcap_ok = market_cap_cad and market_cap_cad > 0

    return not (sector_ok and industry_ok and mcap_ok)


def fetch_ticker_info(ticker_symbol):
    """Fetch sector, industry, market cap, and shares from yfinance."""
    try:
        time.sleep(0.2)  # Rate limit delay
        t = yf.Ticker(ticker_symbol)
        info = t.info

        sector = info.get('sector', '')
        industry = info.get('industry', '')
        market_cap = info.get('marketCap', 0) or 0
        currency = info.get('currency', 'CAD')
        float_shares = info.get('floatShares', 0) or 0
        shares_outstanding = info.get('sharesOutstanding', 0) or 0

        # Convert USD market cap to CAD
        if currency and currency.upper() == 'USD' and market_cap > 0:
            market_cap_cad = int(market_cap * USD_TO_CAD)
        else:
            market_cap_cad = int(market_cap)

        shares = shares_outstanding or float_shares

        return {
            'ticker': ticker_symbol,
            'sector': sector,
            'industry': industry,
            'market_cap_cad': market_cap_cad,
            'shares_outstanding': shares,
            'success': bool(sector or industry or market_cap_cad > 0),
        }
    except Exception as e:
        return {
            'ticker': ticker_symbol,
            'sector': '',
            'industry': '',
            'market_cap_cad': 0,
            'shares_outstanding': 0,
            'success': False,
        }


def main():
    # Load universe
    with open(UNIVERSE_FILE, 'r') as f:
        universe = json.load(f)

    # Build index: yf_ticker -> list index
    ticker_idx = {}
    for i, entry in enumerate(universe):
        yf_t = entry.get('yf_ticker', entry['ticker'])
        ticker_idx[yf_t] = i

    # Load signals to prioritize
    signal_tickers = set()
    if os.path.exists(SIGNALS_FILE):
        with open(SIGNALS_FILE, 'r') as f:
            signals = json.load(f)
        signal_tickers = {s.get('yf_ticker', s['ticker']) for s in signals}
        print(f"Loaded {len(signal_tickers)} tickers from signals_latest.json")

    # Find tickers needing enrichment
    needs_work = []
    already_done = 0
    for entry in universe:
        if _needs_enrichment(entry):
            needs_work.append(entry.get('yf_ticker', entry['ticker']))
        else:
            already_done += 1

    print(f"Universe: {len(universe)} tickers")
    print(f"Already fully enriched: {already_done}")
    print(f"Need enrichment: {len(needs_work)}")

    # Prioritize: signal tickers first, then others
    signal_work = [t for t in needs_work if t in signal_tickers]
    other_work = [t for t in needs_work if t not in signal_tickers]
    work_queue = signal_work + other_work

    print(f"Signal tickers to enrich: {len(signal_work)}")
    print(f"Other tickers to enrich: {len(other_work)}")
    print()

    enriched_count = 0
    failed_count = 0
    sector_counts = {}
    mcap_ranges = {'<1M': 0, '1M-10M': 0, '10M-100M': 0, '100M-1B': 0, '>1B': 0}

    total = len(work_queue)
    start_time = time.time()
    processed = 0
    max_workers = 5

    def save_progress():
        with open(UNIVERSE_FILE, 'w') as f:
            json.dump(universe, f, indent=2)

    # Process using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for yf_t in work_queue:
            future = executor.submit(fetch_ticker_info, yf_t)
            futures[future] = yf_t

        for future in as_completed(futures):
            result = future.result()
            processed += 1
            yf_t = result['ticker']

            idx = ticker_idx.get(yf_t)
            if idx is None:
                failed_count += 1
                continue

            if result['success']:
                entry = universe[idx]
                # Update sector/industry only if we got valid data
                if result['sector']:
                    entry['sector'] = result['sector']
                if result['industry']:
                    entry['industry'] = result['industry']
                if result['market_cap_cad'] > 0:
                    entry['market_cap_cad'] = result['market_cap_cad']
                if result['shares_outstanding'] > 0:
                    entry['shares_outstanding'] = result['shares_outstanding']

                enriched_count += 1

                # Track stats
                s = result['sector'] or entry.get('sector', 'Unknown')
                sector_counts[s] = sector_counts.get(s, 0) + 1

                mcap = result['market_cap_cad']
                if mcap > 0:
                    if mcap < 1_000_000:
                        mcap_ranges['<1M'] += 1
                    elif mcap < 10_000_000:
                        mcap_ranges['1M-10M'] += 1
                    elif mcap < 100_000_000:
                        mcap_ranges['10M-100M'] += 1
                    elif mcap < 1_000_000_000:
                        mcap_ranges['100M-1B'] += 1
                    else:
                        mcap_ranges['>1B'] += 1
            else:
                failed_count += 1

            # Progress and save every 50
            if processed % 50 == 0:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                eta = (total - processed) / rate if rate > 0 else 0
                print(f"  [{processed}/{total}] enriched={enriched_count} failed={failed_count} "
                      f"rate={rate:.1f}/s ETA={eta:.0f}s")
                save_progress()

    # Final save
    save_progress()

    elapsed = time.time() - start_time
    print(f"\nDone in {elapsed:.1f}s")
    print(f"Enriched: {enriched_count}")
    print(f"Failed/no data: {failed_count}")

    # Final stats from full universe
    print(f"\n--- Sector Distribution (full universe) ---")
    full_sector_counts = {}
    full_mcap_ranges = {'<1M': 0, '1M-10M': 0, '10M-100M': 0, '100M-1B': 0, '>1B': 0, 'No data': 0}
    has_mcap = 0
    for entry in universe:
        s = entry.get('sector', 'Unknown')
        full_sector_counts[s] = full_sector_counts.get(s, 0) + 1
        mcap = entry.get('market_cap_cad', 0)
        if mcap > 0:
            has_mcap += 1
            if mcap < 1_000_000:
                full_mcap_ranges['<1M'] += 1
            elif mcap < 10_000_000:
                full_mcap_ranges['1M-10M'] += 1
            elif mcap < 100_000_000:
                full_mcap_ranges['10M-100M'] += 1
            elif mcap < 1_000_000_000:
                full_mcap_ranges['100M-1B'] += 1
            else:
                full_mcap_ranges['>1B'] += 1
        else:
            full_mcap_ranges['No data'] += 1

    for sector, count in sorted(full_sector_counts.items(), key=lambda x: -x[1]):
        print(f"  {sector}: {count}")

    print(f"\n--- Market Cap Distribution (full universe) ---")
    print(f"  Tickers with market cap: {has_mcap}/{len(universe)}")
    for bucket, count in full_mcap_ranges.items():
        print(f"  {bucket}: {count}")


if __name__ == '__main__':
    main()
