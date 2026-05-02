"""
News fetcher for Canadian small-cap tickers.
Uses yfinance news (which pulls from Yahoo Finance) and GlobeNewswire search.
Caches results to avoid repeated lookups.
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
NEWS_CACHE_PATH = DATA_DIR / "news_cache.json"


def _load_cache():
    if NEWS_CACHE_PATH.exists():
        try:
            with open(NEWS_CACHE_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_cache(cache):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(NEWS_CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2, default=str)
    except IOError as e:
        logger.error(f"Failed to save news cache: {e}")


def _normalize_date(raw):
    """Normalize a date value that may be a Unix timestamp or ISO string."""
    if not raw:
        return ""
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw, tz=timezone.utc).isoformat()
    if isinstance(raw, str) and raw.isdigit():
        return datetime.fromtimestamp(int(raw), tz=timezone.utc).isoformat()
    return str(raw)


_COMPANY_SUFFIXES = {
    "inc.", "inc", "corp.", "corp", "ltd.", "ltd", "limited",
    "technologies", "technology", "holdings", "group", "international",
    "enterprises", "solutions", "services", "capital", "resources",
    "co.", "co", "plc",
}


def _clean_company_query(company_name):
    """Extract 2-3 significant words from a company name for search."""
    words = company_name.split()
    significant = [w for w in words if w.lower().rstrip(".,") not in _COMPANY_SUFFIXES]
    # Take first 2-3 significant words
    return " ".join(significant[:3])


def _fetch_google_news(ticker, company_name, days=14):
    """Fetch news from Google News RSS for a ticker/company."""
    results = []
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

    queries = []
    # Primary query: cleaned company name
    clean_name = _clean_company_query(company_name)
    if clean_name:
        queries.append(clean_name)
    # Secondary query: ticker symbol
    queries.append(ticker)

    for i, query in enumerate(queries):
        if i > 0:
            time.sleep(0.5)
        try:
            url = (
                f"https://news.google.com/rss/search?"
                f"q={requests.utils.quote(query)}&hl=en-CA&gl=CA&ceid=CA:en"
            )
            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 429:
                logger.debug(f"Google News rate limited for '{query}', skipping")
                continue
            feed = feedparser.parse(resp.content)

            for entry in feed.entries:
                # Parse published date
                pub_raw = entry.get("published", "")
                pub_normalized = _normalize_date(pub_raw)

                # Filter by date
                try:
                    if pub_raw:
                        pub_struct = entry.get("published_parsed")
                        if pub_struct:
                            pub_dt = datetime(*pub_struct[:6], tzinfo=timezone.utc)
                            if pub_dt < cutoff:
                                continue
                except Exception:
                    pass

                title_full = entry.get("title", "")
                # Google News format: "Article title - Publisher Name"
                if " - " in title_full:
                    title = title_full.rsplit(" - ", 1)[0].strip()
                    source = title_full.rsplit(" - ", 1)[1].strip()
                else:
                    title = title_full
                    source = "Google News"

                summary = entry.get("summary", "")
                # Strip HTML tags from summary
                if "<" in summary:
                    import re
                    summary = re.sub(r"<[^>]+>", "", summary)

                link = entry.get("link", "")

                results.append({
                    "title": title,
                    "summary": summary[:500] if summary else "",
                    "published": pub_normalized,
                    "source": source,
                    "link": link,
                })

        except Exception as e:
            logger.debug(f"Google News RSS error for query '{query}': {e}")

    return results


def _fetch_yfinance_news(yf_ticker, days=14):
    """Pull news from yfinance (Yahoo Finance)."""
    results = []
    try:
        tk = yf.Ticker(yf_ticker)
        news = tk.news or []
        cutoff = datetime.now() - timedelta(days=days)

        for item in news:
            content = item.get("content", {})
            title = content.get("title", "")
            pub_date = _normalize_date(content.get("pubDate", ""))
            summary = content.get("summary", "")
            provider = content.get("provider", {}).get("displayName", "Yahoo Finance")
            link = content.get("canonicalUrl", {}).get("url", "")

            if not title:
                continue

            results.append({
                "title": title,
                "summary": summary[:500] if summary else "",
                "published": pub_date,
                "source": provider,
                "link": link,
            })

    except Exception as e:
        logger.warning(f"yfinance news error for {yf_ticker}: {e}")

    return results


def _fetch_gnw_search(company_name, days=14):
    """Search GlobeNewswire for company press releases."""
    results = []
    try:
        # Use first distinctive word of company name
        search_term = company_name.split()[0]
        if len(search_term) < 3:
            search_term = company_name

        url = "https://www.globenewswire.com/Search"
        params = {
            "keyword": search_term,
            "pageSize": 5,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; MomentumScanner/1.0)",
            "Accept": "application/json",
        }

        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200 and "application/json" in resp.headers.get("content-type", ""):
            data = resp.json()
            for item in data.get("results", [])[:5]:
                results.append({
                    "title": item.get("headline", ""),
                    "summary": item.get("description", "")[:500],
                    "published": item.get("date", ""),
                    "source": "GlobeNewswire",
                    "link": item.get("url", ""),
                })
    except Exception as e:
        logger.debug(f"GlobeNewswire search error: {e}")

    return results


def fetch_news_for_ticker(ticker, company_name, days=14):
    """
    Fetch news for a given ticker. Tries yfinance first, then GlobeNewswire.

    Args:
        ticker: Stock ticker (e.g. "ZDC.V")
        company_name: Full company name for search matching
        days: Number of days back to search (default 14)

    Returns:
        List of dicts with title, summary, published, source, link
    """
    cache = _load_cache()
    today = datetime.now().strftime("%Y-%m-%d")
    cache_key = f"{ticker}_{today}"

    if cache_key in cache:
        return cache[cache_key]

    # Primary: Google News RSS (best coverage for Canadian small-caps)
    results = _fetch_google_news(ticker, company_name, days=days)

    # Supplement: yfinance news
    time.sleep(0.3)
    yf_news = _fetch_yfinance_news(ticker, days=days)
    results.extend(yf_news)

    # Deduplicate by title
    seen = set()
    deduped = []
    for item in results:
        if item["title"] and item["title"] not in seen:
            seen.add(item["title"])
            deduped.append(item)

    # Limit to 5 most recent
    deduped = deduped[:5]

    cache[cache_key] = deduped
    _save_cache(cache)

    return deduped
