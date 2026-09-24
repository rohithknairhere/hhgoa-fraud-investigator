"""Choose the graph backend: live TigerGraph when reachable, deterministic mock otherwise."""

from __future__ import annotations

import logging
import socket
from urllib.parse import urlparse

from app.config import Settings, get_settings
from app.graph.base import GraphProvider
from app.graph.mock_provider import MockGraphProvider

log = logging.getLogger(__name__)


def _reachable(host: str, timeout: float) -> bool:
    parsed = urlparse(host if "://" in host else f"https://{host}")
    port = parsed.port or (443 if parsed.scheme == "https" else 14240)
    try:
        with socket.create_connection((parsed.hostname or "", port), timeout=timeout):
            return True
    except OSError:
        return False


def create_provider(settings: Settings | None = None) -> GraphProvider:
    settings = settings or get_settings()
    if settings.graph_backend == "mock" or (settings.graph_backend == "auto" and not settings.tg_host):
        return MockGraphProvider()
    if not _reachable(settings.tg_host, settings.tg_connect_timeout_s):
        if settings.graph_backend == "tigergraph":
            raise RuntimeError(f"TigerGraph at {settings.tg_host} is unreachable")
        log.warning("TigerGraph unreachable; injecting deterministic mock provider")
        return MockGraphProvider()
    try:
        from app.graph.tigergraph_provider import TigerGraphProvider

        provider = TigerGraphProvider(settings)
        provider.ping()
        return provider
    except Exception as exc:  # auth errors, missing graph, etc.
        if settings.graph_backend == "tigergraph":
            raise
        log.warning("TigerGraph connection failed (%s); injecting deterministic mock provider", exc)
        return MockGraphProvider()
