"""Step 4: Serper API search.

Free tier: 2,500 queries. API key in env var SERPER_API_KEY.
"""
import os
import requests
from urllib.parse import urlparse
from typing import List
from dotenv import load_dotenv

from ..schema import SearchResult

load_dotenv()
_API_KEY = os.getenv("SERPER_API_KEY")


def search(query: str, top_k: int = 10) -> List[SearchResult]:
    try:
        response = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": _API_KEY},
            json={"q": query, "num": top_k},
        )
        results = []
        for item in response.json().get("organic", []):
            domain = urlparse(item.get("link", "")).netloc.removeprefix("www.")
            results.append(SearchResult(
                url=item.get("link", ""),
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                domain=domain,
            ))
        return results
    except Exception as e:
        print(f"[searcher] search failed: {e}")
        return []
