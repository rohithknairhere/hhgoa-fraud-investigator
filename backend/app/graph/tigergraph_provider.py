"""Live TigerGraph provider (pyTigerGraph → installed GSQL queries).

Every method maps 1:1 to an installed query in tigergraph/queries/. The agent
never sends raw GSQL: queries are installed ahead of time and invoked by name
with typed parameters. Results are normalised to the same shapes the mock
provider returns.
"""

from __future__ import annotations

import json
import time
from typing import Any

from app.config import Settings
from app.data.scenarios import DAY
from app.graph.base import GraphProviderError

# GSQL reserves CASE, so the Case vertex is stored as FraudCase.
TYPE_TO_GSQL = {"Case": "FraudCase"}
GSQL_TO_TYPE = {v: k for k, v in TYPE_TO_GSQL.items()}
ID_PREFIX_TYPES = (("CARD-", "Card"), ("DEV-", "Device"), ("CUST-", "Customer"), ("IP-", "IP"),
                   ("CASE-", "FraudCase"), ("HHGOA-", "FraudCase"), ("T", "Transaction"))
CONTEXT_STATS = ("device_distinct_cards", "device_distinct_customers", "device_cards", "ip_distinct_cards",
                 "ip_distinct_customers", "ip_cards_1h", "card_txn_count_1h", "card_amount_1h",
                 "card_countries_1h", "customer_txn_count_24h", "customer_amount_24h",
                 "near_threshold_count_24h", "fraud_labeled_neighbor_txns")


def _first(result: list[dict[str, Any]], key: str, default: Any = None) -> Any:
    for row in result or []:
        if key in row:
            return row[key]
    return default


def gsql_type_for(vertex_id: str) -> str:
    for prefix, vtype in ID_PREFIX_TYPES:
        if vertex_id.startswith(prefix):
            return vtype
    raise GraphProviderError(f"cannot infer vertex type for id '{vertex_id}'")


def normalise_vertex(v: dict[str, Any] | None) -> dict[str, Any] | None:
    if not v:
        return None
    attrs = {k: val for k, val in (v.get("attributes") or {}).items() if not k.startswith("@")}
    vtype = GSQL_TO_TYPE.get(v.get("v_type", ""), v.get("v_type"))
    for key in ("txn_id", "card_id", "device_id", "customer_id", "ip_id", "case_id"):
        attrs.pop(key, None)
    return {"id": v.get("v_id"), "type": vtype, **attrs}


