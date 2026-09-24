"""Deterministic mock provider.

Implements the same semantics as the installed GSQL queries in
tigergraph/queries/*.gsql over an in-memory copy of the benchmark graph, so
the agent, tests and benchmarks run identically with or without a live
TigerGraph instance.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.data.scenarios import DAY, HOUR, build_dataset
from app.graph.base import NEAR_THRESHOLD_HIGH, NEAR_THRESHOLD_LOW, GraphProviderError
from app.graph.store import GraphStore


def _public(v: dict[str, Any]) -> dict[str, Any]:
    return dict(v)


class MockGraphProvider:
    name = "mock"

    def __init__(self, store: GraphStore | None = None) -> None:
        self.store = store or build_dataset().store

    # -- helpers ------------------------------------------------------------
    def _require(self, vid: str, vtype: str) -> dict[str, Any]:
        v = self.store.get(vid)
        if v is None or v["type"] != vtype:
            raise GraphProviderError(f"{vtype} '{vid}' not found")
        return v

    def _one(self, vid: str, vtype: str) -> dict[str, Any] | None:
        ids = self.store.neighbors(vid, vtype)
        return self.store.get(ids[0]) if ids else None

    def _txns(self, vid: str, as_of: int | None) -> list[dict[str, Any]]:
        out = [self.store.get(t) for t in self.store.neighbors(vid, "Transaction")]
        return [t for t in out if t and (as_of is None or t["ts"] <= as_of)]

    # -- queries ------------------------------------------------------------
    def get_case(self, case_id: str) -> dict[str, Any]:
        case = self._require(case_id, "Case")
        txns = sorted(self.store.neighbors(case_id, "Transaction"))
        customers = self.store.neighbors(case_id, "Customer")
        return {"case": _public(case), "transaction_ids": txns,
                "customer_id": customers[0] if customers else None}

    def get_transaction_context(self, txn_id: str) -> dict[str, Any]:
        txn = self._require(txn_id, "Transaction")
        ts = txn["ts"]
        card = self._one(txn_id, "Card")
        device = self._one(txn_id, "Device")
        ip = self._one(txn_id, "IP")
        customer = self._one(txn_id, "Customer")

        def distinct(vid: str, vtype: str, window: int | None = None) -> set[str]:
            found: set[str] = set()
            for t in self._txns(vid, ts):
                if window is not None and t["ts"] < ts - window:
                    continue
                found.update(self.store.neighbors(t["id"], vtype))
            return found

        card_1h = [t for t in self._txns(card["id"], ts) if t["ts"] >= ts - HOUR]
        countries_1h = sorted({
            self.store.get(i)["country"]
            for t in card_1h for i in self.store.neighbors(t["id"], "IP")
        })
        cust_24h = [t for t in self._txns(customer["id"], ts) if t["ts"] >= ts - DAY]
        near = [t for t in cust_24h if NEAR_THRESHOLD_LOW <= t["amount"] < NEAR_THRESHOLD_HIGH]

        neighbour_txns: dict[str, dict[str, Any]] = {}
        for hub in (card["id"], device["id"], ip["id"]):
            for t in self._txns(hub, ts):
                if t["id"] != txn_id:
                    neighbour_txns[t["id"]] = t
        fraud_ids = sorted(t["id"] for t in neighbour_txns.values() if t["is_fraud"] == 1)

        return {
            "transaction": _public(txn),
            "card": _public(card), "device": _public(device), "ip": _public(ip),
            "customer": _public(customer),
            "stats": {
                "device_distinct_cards": len(distinct(device["id"], "Card")),
                "device_distinct_customers": len(distinct(device["id"], "Customer")),
                "device_cards": sorted(distinct(device["id"], "Card")),
                "ip_distinct_cards": len(distinct(ip["id"], "Card")),
                "ip_distinct_customers": len(distinct(ip["id"], "Customer")),
                "ip_cards_1h": len(distinct(ip["id"], "Card", HOUR)),
                "card_txn_count_1h": len(card_1h),
                "card_amount_1h": round(sum(t["amount"] for t in card_1h), 2),
                "card_countries_1h": countries_1h,
                "customer_txn_count_24h": len(cust_24h),
                "customer_amount_24h": round(sum(t["amount"] for t in cust_24h), 2),
                "near_threshold_count_24h": len(near),
                "fraud_labeled_neighbor_txns": fraud_ids,
            },
        }

    def get_customer_history(self, customer_id: str, as_of_ts: int | None = None,
                             lookback_days: int = 365) -> dict[str, Any]:
        cust = self._require(customer_id, "Customer")
        txns = self._txns(customer_id, as_of_ts)
        if as_of_ts is not None:
            # Baseline excludes the 24h leading up to the alert so bursts don't mask themselves.
            txns = [t for t in txns if as_of_ts - lookback_days * DAY <= t["ts"] < as_of_ts - DAY]
        amounts = [t["amount"] for t in txns]
        devices: set[str] = set()
        countries: set[str] = set()
        for t in txns:
            devices.update(self.store.neighbors(t["id"], "Device"))
            countries.update(self.store.get(i)["country"] for i in self.store.neighbors(t["id"], "IP"))
        last_ts = max((t["ts"] for t in txns), default=None)
        prior_cases = []
        for cid in self.store.neighbors(customer_id, "Case"):
            c = self.store.get(cid)
            if c["status"] == "closed":
                prior_cases.append({"case_id": cid, "outcome": c["outcome"], "pattern_tags": c["pattern_tags"]})
        return {
            "customer": _public(cust),
            "cards": sorted(self.store.neighbors(customer_id, "Card")),
            "txn_count": len(txns),
            "avg_amount": round(sum(amounts) / len(amounts), 2) if amounts else None,
            "max_amount": max(amounts) if amounts else None,
            "chargeback_count": sum(1 for t in txns if t.get("chargeback")),
            "known_device_ids": sorted(devices),
            "known_ip_countries": sorted(countries),
            "days_since_last_txn": round((as_of_ts - last_ts) / DAY, 1) if (as_of_ts and last_ts) else None,
            "prior_cases": prior_cases,
        }

    def find_related_entities(self, entity_id: str, hops: int = 2, as_of_ts: int | None = None,
                              limit: int = 50) -> dict[str, Any]:
        root = self.store.get(entity_id)
        if root is None:
            raise GraphProviderError(f"entity '{entity_id}' not found")
        hops = max(1, min(hops, 3))
        seen = {entity_id: 0}
        frontier = [entity_id]
        for depth in range(1, hops + 1):
            nxt = []
            for vid in frontier:
                for other in self.store.neighbors(vid):
                    if other in seen:
                        continue
                    v = self.store.get(other)
                    if v["type"] == "Transaction" and as_of_ts is not None and v["ts"] > as_of_ts:
                        continue
                    if v["type"] == "Case" and v["status"] != "closed" and other != entity_id:
                        continue
                    seen[other] = depth
                    nxt.append(other)
            frontier = nxt
        seen.pop(entity_id)
        counts: dict[str, int] = defaultdict(int)
        fraud_txns, confirmed_cases = [], []
        for vid in seen:
            v = self.store.get(vid)
            counts[v["type"]] += 1
            if v["type"] == "Transaction" and v["is_fraud"] == 1:
                fraud_txns.append(vid)
            if v["type"] == "Case" and v["outcome"] == "confirmed_fraud":
                confirmed_cases.append(vid)
        ordered = sorted(seen.items(), key=lambda kv: (kv[1], self.store.get(kv[0])["type"] == "Transaction", kv[0]))
        entities = [{**_public(self.store.get(vid)), "hops": d} for vid, d in ordered[:limit]]
        # Always surface every related customer (identity-linkage analysis needs them all).
        listed = {e["id"] for e in entities}
        entities += [{**_public(self.store.get(vid)), "hops": d} for vid, d in ordered[limit:]
                     if self.store.get(vid)["type"] == "Customer" and vid not in listed]
        return {
            "root": _public(root),
            "hops": hops,
            "counts": dict(sorted(counts.items())),
            "fraud_transactions": sorted(fraud_txns),
            "confirmed_fraud_cases": sorted(confirmed_cases),
            "entities": entities,
        }

    def find_similar_cases(self, txn_id: str, pattern_tags: list[str], k: int = 5) -> dict[str, Any]:
        self._require(txn_id, "Transaction")
        tags = set(pattern_tags)
        # Entity overlap: closed cases reachable txn -> {card,device,ip,customer} -> txn -> case.
        overlap: dict[str, set[str]] = defaultdict(set)
        for hub in self.store.neighbors(txn_id):
            if self.store.get(hub)["type"] not in {"Card", "Device", "IP", "Customer"}:
                continue
            for t in self.store.neighbors(hub, "Transaction"):
                for cid in self.store.neighbors(t, "Case"):
                    overlap[cid].add(hub)
            for cid in self.store.neighbors(hub, "Case"):
                overlap[cid].add(hub)
        results = []
        for case in self.store.of_type("Case"):
            if case["status"] != "closed":
                continue
            ctags = set(case.get("pattern_tags") or [])
            jac = len(tags & ctags) / len(tags | ctags) if (tags or ctags) else 0.0
            ov = 1.0 if overlap.get(case["id"]) else 0.0
            score = round(0.6 * jac + 0.4 * ov, 3)
            if score < 0.25:
                continue
            results.append({
                "case_id": case["id"], "similarity": score, "pattern_tags": sorted(ctags),
                "outcome": case["outcome"], "decision": case.get("decision", ""),
                "summary": case.get("summary", ""), "shared_entities": sorted(overlap.get(case["id"], set())),
            })
        results.sort(key=lambda r: (-r["similarity"], r["case_id"]))
        return {"query_tags": sorted(tags), "cases": results[:k]}

    def detect_device_sharing(self, min_cards: int = 3) -> list[dict[str, Any]]:
        out = []
        for dev in self.store.of_type("Device"):
            cards: set[str] = set()
            custs: set[str] = set()
            for t in self.store.neighbors(dev["id"], "Transaction"):
                cards.update(self.store.neighbors(t, "Card"))
                custs.update(self.store.neighbors(t, "Customer"))
            if len(cards) >= min_cards:
                out.append({"device_id": dev["id"], "device_info": dev["device_info"],
                            "card_count": len(cards), "customer_count": len(custs), "cards": sorted(cards)})
        return sorted(out, key=lambda r: (-r["card_count"], r["device_id"]))

    def detect_velocity_burst(self, window_seconds: int = 3600, min_txns: int = 6) -> list[dict[str, Any]]:
        out = []
        for card in self.store.of_type("Card"):
            txns = sorted(self._txns(card["id"], None), key=lambda t: t["ts"])
            best, lo, best_span = 0, 0, (0, 0)
            for hi, t in enumerate(txns):
                while t["ts"] - txns[lo]["ts"] > window_seconds:
                    lo += 1
                if hi - lo + 1 > best:
                    best, best_span = hi - lo + 1, (lo, hi)
            if best >= min_txns:
                window = txns[best_span[0]:best_span[1] + 1]
                out.append({"card_id": card["id"], "txn_count": best,
                            "window_start": window[0]["ts"], "window_end": window[-1]["ts"],
                            "total_amount": round(sum(t["amount"] for t in window), 2)})
        return sorted(out, key=lambda r: (-r["txn_count"], r["card_id"]))

    def update_case_memory(self, case_id: str, memory: dict[str, Any]) -> dict[str, Any]:
        self._require(case_id, "Case")
        allowed = {"status", "outcome", "decision", "confidence", "summary", "pattern_tags",
                   "sar_filed", "evidence_ids", "closed_ts"}
        self.store.add_vertex("Case", case_id, **{k: v for k, v in memory.items() if k in allowed})
        return {"case_id": case_id, "written": sorted(k for k in memory if k in allowed), "backend": self.name}
