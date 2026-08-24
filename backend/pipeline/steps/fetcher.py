"""Fetch safe article evidence and keep only the excerpts relevant to a claim.

The server downloads sources itself, so URLs must be checked before every
request and redirect. Long articles are read in full first, then reduced to a
small set of relevant excerpts before being sent to the LLM.
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# newspaper3k uses unescaped regex strings that trip Python 3.12+ SyntaxWarnings.
warnings.filterwarnings("ignore", category=SyntaxWarning, module=r"newspaper")
from newspaper import Article

from ..schema import FetchedArticle, ScoredResult

MIN_BODY_LENGTH = 150
MAX_BODY_LENGTH = 3000  # Maximum evidence text supplied to the LLM per article.
MAX_ARTICLE_TEXT_LENGTH = 120_000  # Keep extraction bounded before excerpt selection.
EXCERPT_CHUNK_SIZE = 900
EXCERPT_CHUNK_OVERLAP = 150
MAX_RELEVANT_EXCERPTS = 3
REQUEST_TIMEOUT = 5
MAX_ARTICLES = 10
MAX_WORKERS = 10
MAX_REDIRECTS = 2
MAX_RESPONSE_BYTES = 2_000_000

_REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
_BLOCKED_HOSTS = {"localhost", "localhost.localdomain", "metadata.google.internal"}
_WORD_RE = re.compile(r"[a-z0-9][a-z0-9'-]*", re.IGNORECASE)
_COMMON_CLAIM_WORDS = {
    "about", "after", "among", "article", "based", "best", "claim", "could",
    "does", "from", "have", "into", "most", "news", "that", "the", "their",
    "then", "they", "this", "was", "were", "what", "when", "where", "which",
    "with", "would", "your",
}

_DATE_META_TAGS = [
    {"property": "article:published_time"},
    {"name": "publish-date"},
    {"name": "publication_date"},
    {"name": "date"},
    {"itemprop": "datePublished"},
]


def _parse_iso_date(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _is_public_ip(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False


def _is_safe_external_url(url: str) -> bool:
    """Allow only public HTTP(S) destinations.

    This blocks loopback, private Docker/VPC addresses, link-local addresses
    (including the cloud metadata endpoint), and non-web protocols.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        if parsed.port not in {None, 80, 443}:
            return False
        hostname = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    except (UnicodeError, ValueError):
        return False

    if hostname in _BLOCKED_HOSTS or hostname.endswith(".localhost"):
        return False
    if _is_public_ip(hostname):
        return True

    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        }
    except socket.gaierror:
        return False
    return bool(addresses) and all(_is_public_ip(address) for address in addresses)


