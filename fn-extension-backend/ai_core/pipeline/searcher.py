"""Step 4: Serper.dev search.

API key in env var SERPER_API_KEY.
"""
import os
from typing import List
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

from ..schema import SearchResult

load_dotenv()
_API_KEY = os.getenv("SERPER_API_KEY")


def _domain(url: str) -> str:
    return urlparse(url or "").netloc.removeprefix("www.")


def search(query: str, top_k: int = 10) -> List[SearchResult]:
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
            json={"q": query, "num": top_k},
            timeout=10,
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
