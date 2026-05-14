"""Step 6: fetch article body from credible sources.

Primary: Newspaper3k (built for news, handles most cases).
Fallback: requests + BeautifulSoup when Newspaper3k fails.
JS-heavy sites (Playwright/Selenium) are explicitly v2.
"""

from typing import List

from ..schema import Source


def fetch(source: Source, timeout_s: float = 5.0) -> Source:
    """Populate `source.fetched_text` in place (or return a copy with it set).

    TODO: try Newspaper3k Article(url).download().parse(); on failure or empty
    body, fall back to requests.get + BeautifulSoup main-content extraction.
    Return source unchanged if both fail (caller decides what to do).
    """
    raise NotImplementedError


def fetch_all(sources: List[Source]) -> List[Source]:
    """Fetch every source. v1 = sequential; v2 = async/concurrent."""
    return [fetch(s) for s in sources]
