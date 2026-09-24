"""Simulated out-of-band evidence (customer step-up results, analyst findings).

In production these arrive asynchronously from the auth service and the case
management UI; for the benchmark each scenario scripts what would come back
for each kind of request. Unscripted requests return nothing, which is itself
information the agent must handle.
"""

from __future__ import annotations

from typing import Any, Protocol


class EvidenceOracle(Protocol):
    def request(self, request_type: str) -> list[dict[str, Any]]: ...


class ScriptedEvidenceOracle:
    def __init__(self, followups: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.followups = followups or {}
        self.served: list[str] = []

    def request(self, request_type: str) -> list[dict[str, Any]]:
        self.served.append(request_type)
        return [dict(item) for item in self.followups.get(request_type, [])]