class TigerGraphProvider:
    name = "tigergraph"

    def __init__(self, settings: Settings) -> None:
        from pyTigerGraph import TigerGraphConnection  # imported lazily: optional at runtime

        self.settings = settings
        self.conn = TigerGraphConnection(
            host=settings.tg_host,
            graphname=settings.tg_graph,
            username=settings.tg_username,
            password=settings.tg_password,
        )
        if settings.tg_secret:
            self.conn.getToken(settings.tg_secret)

    def ping(self) -> None:
        self.conn.echo()

    def _run(self, query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            return self.conn.runInstalledQuery(query, params=params, timeout=15_000)
        except Exception as exc:  # pyTigerGraph raises a variety of exception types
            raise GraphProviderError(f"TigerGraph query {query} failed: {exc}") from exc

    def _one(self, res: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
        rows = _first(res, key) or []
        return normalise_vertex(rows[0]) if rows else None

    def get_case(self, case_id: str) -> dict[str, Any]:
        res = self._run("get_case", {"case_id": case_id})
        case = self._one(res, "fraud_case")
        if case is None:
            raise GraphProviderError(f"Case '{case_id}' not found")
        return {"case": case, "transaction_ids": sorted(_first(res, "transaction_ids", [])),
                "customer_id": _first(res, "customer_id")}

    def get_transaction_context(self, txn_id: str) -> dict[str, Any]:
        res = self._run("get_transaction_context", {"txn": txn_id})
        txn = self._one(res, "transaction")
        if txn is None:
            raise GraphProviderError(f"Transaction '{txn_id}' not found")
        stats = {k: _first(res, k) for k in CONTEXT_STATS}
        for k in ("device_cards", "card_countries_1h", "fraud_labeled_neighbor_txns"):
            stats[k] = sorted(stats[k] or [])
        return {"transaction": txn, "card": self._one(res, "card"), "device": self._one(res, "device"),
                "ip": self._one(res, "ip"), "customer": self._one(res, "customer"), "stats": stats}

    def get_customer_history(self, customer_id: str, as_of_ts: int | None = None,
                             lookback_days: int = 365) -> dict[str, Any]:
        as_of = as_of_ts or int(time.time())
        res = self._run("get_customer_history", {"customer_id": customer_id, "as_of_ts": as_of,
                                                 "lookback_days": lookback_days})
        n = _first(res, "txn_count", 0)
        last_ts = _first(res, "last_ts")
        return {
            "customer": self._one(res, "customer"),
            "cards": sorted(_first(res, "cards", [])),
            "txn_count": n,
            "avg_amount": round(_first(res, "total_amount", 0) / n, 2) if n else None,
            "max_amount": _first(res, "max_amount") if n else None,
            "chargeback_count": _first(res, "chargeback_count", 0),
            "known_device_ids": sorted(_first(res, "known_device_ids", [])),
            "known_ip_countries": sorted(_first(res, "known_ip_countries", [])),
            "days_since_last_txn": round((as_of - last_ts) / DAY, 1) if (n and last_ts is not None) else None,
            "prior_cases": _first(res, "prior_cases", []),
        }

    def find_related_entities(self, entity_id: str, hops: int = 2, as_of_ts: int | None = None,
                              limit: int = 50) -> dict[str, Any]:
        res = self._run("find_related_entities", {
            "root_id": entity_id, "root_id.type": gsql_type_for(entity_id), "hops": max(1, min(hops, 3)),
            "as_of_ts": as_of_ts or 2**62, "max_rows": limit})
        entities = []
        for v in _first(res, "entities", []):
            entities.append({**normalise_vertex(v), "hops": (v.get("attributes") or {}).get("@hop")})
        counts = {GSQL_TO_TYPE.get(k, k): c for k, c in (_first(res, "counts", {}) or {}).items()}
        return {
            "root": self._one(res, "root"),
            "hops": hops,
            "counts": dict(sorted(counts.items())),
            "fraud_transactions": sorted(_first(res, "fraud_transactions", [])),
            "confirmed_fraud_cases": sorted(_first(res, "confirmed_fraud_cases", [])),
            "entities": entities,
        }

    def find_similar_cases(self, txn_id: str, pattern_tags: list[str], k: int = 5) -> dict[str, Any]:
        res = self._run("find_similar_cases", {"txn": txn_id, "tags": pattern_tags, "k": k})
        cases = []
        for v in _first(res, "cases", []):
            attrs = v.get("attributes") or {}
            cases.append({
                "case_id": v["v_id"], "similarity": round(attrs.get("similarity", 0.0), 3),
                "pattern_tags": sorted(attrs.get("pattern_tags", [])), "outcome": attrs.get("outcome"),
                "decision": attrs.get("decision", ""), "summary": attrs.get("summary", ""),
                "shared_entities": sorted(attrs.get("shared_entities", [])),
            })
        return {"query_tags": sorted(pattern_tags), "cases": cases}

    def detect_device_sharing(self, min_cards: int = 3) -> list[dict[str, Any]]:
        return _first(self._run("detect_device_sharing", {"min_cards": min_cards}), "devices", [])

    def detect_velocity_burst(self, window_seconds: int = 3600, min_txns: int = 6) -> list[dict[str, Any]]:
        bursts = _first(self._run("detect_velocity_burst",
                                  {"window_seconds": window_seconds, "min_txns": min_txns}), "bursts", {})
        rows = list(bursts.values()) if isinstance(bursts, dict) else list(bursts)
        return sorted(rows, key=lambda r: (-r["txn_count"], r["card_id"]))

    def update_case_memory(self, case_id: str, memory: dict[str, Any]) -> dict[str, Any]:
        attrs: dict[str, Any] = {k: v for k, v in memory.items() if k in {
            "status", "outcome", "decision", "confidence", "summary", "sar_filed", "closed_ts"}}
        attrs["pattern_tags"] = list(memory.get("pattern_tags", []))
        attrs["evidence_ids"] = json.dumps(memory.get("evidence_ids", []))
        try:
            self.conn.upsertVertex("FraudCase", case_id, attrs)
        except Exception as exc:
            raise GraphProviderError(f"case memory upsert failed: {exc}") from exc
        return {"case_id": case_id, "written": sorted(attrs), "backend": self.name}
