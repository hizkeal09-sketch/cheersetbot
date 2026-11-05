"""Reusable UI helpers: rate limiting and anti-spam primitives."""

from __future__ import annotations

import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    """In-process per-user sliding-window limiter.

    Adequate for a single bot process. For multi-worker deployments use a
    shared store (Redis) instead; see README.
    """

    def __init__(self, max_events: int, window_seconds: float) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: dict[int, deque[float]] = defaultdict(deque)
        self._calls = 0

    def is_allowed(self, user_id: int) -> bool:
        now = time.monotonic()
        bucket = self._events[user_id]
        cutoff = now - self.window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= self.max_events:
            return False
        bucket.append(now)
        self._calls += 1
        if self._calls % 500 == 0:
            self._cleanup(cutoff)
        return True

    def _cleanup(self, cutoff: float) -> None:
        stale = [key for key, bucket in self._events.items() if not bucket or bucket[-1] <= cutoff]
        for key in stale:
            self._events.pop(key, None)
