"""Step 4: Serper.dev search.

API key in env var SERPER_API_KEY.
"""
import os
from typing import List
from urllib.parse import urlparse

import requests

from ..schema import SearchResult

_API_KEY = os.getenv("SERPER_API_KEY")
_REQUEST_TIMEOUT_SECONDS = 6


def _domain(url: str) -> str:
    return urlparse(url or "").netloc.removeprefix("www.")


def search(query: str, top_k: int = 20) -> List[SearchResult]:
    if not _API_KEY:
        print("[searcher] no search API key found; set SERPER_API_KEY")
        return []

    try:
        response = requests.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": _API_KEY,
                "Content-Type": "application/json",
            },
            json={"q": query, "num": min(max(top_k, 1), 20)},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        results = []
        for item in response.json().get("organic", []):
            link = item.get("link", "")
            results.append(SearchResult(
                url=link,
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                domain=_domain(link),
            ))
        return results
    except Exception as e:
        print(f"[searcher] Serper search failed: {e}")
        return []
