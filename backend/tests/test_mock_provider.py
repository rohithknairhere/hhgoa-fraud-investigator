from app.graph.factory import create_provider
from app.graph.mock_provider import MockGraphProvider
from app.config import Settings


def test_device_sharing_detects_ring_device(provider, scenarios):
    ring = provider.get_transaction_context(scenarios["HHGOA-001"].focal_txn_id)["device"]["id"]
    top = provider.detect_device_sharing(min_cards=3)[0]
    assert top["device_id"] == ring
    assert top["card_count"] >= 7


def test_velocity_burst_detects_card_testing(provider, scenarios):
    card = provider.get_transaction_context(scenarios["HHGOA-002"].focal_txn_id)["card"]["id"]
    bursts = {b["card_id"]: b for b in provider.detect_velocity_burst(window_seconds=3600, min_txns=6)}
    assert bursts[card]["txn_count"] == 15


def test_context_is_point_in_time(provider, scenarios):
    # HHGOA-017 later adds another card to the ring device; HHGOA-001 must not see it.
    ctx = provider.get_transaction_context(scenarios["HHGOA-001"].focal_txn_id)
    assert ctx["stats"]["device_distinct_cards"] == 7
    ctx17 = provider.get_transaction_context(scenarios["HHGOA-017"].focal_txn_id)
    assert ctx17["stats"]["device_distinct_cards"] == 8


def test_customer_history_excludes_final_24h(provider, scenarios):
    ctx = provider.get_transaction_context(scenarios["HHGOA-002"].focal_txn_id)
    hist = provider.get_customer_history(ctx["customer"]["id"], as_of_ts=ctx["transaction"]["ts"])
    assert hist["txn_count"] == 30
    assert ctx["device"]["id"] not in hist["known_device_ids"]


def test_similar_cases_use_entity_overlap(provider, scenarios):
    res = provider.find_similar_cases(scenarios["HHGOA-001"].focal_txn_id, ["device_sharing"])
    top = res["cases"][0]
    assert top["case_id"] == "CASE-H900" and top["shared_entities"]


def test_update_case_memory_is_retrievable(provider, scenarios):
    provider.update_case_memory("HHGOA-001", {"status": "closed", "outcome": "confirmed_fraud",
                                              "pattern_tags": ["device_sharing"], "ignored": 1})
    case = provider.get_case("HHGOA-001")["case"]
    assert case["status"] == "closed" and "ignored" not in case


def test_unreachable_tigergraph_falls_back_to_mock():
    s = Settings(tg_host="https://127.0.0.1:1", graph_backend="auto", tg_connect_timeout_s=0.2)
    assert isinstance(create_provider(s), MockGraphProvider)


def test_mock_forced_without_host():
    assert create_provider(Settings(tg_host="", graph_backend="auto")).name == "mock"
