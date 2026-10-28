"""Small pure-ASGI middleware for the API: security headers, body size limit, rate limit.

Plain ASGI classes are used (not BaseHTTPMiddleware) so streaming and errors behave predictably.
Errors use the same shape as the rest of the API: {"detail": ["message", ...]}.
"""
import json
import math
import threading
import time
from collections import deque
from typing import Callable, Iterable, Mapping, Optional

from starlette.datastructures import Headers, MutableHeaders

# The API only returns JSON, CSV and plain text, so no resource is ever loaded from it.
API_CSP = "default-src 'none'; frame-ancestors 'none'"
STATIC_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
# Multipart framing around an uploaded file (boundaries, headers), far below 64 KB
_MULTIPART_OVERHEAD = 64 * 1024


async def send_error(send, status: int, message: str, extra_headers: Iterable = ()):
    body = json.dumps({"detail": [message]}).encode("utf-8")
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), *extra_headers]
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class SecurityHeadersMiddleware:
    """Adds browser security headers. Headers an endpoint already set are left alone."""

    def __init__(self, app, csp_skip_paths: Iterable = ()):
        self.app = app
        self.csp_skip_paths = frozenset(csp_skip_paths)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method, path = scope["method"], scope["path"]

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for key, value in STATIC_SECURITY_HEADERS.items():
                    headers.setdefault(key, value)
                if path not in self.csp_skip_paths:
                    headers.setdefault("Content-Security-Policy", API_CSP)
                if method == "POST":
                    headers.setdefault("Cache-Control", "no-store")
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodySizeLimitMiddleware:
    """Rejects request bodies over a limit with 413, before the body is parsed.

    Checks the Content-Length header first. For uploads without one (chunked), counts the bytes
    as they stream in and stops the request once the limit is crossed.
    """

    def __init__(self, app, default_limit: int, path_limits: Optional[Mapping] = None):
        self.app = app
        self.default_limit = default_limit
        self.path_limits = dict(path_limits or {})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in SAFE_METHODS:
            await self.app(scope, receive, send)
            return

        limit = self.path_limits.get(scope["path"], self.default_limit)
        message = f"Request body is larger than {_pretty_size(limit)}."
        if scope["path"] in self.path_limits:
            message = f"File is larger than {_pretty_size(limit - _MULTIPART_OVERHEAD)}."

        declared = Headers(scope=scope).get("content-length")
        if declared is not None:
            try:
                too_big = int(declared) > limit
            except ValueError:
                too_big = False  # a malformed header is the server's problem, not ours
            if too_big:
                await send_error(send, 413, message)
                return

        received = 0
        too_large = False
        started = False

        async def counting_receive():
            nonlocal received, too_large
            if too_large:
                return {"type": "http.disconnect"}
            event = await receive()
            if event["type"] == "http.request":
                received += len(event.get("body", b""))
                if received > limit:
                    too_large = True
                    return {"type": "http.disconnect"}
            return event

        async def guarded_send(event):
            nonlocal started
            if too_large:
                return  # whatever the app answers after we cut the body is replaced by the 413
            if event["type"] == "http.response.start":
                started = True
            await send(event)

        try:
            await self.app(scope, counting_receive, guarded_send)
        except Exception:
            if too_large and not started:
                await send_error(send, 413, message)
                return
            raise
        if too_large and not started:
            await send_error(send, 413, message)



def _pretty_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:g} MB"
    return f"{max(size // 1024, 1)} KB"


def multipart_limit(max_upload_bytes: int) -> int:
    """Body limit for the upload route: the file limit plus the multipart framing."""
    return max_upload_bytes + _MULTIPART_OVERHEAD


class RateLimitMiddleware:
    """Sliding-window limit per client address and route, kept in memory (one process).

    rules maps (method, path) to (limit, window_seconds). Any other route uses the default.
    Exempt paths (health checks) are never limited.
    """

    PRUNE_EVERY = 1000

    def __init__(self, app, rules: Mapping, exempt_paths: Iterable = ("/health",),
                 clock: Callable[[], float] = time.monotonic):
        self.app = app
        self.rules = dict(rules)
        self.default_rule = self.rules.pop(None)
        self.exempt_paths = frozenset(exempt_paths)
        self.clock = clock
        self._hits = {}  # (client, bucket) -> (deque of timestamps, window)
        self._lock = threading.Lock()
        self._calls = 0

    def _check(self, key, limit: int, window: float):
        """Return 0 if the request may pass, otherwise the seconds to wait."""
        now = self.clock()
        with self._lock:
            entry = self._hits.get(key)
            if entry is None:
                entry = self._hits[key] = (deque(), window)
            hits = entry[0]
            while hits and hits[0] <= now - window:
                hits.popleft()
            if len(hits) >= limit:
                return max(1, math.ceil(hits[0] + window - now))
            hits.append(now)
            self._calls += 1
            if self._calls % self.PRUNE_EVERY == 0:
                self._prune(now)
            return 0

    def _prune(self, now: float):
        stale = [k for k, (hits, window) in self._hits.items() if not hits or hits[-1] <= now - window]
        for key in stale:
            del self._hits[key]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        method, path = scope["method"], scope["path"]
        rule = self.rules.get((method, path))
        bucket = f"{method} {path}" if rule else "default"
        limit, window = rule or self.default_rule
        client = scope["client"][0] if scope.get("client") else "unknown"

        wait = self._check((client, bucket), limit, window)
        if wait:
            await send_error(send, 429, f"Too many requests. Try again in {wait} seconds.",
                             [(b"retry-after", str(wait).encode())])
            return
        await self.app(scope, receive, send)
