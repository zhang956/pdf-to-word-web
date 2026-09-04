import time
from collections import deque
from threading import Lock

from fastapi import Request


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: int, max_buckets: int = 10_000):
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_buckets = max_buckets
        self._events: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str, now: float | None = None) -> bool:
        timestamp = time.monotonic() if now is None else now
        cutoff = timestamp - self.window_seconds
        with self._lock:
            for stale_key in [
                bucket_key
                for bucket_key, bucket in self._events.items()
                if not bucket or bucket[-1] <= cutoff
            ]:
                del self._events[stale_key]
            if key not in self._events and len(self._events) >= self.max_buckets:
                oldest_key = min(
                    self._events,
                    key=lambda bucket_key: self._events[bucket_key][-1],
                )
                del self._events[oldest_key]
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(timestamp)
            return True


def client_ip(request: Request, trust_render_proxy: bool = False) -> str:
    if trust_render_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.rsplit(",", 1)[-1].strip()
    return request.client.host if request.client else "unknown"
