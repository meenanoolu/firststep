"""Tiny in-memory sliding-window limiter, keyed by anything (client IP, learner id). Resets on restart, which is fine
for a single-instance deploy; it exists to stop one client from hogging the code runner or guessing unlock codes."""
from __future__ import annotations

import time
from collections import deque


class Limiter:
    def __init__(self):
        self.hits: dict[str, deque] = {}

    def _prune(self, key: str, window_s: float, now: float) -> deque:
        q = self.hits.setdefault(key, deque())
        while q and now - q[0] > window_s:
            q.popleft()
        if not q:
            self.hits.pop(key, None)
            q = self.hits.setdefault(key, deque())
        return q

    def blocked(self, key: str, limit: int, window_s: float, now: float | None = None) -> bool:
        return len(self._prune(key, window_s, time.time() if now is None else now)) >= limit

    def record(self, key: str, window_s: float = 86400, now: float | None = None) -> None:
        now = time.time() if now is None else now
        self._prune(key, window_s, now).append(now)


def client_ip(request) -> str:
    """Behind Render's proxy the LAST X-Forwarded-For entry is the address the proxy saw; earlier ones can be spoofed."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"
