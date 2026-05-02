"""
Catalyst classifier using Claude API (or mock fallback).
Classifies press releases into GREEN / YELLOW / RED categories.
"""

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"
CATALYST_CACHE_PATH = DATA_DIR / "catalyst_cache.json"

SYSTEM_PROMPT = """You are a Canadian small-cap stock catalyst classifier.
Given a press release title and text, classify the catalyst into one of three categories:

GREEN (Strong, verifiable catalyst):
- Regulatory clearance or approval
- Government grant or equity investment
- Public company equity investment
- Purchase order (with dollar value)
- Master services agreement
- Audited earnings beat

YELLOW (Moderate catalyst, needs verification):
- Pilot program conversion to full contract
- Credit facility secured
- Analyst initiation of coverage
- Bought deal financing

RED (Weak or unverifiable catalyst):
- Letter of Intent (LOI)
- Memorandum of Understanding (MOU)
- Advisory board appointment
- Partnership announcement without capital commitment
- Pilot program (not yet converted)

Respond ONLY with valid JSON in this exact format:
{
  "catalyst_type": "string describing the catalyst type",
  "third_party_committed": true/false,
  "third_party_name": "name or null",
  "capital_committed": true/false,
  "capital_amount_cad": "dollar amount or null",
  "classification": "GREEN/YELLOW/RED",
  "reasoning": "1-2 sentence explanation",
  "red_flags": ["list of any red flags or empty array"]
}"""


def _load_cache():
    """Load catalyst cache from disk."""
    if CATALYST_CACHE_PATH.exists():
        try:
            with open(CATALYST_CACHE_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_cache(cache):
    """Save catalyst cache to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(CATALYST_CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2, default=str)
    except IOError as e:
        logger.error(f"Failed to save catalyst cache: {e}")


def _mock_classify(title, text):
    """
    Simple keyword-based mock classification when API key is not available.
    """
    combined = f"{title} {text}".lower()

    # GREEN keywords
    green_keywords = ["agreement", "order", "clearance", "grant", "approval",
                      "purchase order", "regulatory", "contract awarded",
                      "earnings beat", "revenue growth"]
    # YELLOW keywords
    yellow_keywords = ["bought deal", "analyst", "credit", "facility",
                       "initiation", "coverage", "financing", "pilot conversion"]
    # RED keywords (or default)
    red_keywords = ["loi", "letter of intent", "mou", "memorandum",
                    "advisory", "partnership", "pilot program", "exploring"]

    classification = "RED"
    catalyst_type = "Unknown"

    for kw in green_keywords:
        if kw in combined:
            classification = "GREEN"
            catalyst_type = kw.title()
            break

    if classification == "RED":
        for kw in yellow_keywords:
            if kw in combined:
                classification = "YELLOW"
                catalyst_type = kw.title()
                break

    if classification == "RED":
        for kw in red_keywords:
            if kw in combined:
                catalyst_type = kw.title()
                break

    return {
        "catalyst_type": catalyst_type,
        "third_party_committed": classification == "GREEN",
        "third_party_name": None,
        "capital_committed": classification == "GREEN",
        "capital_amount_cad": None,
        "classification": classification,
        "reasoning": f"Mock classification based on keyword matching ('{catalyst_type}' detected in text).",
        "red_flags": [] if classification == "GREEN" else ["Mock classification - verify manually"],
    }


def classify_catalyst(ticker, press_release_title, press_release_text):
    """
    Classify a press release catalyst using Claude API.
    Falls back to mock classification if API key is not set.

    Args:
        ticker: Stock ticker
        press_release_title: Title of the press release
        press_release_text: Body text of the press release

    Returns:
        Dict with classification results
    """
    # Check cache first
    cache = _load_cache()
    cache_key = f"{ticker}_{press_release_title[:80]}"

    if cache_key in cache:
        logger.info(f"Catalyst cache hit for {ticker}")
        return cache[cache_key]

    # Check API key
    api_key = os.getenv("ANTHROPIC_API_KEY", "your_key_here")

    if not api_key or api_key == "your_key_here":
        logger.info(f"No API key set, using mock classification for {ticker}")
        result = _mock_classify(press_release_title, press_release_text)
        cache[cache_key] = result
        _save_cache(cache)
        return result

    # Use Claude API
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        user_message = (
            f"Ticker: {ticker}\n"
            f"Title: {press_release_title}\n"
            f"Text: {press_release_text[:3000]}"
        )

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_message}
            ],
        )

        response_text = response.content[0].text.strip()

        # Parse JSON from response
        # Handle case where response might have markdown code fences
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        result = json.loads(response_text)

        # Cache result
        cache[cache_key] = result
        _save_cache(cache)

        logger.info(f"Classified {ticker}: {result.get('classification', 'UNKNOWN')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude response for {ticker}: {e}")
        result = _mock_classify(press_release_title, press_release_text)
        cache[cache_key] = result
        _save_cache(cache)
        return result

    except Exception as e:
        logger.error(f"Claude API error for {ticker}: {e}")
        result = _mock_classify(press_release_title, press_release_text)
        cache[cache_key] = result
        _save_cache(cache)
        return result
