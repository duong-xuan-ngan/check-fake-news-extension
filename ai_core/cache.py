"""Disk-backed result cache for the fake news detection pipeline.

Key design decisions:
  - Cache key: SHA-256 of the lowercased, stripped english_claim.
  - Storage: data/cache.json — flat JSON dict, sits next to mbfc_credibility.json.
  - TTL: 24 hours. Stale entries are ignored on read and pruned on write.
  - Structure per entry:
        {
            "<sha256_hex>": {
                "stored_at": "<ISO 8601 UTC datetime>",
                "result":    { ...AnalysisResult JSON... }
            }
        }
  - Thread safety: not guaranteed. Acceptable for a single-process extension
    backend. If the backend becomes multi-process, wrap writes in a file lock.

Public API (the only two functions analyze() needs):
    get(english_claim: str) -> Optional[AnalysisResult]
    set(english_claim: str, result: AnalysisResult) -> None
"""
import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from .schema import AnalysisResult

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_TTL_HOURS = 24
_CACHE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cache.json"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cache_key(english_claim: str) -> str:
    """Stable, case-insensitive SHA-256 key for a claim string."""
    normalized = english_claim.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _load() -> dict:
    """Read the cache file. Returns an empty dict if missing or corrupt."""
    if not _CACHE_PATH.exists():
        return {}
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[cache] Failed to load cache file, starting fresh: {e}")
        return {}


def _save(data: dict) -> None:
    """Write the cache dict to disk. Silently logs on failure — never crashes."""
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except OSError as e:
        print(f"[cache] Failed to write cache file: {e}")


def _is_expired(stored_at_iso: str) -> bool:
    """Return True if the entry is older than TTL_HOURS."""
    try:
        stored_at = datetime.fromisoformat(stored_at_iso)
        # Ensure timezone-aware comparison
        if stored_at.tzinfo is None:
            stored_at = stored_at.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - stored_at
        return age > timedelta(hours=_TTL_HOURS)
    except (ValueError, TypeError):
        # Unparseable timestamp → treat as expired
        return True


def _prune(data: dict) -> dict:
    """Remove all expired entries. Called on every write to keep the file lean."""
    return {k: v for k, v in data.items() if not _is_expired(v.get("stored_at", ""))}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get(english_claim: str) -> Optional[AnalysisResult]:
    """Look up a cached result for this claim.

    Returns the AnalysisResult with cached=True if found and fresh.
    Returns None on miss, expiry, or any deserialization error.
    """
    key = _cache_key(english_claim)
    data = _load()
    entry = data.get(key)

    if entry is None:
        return None

    if _is_expired(entry.get("stored_at", "")):
        print(f"[cache] Miss (expired) for key {key[:8]}...")
        return None

    try:
        result = AnalysisResult(**entry["result"])
        result.cached = True
        print(f"[cache] Hit for key {key[:8]}...")
        return result
    except Exception as e:
        print(f"[cache] Failed to deserialize entry: {e}")
        return None


def set(english_claim: str, result: AnalysisResult) -> None:
    """Store a result under this claim's cache key.

    Prunes expired entries on every write so the file doesn't grow unbounded.
    Does not store results that are themselves cache hits — no re-caching.
    """
    if result.cached:
        # Already came from cache — don't re-write, don't update stored_at
        return

    key = _cache_key(english_claim)
    data = _prune(_load())

    data[key] = {
        "stored_at": datetime.now(timezone.utc).isoformat(),
        "result": json.loads(result.model_dump_json()),
    }

    _save(data)
    print(f"[cache] Stored result for key {key[:8]}...")
