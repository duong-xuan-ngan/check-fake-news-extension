"""Small in-process rate limiter for the single-backend deployment.

The daily quota answers "how many analyses may this user run today?". This
module answers "how quickly may a user/IP send requests?" so a retry loop or
bot cannot burst expensive work into the backend.
"""
from __future__ import annotations

from collections import deque
from math import ceil
from threading import Lock
from time import monotonic
from typing import Callable

from fastapi import HTTPException, Request, status

from .config import get_settings


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window limiter.

    This is deliberately in-process because production currently has one
    backend container. If the service is scaled to multiple backend replicas,
    replace this store with Redis so every replica shares the same counters.
    """

    def __init__(self, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._events: dict[str, deque[float]] = {}
        self._lock = Lock()

    def hit(self, key: str, limit: int, window_seconds: int) -> int | None:
        """Record a request, returning retry-after seconds when it is blocked."""
        if limit < 1 or window_seconds < 1:
            return None

        now = self._clock()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= limit:
                return max(1, ceil(window_seconds - (now - events[0])))

            events.append(now)
            return None


_limiter = SlidingWindowRateLimiter()


def client_ip(request: Request) -> str:
    """Use Caddy's client IP only in production, where backend is private."""
    settings = get_settings()
    forwarded = request.headers.get("x-forwarded-for", "")
    if settings.environment == "production" and forwarded:
        return forwarded.split(",", 1)[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(bucket: str, subject: str, limit: int, window_seconds: int) -> None:
    retry_after = _limiter.hit(f"{bucket}:{subject}", limit, window_seconds)
    if retry_after is None:
        return

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "error": "rate_limit_exceeded",
            "retry_after_seconds": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


def limit_analyze(request: Request, user_id: str) -> None:
    settings = get_settings()
    enforce_rate_limit(
        "analyze-user",
        user_id,
        settings.analyze_rate_limit_per_minute,
        settings.rate_limit_window_seconds,
    )
    enforce_rate_limit(
        "analyze-ip",
        client_ip(request),
        settings.analyze_ip_rate_limit_per_minute,
        settings.rate_limit_window_seconds,
    )


def limit_auth(request: Request) -> None:
    settings = get_settings()
    enforce_rate_limit(
        "auth-ip",
        client_ip(request),
        settings.auth_rate_limit_per_minute,
        settings.rate_limit_window_seconds,
    )


def limit_public_read(request: Request) -> None:
    settings = get_settings()
    enforce_rate_limit(
        "public-read-ip",
        client_ip(request),
        settings.public_rate_limit_per_minute,
        settings.rate_limit_window_seconds,
    )
