from app.agent import policy
from app.agent.signals import IDENTITY


def sig(name, contribution, needs=None):
    return {"name": name, "contribution": contribution, "needs_verification": needs}


ALL_GRAPH = set(policy.GRAPH_CATEGORIES)


def test_missing_verification_lowers_confidence():
    s = [sig("new_device", 0.7, IDENTITY), sig("amount_anomaly", 1.0, IDENTITY)]
    unverified = policy.assess(0.7, s, ALL_GRAPH, set())
    verified = policy.assess(0.7, s, ALL_GRAPH, {IDENTITY})
    assert unverified["missing_verifications"] == [IDENTITY]
    assert verified["confidence"] > unverified["confidence"]
    assert unverified["p_fraud"] == verified["p_fraud"]


def test_conflicting_signals_are_penalised():
    clean = policy.assess(0.5, [sig("a", 2.0)], ALL_GRAPH, set())
    mixed = policy.assess(0.5, [sig("a", 3.2), sig("b", -1.2)], ALL_GRAPH, set())
    assert mixed["components"]["signal_conflict"] > 0
    assert mixed["confidence"] < clean["confidence"] + 0.01


def test_low_confidence_requests_step_up_first():
    a = policy.assess(0.6, [sig("new_device", 0.7, IDENTITY)], ALL_GRAPH, set())
    nba = policy.choose_action(a, [], [], 100, 0.6, 0, 2, [])
    assert nba["action"] == "MONITOR_ACCOUNT_AND_REQUEST_STEP_UP_AUTH" and not nba["terminal"]


def test_escalates_when_rounds_exhausted():
    a = policy.assess(0.5, [sig("x", 0.1)], ALL_GRAPH, set())
    nba = policy.choose_action(a, [], [], 100, 0.6, 2, 2, ["step_up_auth"])
    assert nba["action"] == "ESCALATE_TO_SENIOR_ANALYST" and nba["terminal"]


def test_sar_requires_high_probability_and_typology():
    a = policy.assess(0.9, [sig("device_sharing", 5.0)], ALL_GRAPH, set())
    assert policy.choose_action(a, [], ["device_sharing"], 500, 0.6, 0, 2, [])["action"] == "BLOCK_AND_FILE_SAR"
    assert policy.choose_action(a, [], ["velocity_burst"], 500, 0.6, 0, 2, [])["action"] == "BLOCK_TRANSACTION"
    assert policy.choose_action(a, [], ["velocity_burst"], 9000, 0.6, 0, 2, [])["action"] == "BLOCK_AND_FILE_SAR"