def _safe_fetch_html(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Fetch a public URL without following an unchecked redirect."""
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        if not _is_safe_external_url(current_url):
            print(f"[fetcher] blocked unsafe URL: {current_url!r}")
            return None, None

        try:
            response = requests.get(
                current_url,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0"},
                allow_redirects=False,
            )
        except Exception as exc:
            print(f"[fetcher] request failed for {current_url!r}: {exc}")
            return None, None

        if response.status_code in _REDIRECT_STATUS_CODES:
            location = response.headers.get("location")
            if not location:
                print(f"[fetcher] redirect without location: {current_url!r}")
                return None, None
            current_url = urljoin(current_url, location)
            continue

        try:
            response.raise_for_status()
        except Exception as exc:
            print(f"[fetcher] HTTP request failed for {current_url!r}: {exc}")
            return None, None

        if len(response.content) > MAX_RESPONSE_BYTES:
            print(f"[fetcher] response too large for {current_url!r}")
            return None, None
        return response.text, current_url

    print(f"[fetcher] too many redirects for {url!r}")
    return None, None


def _parse_with_newspaper(url: str, html: str) -> Tuple[Optional[str], Optional[datetime]]:
    """Parse already-safe HTML without letting newspaper3k issue its own request."""
    try:
        article = Article(url)
        article.set_html(html)
        article.parse()
        return article.text or None, article.publish_date
    except Exception as exc:
        print(f"[fetcher] newspaper3k parse failed for {url!r}: {exc}")
        return None, None


def _parse_with_bs4(html: str) -> Tuple[Optional[str], Optional[datetime]]:
    """Fallback text and date extraction from already-safe HTML."""
    try:
        soup = BeautifulSoup(html, "lxml")
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
        body = "\n\n".join(paragraphs) or None
        return body, _extract_date_from_soup(soup)
    except Exception as exc:
        print(f"[fetcher] BeautifulSoup parse failed: {exc}")
        return None, None


def _extract_date_from_soup(soup: BeautifulSoup) -> Optional[datetime]:
    for attrs in _DATE_META_TAGS:
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            parsed = _parse_iso_date(tag["content"])
            if parsed:
                return parsed

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and item.get("datePublished"):
                parsed = _parse_iso_date(item["datePublished"])
                if parsed:
                    return parsed

    time_tag = soup.find("time", attrs={"datetime": True})
    return _parse_iso_date(time_tag["datetime"]) if time_tag else None


def _claim_terms(claim: str) -> set[str]:
    return {
        token.lower()
        for token in _WORD_RE.findall(claim or "")
        if len(token) >= 3 and token.lower() not in _COMMON_CLAIM_WORDS
    }


def _proper_claim_terms(claim: str) -> set[str]:
    """Prefer named entities such as people, places, teams, and organizations."""
    return {
        match.group(0).lower()
        for match in re.finditer(r"\b[A-Z][a-z]{2,}\b", claim or "")
    }


def _split_into_chunks(text: str) -> List[str]:
    chunks: List[str] = []
    start = 0
    text = text.strip()

    while start < len(text):
        end = min(start + EXCERPT_CHUNK_SIZE, len(text))
        if end < len(text):
            minimum_break = start + EXCERPT_CHUNK_SIZE // 2
            candidates = (
                text.rfind("\n", minimum_break, end),
                text.rfind(". ", minimum_break, end),
                text.rfind(" ", minimum_break, end),
            )
            boundary = max(candidates)
            if boundary > start:
                end = boundary + (1 if text[boundary:boundary + 2] == ". " else 0)

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - EXCERPT_CHUNK_OVERLAP, start + 1)

    return chunks


def _select_relevant_excerpt(body: str, claim: str) -> str:
    """Keep relevant article regions within the fixed LLM evidence budget."""
    body = body[:MAX_ARTICLE_TEXT_LENGTH].strip()
    if len(body) <= MAX_BODY_LENGTH:
        return body

    chunks = _split_into_chunks(body)
    terms = _claim_terms(claim)
    proper_terms = _proper_claim_terms(claim)
    if not chunks:
        return body[:MAX_BODY_LENGTH]

    def score(chunk: str) -> int:
        lowered = chunk.lower()
        return sum(min(lowered.count(term), 3) for term in terms)

    def proper_score(chunk: str) -> int:
        lowered = chunk.lower()
        return sum(min(lowered.count(term), 3) for term in proper_terms)

    ranked = sorted(
        range(len(chunks)),
        key=lambda index: (
            -proper_score(chunks[index]),
            -score(chunks[index]),
            index,
        ),
    )
    selected = [index for index in ranked[:MAX_RELEVANT_EXCERPTS] if score(chunks[index]) > 0]
    if not selected:
        selected = [0]

    excerpts = [chunks[index] for index in sorted(selected)]
    return "\n\n[...]\n\n".join(excerpts)[:MAX_BODY_LENGTH]


def _fetch_article(url: str, claim: str = "") -> Tuple[Optional[str], Optional[datetime]]:
    """Fetch one safe article and reduce it to claim-relevant evidence."""
    html, final_url = _safe_fetch_html(url)
    if not html or not final_url:
        return None, None

    body, publish_date = _parse_with_newspaper(final_url, html)
    if not body or len(body) < MIN_BODY_LENGTH:
        body, fallback_date = _parse_with_bs4(html)
        if publish_date is None:
            publish_date = fallback_date

    if not body or len(body) < MIN_BODY_LENGTH:
        return None, None
    if publish_date is None:
        try:
            publish_date = _extract_date_from_soup(BeautifulSoup(html, "lxml"))
        except Exception as exc:
            print(f"[fetcher] date parse failed: {exc}")
    return _select_relevant_excerpt(body, claim), publish_date


def fetch_all(results: List[ScoredResult], claim: str = "") -> List[FetchedArticle]:
    """Fetch up to ten sources concurrently and preserve search-result order."""
    if not results:
        return []

    selected = results[:MAX_ARTICLES]
    with ThreadPoolExecutor(max_workers=min(len(selected), MAX_WORKERS)) as pool:
        fetched = list(pool.map(lambda result: _fetch_article(result.url, claim), selected))

    output = []
    for result, (body, publish_date) in zip(selected, fetched):
        if body is None:
            print(f"[fetcher] skipping {result.domain} — body too short, failed, or unsafe")
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
