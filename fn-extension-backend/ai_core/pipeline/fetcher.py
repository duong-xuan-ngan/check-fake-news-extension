"""Step 6: Fetch article bodies from credible sources.

Primary: newspaper3k (built for news, handles most sites).
Fallback: requests + BeautifulSoup <p> extraction.
JS-heavy sites (Playwright) are explicitly v2 scope.

Also extracts publish_date when available. None when the site doesn't expose
a parseable date — the synthesizer treats date-missing articles as lower weight.

Install deps if needed:
    pip install newspaper3k beautifulsoup4 lxml requests
"""
import json
import requests
from datetime import datetime
from typing import List, Optional, Tuple
from bs4 import BeautifulSoup
from newspaper import Article

from ..schema import ScoredResult, FetchedArticle

MIN_BODY_LENGTH = 150   # ~3-4 sentences; shorter bodies are skipped
MAX_BODY_LENGTH = 3000  # truncation limit passed to LLM
REQUEST_TIMEOUT = 8     # seconds per article

# Meta tags to check for publication date, in order of reliability.
_DATE_META_TAGS = [
    {"property": "article:published_time"},   # OpenGraph
    {"name": "publish-date"},
    {"name": "publication_date"},
    {"name": "date"},
    {"itemprop": "datePublished"},
]


def _parse_iso_date(raw: str) -> Optional[datetime]:
    """Parse an ISO-8601 date string. Returns None if unparseable."""
    if not raw:
        return None
    try:
        # Handle trailing 'Z' (Zulu time) which fromisoformat rejects pre-3.11
        cleaned = raw.strip().replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        return None


def _fetch_with_newspaper(url: str) -> Tuple[Optional[str], Optional[datetime]]:
    """Try newspaper3k first — handles most news sites cleanly.

    Returns (body, publish_date). Either or both may be None.
    """
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text or None, article.publish_date
    except Exception as e:
        print(f"[fetcher] newspaper3k failed for {url}: {e}")
        return None, None


def _fetch_with_bs4(url: str) -> Tuple[Optional[str], Optional[datetime]]:
    """Fallback: grab all <p> tags + scan meta tags for publish date.

    Returns (body, publish_date). Either or both may be None.
    """
    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        # Body
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
        body = " ".join(paragraphs) or None

        # Publish date — try each known meta tag, stop at the first parseable hit
        publish_date = None
        for attrs in _DATE_META_TAGS:
            tag = soup.find("meta", attrs=attrs)
            if tag and tag.get("content"):
                publish_date = _parse_iso_date(tag["content"])
                if publish_date:
                    break

        return body, publish_date
    except Exception as e:
        print(f"[fetcher] bs4 fallback failed for {url}: {e}")
        return None, None


def _extract_date_from_html(url: str) -> Optional[datetime]:
    """Standalone date scraper. Tries meta tags, then JSON-LD, then <time> elements.

    Used as a supplement when newspaper3k succeeds on body but misses the date.
    Returns None on any failure.
    """
    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        # Strategy 1: standard meta tags
        for attrs in _DATE_META_TAGS:
            tag = soup.find("meta", attrs=attrs)
            if tag and tag.get("content"):
                parsed = _parse_iso_date(tag["content"])
                if parsed:
                    return parsed

        # Strategy 2: JSON-LD structured data (used heavily by ESPN, NYT, etc.)
        # Search every <script type="application/ld+json"> for a datePublished field.
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except (json.JSONDecodeError, TypeError):
                continue
            # JSON-LD can be a dict or a list of dicts; normalize to a list
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get("datePublished"):
                    parsed = _parse_iso_date(item["datePublished"])
                    if parsed:
                        return parsed

        # Strategy 3: <time datetime="..."> element
        time_tag = soup.find("time", attrs={"datetime": True})
        if time_tag:
            parsed = _parse_iso_date(time_tag["datetime"])
            if parsed:
                return parsed

        return None
    except Exception as e:
        print(f"[fetcher] date scrape failed for {url}: {e}")
        return None


def _fetch_article(url: str) -> Tuple[Optional[str], Optional[datetime]]:
    """Try newspaper3k, fall back to bs4. Return (body, date), either may be None.

    Body must meet length thresholds; date is optional. If newspaper3k succeeds
    on body but misses the date, do a supplementary meta-tag scrape.
    """
    body, publish_date = _fetch_with_newspaper(url)

    # If newspaper3k failed entirely or returned too-short body, try bs4
    if not body:
        body, bs4_date = _fetch_with_bs4(url)
        if publish_date is None:
            publish_date = bs4_date

    # newspaper3k often misses dates even when it gets the body right.
    # Supplementary meta-tag scrape — costs one HTTP request but high payoff.
    if body and publish_date is None:
        publish_date = _extract_date_from_html(url)

    if not body or len(body) < MIN_BODY_LENGTH:
        return None, None

    return body[:MAX_BODY_LENGTH], publish_date


def fetch_all(results: List[ScoredResult]) -> List[FetchedArticle]:
    """Fetch article bodies + publish dates. Skips results where body is empty or too short.

    v1: sequential. v2 scope: asyncio / ThreadPoolExecutor for concurrency.
    """
    output = []
    for result in results:
        body, publish_date = _fetch_article(result.url)
        if body is None:
            print(f"[fetcher] skipping {result.domain} — body too short or fetch failed")
            continue
        output.append(FetchedArticle(
            url=result.url,
            domain=result.domain,
            title=result.title,
            body=body,
            credibility_score=result.credibility_score,
            rating_status=result.rating_status,
            published_at=publish_date,
        ))
    return output
