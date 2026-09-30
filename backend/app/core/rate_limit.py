from collections import OrderedDict, deque
from hashlib import sha256
from ipaddress import ip_address
from secrets import token_hex
from threading import Lock
from time import monotonic

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import ApiError


class InMemoryRateLimiter:
    """Bounded per-process rate state for the single-instance portfolio service."""

    def __init__(self, *, max_keys: int = 8_192) -> None:
        self._events: OrderedDict[str, deque[tuple[str, float]]] = OrderedDict()
        self._lock = Lock()
        self._max_keys = max_keys

    def reserve(self, key: str, limit: int, window_seconds: int) -> tuple[str | None, int | None]:
        """Atomically check the window and reserve an attempt while it is in flight."""
        now = monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events.get(key)
            if events is None:
                self._make_room()
                events = deque()
                self._events[key] = events
            self._prune(key, events, cutoff)
            if not events:
                events = deque()
                self._events[key] = events
            if len(events) >= limit:
                return None, max(1, int(events[0][1] + window_seconds - now + 0.999))
            token = token_hex(8)
            events.append((token, now))
            self._events.move_to_end(key)
            return token, None

    def record(self, key: str, window_seconds: int) -> str:
        now = monotonic()
        with self._lock:
            events = self._events.get(key)
            if events is None:
                self._make_room()
                events = deque()
                self._events[key] = events
            self._prune(key, events, now - window_seconds)
            if not events:
                events = deque()
                self._events[key] = events
            token = token_hex(8)
            events.append((token, now))
            self._events.move_to_end(key)
            return token

    def release(self, key: str, token: str | None) -> None:
        if token is None:
            return
        with self._lock:
            events = self._events.get(key)
            if events is not None:
                self._events[key] = deque(event for event in events if event[0] != token)
                if not self._events[key]:
                    del self._events[key]

    def clear(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

    def clear_all(self) -> None:
        with self._lock:
            self._events.clear()

    def _make_room(self) -> None:
        while len(self._events) >= self._max_keys:
            self._events.popitem(last=False)

    def _prune(self, key: str, events: deque[tuple[str, float]], cutoff: float) -> None:
        while events and events[0][1] <= cutoff:
            events.popleft()
        if not events:
            self._events.pop(key, None)


rate_limiter = InMemoryRateLimiter()


def client_ip(request: Request) -> str:
    """Use Render's edge-owned client address; never trust caller-supplied X-Forwarded-For."""
    if get_settings().trust_render_edge_ip:
        forwarded = request.headers.get("cf-connecting-ip", "")
        try:
            return str(ip_address(forwarded))
        except ValueError:
            pass
    return request.client.host if request.client is not None else "unknown"


def identity_key(email: str) -> str:
    return sha256(email.strip().casefold().encode("utf-8")).hexdigest()


def reserve_rate_limit_event(key: str, limit: int, window_seconds: int) -> str | None:
    if not get_settings().rate_limit_enabled:
        return None
    token, retry_after = rate_limiter.reserve(key, limit, window_seconds)
    if retry_after is not None:
        raise ApiError(
            429,
            "RATE_LIMITED",
            "Too many requests. Please wait before trying again.",
            headers={"Retry-After": str(retry_after)},
        )
    return token


def consume_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    reserve_rate_limit_event(key, limit, window_seconds)


def release_rate_limit_event(key: str, token: str | None) -> None:
    rate_limiter.release(key, token)
