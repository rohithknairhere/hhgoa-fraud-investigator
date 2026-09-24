"""A tiny in-memory property graph used by the mock provider and CSV export.

It mirrors the vertex/edge types declared in tigergraph/schema.gsql so the mock
provider and the live TigerGraph queries answer the same questions over the
same shape of data.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

VERTEX_TYPES = ("Transaction", "Card", "Device", "Customer", "IP", "Case")

# edge type -> (from vertex type, to vertex type); all edges are undirected.
EDGE_TYPES: dict[str, tuple[str, str]] = {
    "PAID_WITH": ("Transaction", "Card"),
    "USED_DEVICE": ("Transaction", "Device"),
    "FROM_IP": ("Transaction", "IP"),
    "PLACED_BY": ("Transaction", "Customer"),
    "HOLDS": ("Customer", "Card"),
    "USES_DEVICE": ("Customer", "Device"),
    "USES_IP": ("Customer", "IP"),
    "INVESTIGATES": ("Case", "Transaction"),
    "CONCERNS": ("Case", "Customer"),
}


class GraphStore:
    def __init__(self) -> None:
        self.vertices: dict[str, dict[str, Any]] = {}
        self._adj: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self._edge_set: set[tuple[str, str, str]] = set()

    # -- mutation ---------------------------------------------------------
    def add_vertex(self, vtype: str, vid: str, **attrs: Any) -> str:
        if vtype not in VERTEX_TYPES:
            raise ValueError(f"unknown vertex type {vtype}")
        existing = self.vertices.get(vid)
        if existing is None:
            self.vertices[vid] = {"id": vid, "type": vtype, **attrs}
        else:
            existing.update(attrs)
        return vid

    def add_edge(self, etype: str, a: str, b: str) -> None:
        src_t, dst_t = EDGE_TYPES[etype]
        if self.vertices[a]["type"] != src_t or self.vertices[b]["type"] != dst_t:
            raise ValueError(f"{etype} expects {src_t}->{dst_t}, got {a}->{b}")
        key = (etype, a, b)
        if key in self._edge_set:
            return
        self._edge_set.add(key)
        self._adj[a].append((etype, b))
        self._adj[b].append((etype, a))

    # -- reads ------------------------------------------------------------
    def get(self, vid: str) -> dict[str, Any] | None:
        return self.vertices.get(vid)

    def neighbors(self, vid: str, vtype: str | None = None, etype: str | None = None) -> list[str]:
        out = []
        for et, other in self._adj.get(vid, []):
            if etype and et != etype:
                continue
            if vtype and self.vertices[other]["type"] != vtype:
                continue
            out.append(other)
        return out

    def of_type(self, vtype: str) -> Iterable[dict[str, Any]]:
        return (v for v in self.vertices.values() if v["type"] == vtype)

    def edges(self) -> Iterable[tuple[str, str, str]]:
        return iter(sorted(self._edge_set))

    def bfs(self, root: str, hops: int) -> dict[str, int]:
        """Return {vertex_id: hop_distance} for every vertex within `hops`."""
        seen = {root: 0}
        frontier = [root]
        for depth in range(1, hops + 1):
            nxt = []
            for vid in frontier:
                for _, other in self._adj.get(vid, []):
                    if other not in seen:
                        seen[other] = depth
                        nxt.append(other)
            frontier = nxt
        return seen
