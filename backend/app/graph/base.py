"""Graph provider contract shared by the live TigerGraph client and the mock."""

from __future__ import annotations

from typing import Any, Protocol

NEAR_THRESHOLD_LOW = 9_000.0
NEAR_THRESHOLD_HIGH = 10_000.0


class GraphProvider(Protocol):
    name: str

    def get_case(self, case_id: str) -> dict[str, Any]: ...

    def get_transaction_context(self, txn_id: str) -> dict[str, Any]: ...

    def get_customer_history(self, customer_id: str, as_of_ts: int | None = None,
                             lookback_days: int = 365) -> dict[str, Any]: ...

    def find_related_entities(self, entity_id: str, hops: int = 2, as_of_ts: int | None = None,
                              limit: int = 50) -> dict[str, Any]: ...

    def find_similar_cases(self, txn_id: str, pattern_tags: list[str], k: int = 5) -> dict[str, Any]: ...

    def detect_device_sharing(self, min_cards: int = 3) -> list[dict[str, Any]]: ...

    def detect_velocity_burst(self, window_seconds: int = 3600, min_txns: int = 6) -> list[dict[str, Any]]: ...

    def update_case_memory(self, case_id: str, memory: dict[str, Any]) -> dict[str, Any]: ...


class GraphProviderError(RuntimeError):
    pass
