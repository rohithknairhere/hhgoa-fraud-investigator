import pytest

from app.agent.planner import DeterministicPlanner
from app.agent.service import investigate_scenario
from app.data.scenarios import SCENARIOS, build_dataset
from app.graph.mock_provider import MockGraphProvider
from app.mcp_server.gateway import open_gateway


@pytest.fixture(scope="module")
def records():
    """Run all 20 cases once, sequentially, on one shared graph (case memory accumulates)."""
    import asyncio

    async def run():
        build_dataset()
        provider = MockGraphProvider()
        out = {}
        async with open_gateway(provider) as gw:
            for sc in SCENARIOS:
                out[sc.case_id] = await investigate_scenario(sc, gw, DeterministicPlanner(), provider.name)
        return out, provider

    return asyncio.run(run())


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.case_id)
def test_benchmark_outcomes(records, scenario):
    rec = records[0][scenario.case_id]
    assert rec["nba_before_additional_evidence"]["terminal"] == scenario.expected_initial_terminal
    assert rec["nba_after_additional_evidence"]["action"] == scenario.expected_final_action
    assert rec["benchmark"]["passed"]


def test_uncertain_cases_log_initial_and_updated_nba(records):
    for rec in records[0].values():
        log = rec["investigation_record"]["nba_log"]
        assert log[0]["phase"] == "initial"
        if not log[0]["terminal"]:
            assert log[0]["confidence"] < 0.60
            assert rec["additional_evidence_requested"]
            assert all(n["phase"] == "updated" for n in log[1:]) and len(log) >= 2
        else:
            assert log[0]["confidence"] >= 0.60 and len(log) == 1


def test_cycle_runs_multiple_evidence_rounds(records):
    rec = records[0]["HHGOA-015"]
    nodes = [t["node"] for t in rec["investigation_record"]["trace"]]
    assert nodes.count("gather_more_evidence") == 2
    assert nodes.count("assess_uncertainty") == 3
    assert nodes[-1] == "update_case_memory"


def test_every_decision_cites_graph_evidence(records):
    for rec in records[0].values():
        d = rec["final_decision"]
        evidence_ids = {e["evidence_id"] for e in rec["investigation_record"]["evidence"]}
        assert d["justification"], rec["case_id"]
        graph_cited = [e for e in d["evidence_cited"] if e["source"] == "tigergraph-mcp"]
        assert graph_cited, rec["case_id"]
        for j in d["justification"]:
            assert set(j["evidence_ids"]) <= evidence_ids
        for e in graph_cited:
            assert e["tool"] in {"get_transaction_context", "get_customer_history",
                                 "find_related_entities", "find_similar_cases"}
            assert e["mcp_call_id"].startswith("mcp-")


def test_sar_narrative_only_when_required(records):
    for rec in records[0].values():
        if rec["final_decision"]["action"] == "BLOCK_AND_FILE_SAR":
            assert rec["sar"]["required"] and "Basis for suspicion" in rec["sar"]["narrative"]
        else:
            assert rec["sar"] == {"required": False, "narrative": None}


def test_case_memory_written_back(records):
    recs, provider = records
    for cid, rec in recs.items():
        case = provider.get_case(cid)["case"]
        assert case["decision"] == rec["final_decision"]["action"]
    # GraphRAG memory: the later ring case retrieves the earlier one it shares a device with.
    similar = [c["case_id"] for c in recs["HHGOA-017"]["investigation_record"]["graph_context"]["similar_cases"]]
    assert "HHGOA-001" in similar
