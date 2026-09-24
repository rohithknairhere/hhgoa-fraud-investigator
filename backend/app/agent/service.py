"""Run investigations and shape the investigation record."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from app.agent.graph import INVESTIGATION_GRAPH, AgentDeps
from app.agent.oracle import ScriptedEvidenceOracle
from app.agent.planner import Planner
from app.config import get_settings
from app.data.scenarios import Scenario
from app.mcp_server.gateway import MCPToolGateway


def alert_for(scenario: Scenario) -> dict[str, Any]:
    return {
        "case_id": scenario.case_id,
        "transaction_id": scenario.focal_txn_id,
        "rule": scenario.alert_rule,
        "risk_score": scenario.risk_score,
        "source": "hhgoa-risk-engine",
    }


def graph_view(results: dict[str, Any], signals: list[dict[str, Any]]) -> dict[str, Any]:
    """Compact node/edge view of the evidence sub-graph for the dashboard."""
    ctx = results["context"]
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []
    flagged = {el for s in signals if s["contribution"] > 0 for el in s["graph_elements"]}

    def node(v: dict[str, Any], role: str = "context") -> str:
        label = v["id"]
        if v["type"] == "Transaction":
            label = f"{v['id']} (${v['amount']:,.0f})"
        elif v["type"] == "Device":
            label = f"{v['id']} ({v['device_info']})"
        elif v["type"] == "IP":
            label = f"{v['id']} ({v['country']}{', proxy' if v.get('is_proxy') else ''})"
        nodes.setdefault(v["id"], {"id": v["id"], "type": v["type"], "label": label, "role": role,
                                   "flagged": v["id"] in flagged})
        return v["id"]

    t = node(ctx["transaction"], "focal")
    for key, et in (("card", "PAID_WITH"), ("device", "USED_DEVICE"), ("ip", "FROM_IP"), ("customer", "PLACED_BY")):
        edges.append({"source": t, "target": node(ctx[key]), "type": et})
    dev_id = ctx["device"]["id"]
    for card_id in ctx["stats"]["device_cards"][:8]:
        if card_id != ctx["card"]["id"]:
            nodes.setdefault(card_id, {"id": card_id, "type": "Card", "label": card_id, "role": "neighbour",
                                       "flagged": card_id in flagged})
            edges.append({"source": dev_id, "target": card_id, "type": "SHARED_DEVICE"})
    for key in ("related_device", "related_ip", "related_customer"):
        rel = results.get(key) or {}
        for fid in rel.get("fraud_transactions", [])[:5]:
            nodes.setdefault(fid, {"id": fid, "type": "Transaction", "label": f"{fid} (fraud)",
                                   "role": "neighbour", "flagged": True})
            edges.append({"source": rel["root"]["id"], "target": fid, "type": "LINKED_FRAUD"})
    for s in signals:
        if s["name"] == "synthetic_identity":
            for peer in s["graph_elements"][1:]:
                nodes.setdefault(peer, {"id": peer, "type": "Customer", "label": peer, "role": "neighbour",
                                        "flagged": True})
                edges.append({"source": ctx["customer"]["id"], "target": peer, "type": "SHARED_ADDRESS"})
    for c in results["similar"]["cases"][:3]:
        nodes.setdefault(c["case_id"], {"id": c["case_id"], "type": "Case",
                                        "label": f"{c['case_id']} ({c['outcome']})", "role": "memory",
                                        "flagged": c["outcome"] == "confirmed_fraud"})
        edges.append({"source": t, "target": c["case_id"], "type": "SIMILAR_TO"})
    # de-duplicate edges
    seen, uniq = set(), []
    for e in edges:
        k = (e["source"], e["target"], e["type"])
        if k not in seen:
            seen.add(k)
            uniq.append(e)
    return {"nodes": list(nodes.values()), "edges": uniq}


async def investigate_scenario(scenario: Scenario, gateway: MCPToolGateway, planner: Planner,
                               backend: str) -> dict[str, Any]:
    settings = get_settings()
    deps = AgentDeps(gateway=gateway, planner=planner, oracle=ScriptedEvidenceOracle(scenario.followups),
                     threshold=settings.confidence_threshold, max_rounds=settings.max_evidence_rounds)
    first_call = len(gateway.calls)
    state = await INVESTIGATION_GRAPH.ainvoke({"alert": alert_for(scenario)}, context=deps)
    nba_log = state["nba_log"]
    initial, final = nba_log[0], nba_log[-1]
    requested = bool(state.get("requests_made"))
    passed = (final["action"] == scenario.expected_final_action
              and initial["terminal"] == scenario.expected_initial_terminal)
    results = state["tool_results"]
    return {
        "case_id": scenario.case_id,
        "title": scenario.title,
        "typology": scenario.typology,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "graph_backend": backend,
        "planner": planner.name,
        "alert": state["alert"],
        "investigation_record": {
            "transaction_id": state["transaction_id"],
            "customer_id": state["customer_id"],
            "pattern_tags": state["pattern_tags"],
            "evidence": state["evidence"],
            "signals": state["signals"],
            "assessments": state["assessments"],
            "nba_log": nba_log,
            "trace": state["trace"],
            "mcp_tool_calls": [asdict(c) for c in gateway.calls[first_call:]],
            "graph_context": {
                "transaction": results["context"]["transaction"],
                "card": results["context"]["card"],
                "device": results["context"]["device"],
                "ip": results["context"]["ip"],
                "customer": results["context"]["customer"],
                "stats": results["context"]["stats"],
                "customer_history": {k: v for k, v in results["history"].items() if k != "customer"},
                "neighbourhoods": {k: {"root": results[k]["root"]["id"], "counts": results[k]["counts"],
                                       "fraud_transactions": results[k]["fraud_transactions"],
                                       "confirmed_fraud_cases": results[k]["confirmed_fraud_cases"]}
                                   for k in ("related_device", "related_ip", "related_customer") if k in results},
                "similar_cases": results["similar"]["cases"],
                "view": graph_view(results, state["signals"]),
            },
        },
        "nba_before_additional_evidence": initial,
        "additional_evidence_requested": requested,
        "additional_evidence": state.get("followups", []),
        "nba_after_additional_evidence": final,
        "final_decision": state["decision"],
        "sar": state["sar"] or {"required": False, "narrative": None},
        "case_memory_write": state["memory_write"],
        "benchmark": {
            "expected_initial_terminal": scenario.expected_initial_terminal,
            "expected_final_action": scenario.expected_final_action,
            "passed": passed,
        },
    }
