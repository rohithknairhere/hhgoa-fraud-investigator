"""HTTP hardening middleware: HTTPS enforcement, rate limiting, security headers."""

from __future__ import annotations

import ipaddress
import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

LOOPBACK_HOSTS = {"testclient", "localhost"}


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    if host in LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class HTTPSEnforcementMiddleware(BaseHTTPMiddleware):
    """Reject plaintext HTTP.

    The effective scheme is the socket scheme, or X-Forwarded-Proto when the
    peer is a trusted reverse proxy (TLS terminated upstream). Loopback clients
    may be exempted for local development via ALLOW_LOCAL_HTTP.
    """

    def __init__(self, app: ASGIApp, enabled: bool, allow_local_http: bool,
                 trusted_proxies: set[str] | None = None) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.allow_local_http = allow_local_http
        self.trusted_proxies = trusted_proxies or {"127.0.0.1", "::1"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self.enabled:
            peer = request.client.host if request.client else None
            scheme = request.url.scheme
            forwarded = request.headers.get("x-forwarded-proto")
            if forwarded and peer in self.trusted_proxies:
                scheme = forwarded.split(",")[0].strip().lower()
            if scheme != "https" and not (self.allow_local_http and _is_loopback(peer) and not forwarded):
                return JSONResponse(
                    {"detail": "HTTPS is required. Retry this request over https://."},
                    status_code=403,
                    headers={"Upgrade": "TLS/1.2, HTTP/1.1", "Connection": "Upgrade"},
                )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window limiter per client IP; writes have a tighter budget than reads."""

    WINDOW_S = 60.0

    def __init__(self, app: ASGIApp, read_per_minute: int, write_per_minute: int) -> None:
        super().__init__(app)
        self.limits = {"read": read_per_minute, "write": write_per_minute}
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        kind = "read" if request.method in {"GET", "HEAD", "OPTIONS"} else "write"
        client = request.client.host if request.client else "unknown"
        limit = self.limits[kind]
        now = time.monotonic()
        with self._lock:
            hits = self._hits[(client, kind)]
            while hits and now - hits[0] > self.WINDOW_S:
                hits.popleft()
            if len(hits) >= limit:
                retry = max(1, int(self.WINDOW_S - (now - hits[0])) + 1)
                return JSONResponse({"detail": "Rate limit exceeded. Slow down."}, status_code=429,
                                    headers={"Retry-After": str(retry), "X-RateLimit-Limit": str(limit),
                                             "X-RateLimit-Remaining": "0"})
            hits.append(now)
            remaining = limit - len(hits)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Cache-Control"] = "no-store"
        return response
