"""Step 3: Serper API search.

Free tier: 2,500 queries. API key in env var SERPER_API_KEY.
"""

from typing import List

from ..schema import SearchResult


def search(query: str, top_k: int = 10) -> List[SearchResult]:
    """Hit Serper with `query`, return up to `top_k` results.

    TODO: POST https://google.serper.dev/search with header X-API-KEY,
    body {"q": query, "num": top_k}. Map response['organic'] to SearchResult.
    Extract domain from each url (urllib.parse.urlparse(url).netloc, strip leading 'www.').
    """
    raise NotImplementedError
