"""Contract tests for the live provider's result normalisation (pyTigerGraph is faked)."""

import csv

import pytest

from app.config import Settings
from app.graph import tigergraph_provider as tgp
from app.graph.base import GraphProviderError


class FakeConn:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.upserts = []

    def runInstalledQuery(self, name, params=None, timeout=None):
        self.calls.append((name, params))
        return self.responses[name]

    def upsertVertex(self, vtype, vid, attrs):
        self.upserts.append((vtype, vid, attrs))

    def echo(self):
        return "Hello GSQL"


def provider_with(responses) -> tgp.TigerGraphProvider:
    p = tgp.TigerGraphProvider.__new__(tgp.TigerGraphProvider)
    p.settings = Settings()
    p.conn = FakeConn(responses)
    return p


def v(vid, vtype, **attrs):
    return {"v_id": vid, "v_type": vtype, "attributes": attrs}


def test_context_is_normalised_to_mock_shape():
    p = provider_with({"get_transaction_context": [
        {"transaction": [v("T1", "Transaction", txn_id="T1", amount=10.0, ts=5)],
         "card": [v("CARD-1", "Card")], "device": [v("DEV-1", "Device")], "ip": [v("IP-1", "IP")],
         "customer": [v("CUST-1", "Customer")]},
        {"device_distinct_cards": 2, "device_cards": ["CARD-2", "CARD-1"], "card_countries_1h": ["US"],
         "fraud_labeled_neighbor_txns": []},
    ]})
    ctx = p.get_transaction_context("T1")
    assert ctx["transaction"] == {"id": "T1", "type": "Transaction", "amount": 10.0, "ts": 5}
    assert ctx["stats"]["device_cards"] == ["CARD-1", "CARD-2"]


def test_related_entities_passes_vertex_type_and_maps_fraudcase():
    p = provider_with({"find_related_entities": [
        {"root": [v("DEV-1", "Device")]},
        {"entities": [v("HHGOA-001", "FraudCase", status="closed", **{"@hop": 2})]},
        {"counts": {"FraudCase": 1}, "fraud_transactions": [], "confirmed_fraud_cases": []},
    ]})
    rel = p.find_related_entities("DEV-1", 2, 100)
    assert p.conn.calls[0][1]["root_id.type"] == "Device"
    assert rel["entities"][0]["type"] == "Case" and rel["entities"][0]["hops"] == 2
    assert rel["counts"] == {"Case": 1}


def test_history_derives_average_and_dormancy():
    p = provider_with({"get_customer_history": [
        {"customer": [v("CUST-1", "Customer", tenure_days=900)]},
        {"txn_count": 4, "total_amount": 400.0, "max_amount": 150.0, "chargeback_count": 0,
         "known_device_ids": ["DEV-1"], "known_ip_countries": ["US"], "cards": ["CARD-1"],
         "last_ts": 0, "prior_cases": []},
    ]})
    hist = p.get_customer_history("CUST-1", as_of_ts=86_400 * 10)
    assert hist["avg_amount"] == 100.0 and hist["days_since_last_txn"] == 10.0


def test_case_memory_upserts_fraudcase():
    p = provider_with({})
    p.update_case_memory("HHGOA-001", {"status": "closed", "pattern_tags": ["a"], "evidence_ids": ["EV-01"]})
    vtype, vid, attrs = p.conn.upserts[0]
    assert vtype == "FraudCase" and attrs["pattern_tags"] == ["a"]


def test_unknown_id_prefix_rejected():
    with pytest.raises(GraphProviderError):
        tgp.gsql_type_for("???")


def test_csv_export_covers_every_vertex(tmp_path):
    from scripts.export_tigergraph_csv import export

    counts = export(tmp_path)
    assert counts["cases.csv"] >= 20 + 33
    with (tmp_path / "transactions.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    assert all(r["card_id"] and r["device_id"] and r["ip_id"] and r["customer_id"] for r in rows)
