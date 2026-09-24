"""Cyclic LangGraph investigation loop.

    trigger → investigate (GraphRAG via MCP) → assess_uncertainty → next_best_action
                                                   ▲                      │
                                                   │   confidence < 0.60  ▼
                                          gather_more_evidence ◄──────────┤
                                                                          │ terminal
                                                                          ▼
                                                                 update_case_memory → END
"""

from __future__ import annotations

import functools
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from app.agent import policy
from app.agent.oracle import EvidenceOracle
from app.agent.planner import EvidenceCollector, Planner
from app.agent.signals import (
    derive_pattern_tags, extract_graph_signals, followup_signal, precedent_signal,
)
from app.mcp_server.gateway import MCPToolGateway

LABEL_CATEGORY = {"context": "transaction_context", "history": "customer_history",
                  "related_device": "related_entities", "related_ip": "related_entities",
                  "related_customer": "related_entities", "similar": "similar_cases"}


class InvestigationState(TypedDict, total=False):
    case_id: str
    alert: dict[str, Any]
    transaction_id: str
    customer_id: str
    tool_results: dict[str, Any]
    evidence: list[dict[str, Any]]
    pattern_tags: list[str]
    signals: list[dict[str, Any]]
    assessment: dict[str, Any]
    assessments: list[dict[str, Any]]
    nba_log: list[dict[str, Any]]
    requests_made: list[str]
    followups: list[dict[str, Any]]
    rounds: int
    trace: list[dict[str, Any]]
    decision: dict[str, Any]
    sar: dict[str, Any] | None
    memory_write: dict[str, Any]


@dataclass
class AgentDeps:
    gateway: MCPToolGateway
    planner: Planner
    oracle: EvidenceOracle
    threshold: float = 0.60
    max_rounds: int = 2
    collector: EvidenceCollector | None = field(default=None)


Node = Callable[[InvestigationState, Runtime[AgentDeps]], Awaitable[dict[str, Any]]]


def traced(title: str) -> Callable[[Node], Node]:
    """Append a waterfall entry (timing + summary) for every node execution."""

    def wrap(fn: Node) -> Node:
        @functools.wraps(fn)
        async def inner(state: InvestigationState, runtime: Runtime[AgentDeps]) -> dict[str, Any]:
            started = datetime.now(timezone.utc)
            t0 = time.perf_counter()
            update = await fn(state, runtime)
            summary = update.pop("_summary", "")
            details = update.pop("_details", {})
            trace = list(state.get("trace", []))
            trace.append({
                "step": len(trace) + 1,
                "node": fn.__name__,
                "title": title,
                "started_at": started.isoformat(timespec="milliseconds"),
                "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
                "summary": summary,
                "details": details,
            })
            update["trace"] = trace
            return update

        return inner

    return wrap


@traced("Trigger: alert ingested")
async def trigger(state: InvestigationState, runtime: Runtime[AgentDeps]) -> dict[str, Any]:
    alert = state["alert"]
    for key in ("case_id", "transaction_id", "rule", "risk_score"):
        if key not in alert:
            raise ValueError(f"alert missing '{key}'")
    runtime.context.collector = EvidenceCollector(runtime.context.gateway)
    return {
        "case_id": alert["case_id"], "transaction_id": alert["transaction_id"],
        "evidence": [], "assessments": [], "nba_log": [], "requests_made": [], "followups": [], "rounds": 0,
        "_summary": f"{alert['rule']} fired on {alert['transaction_id']} with risk score {alert['risk_score']:.2f}.",
        "_details": {"alert": alert},
    }


@traced("Investigate: GraphRAG evidence via TigerGraph MCP")
async def investigate(state: InvestigationState, runtime: Runtime[AgentDeps]) -> dict[str, Any]:
    deps = runtime.context
    col = deps.collector
    assert col is not None
    await deps.planner.gather(col, state["alert"])
    prelim = extract_graph_signals(col.results, col.evidence_ids)
    tags = derive_pattern_tags(prelim)
    await col.call("similar", "find_similar_cases",
                   {"transaction_id": state["transaction_id"], "pattern_tags": tags, "k": 5}, deps.planner.name)
    similar = col.results["similar"]["cases"]
    return {
        "customer_id": col.results["context"]["customer"]["id"],
        "tool_results": dict(col.results),
        "evidence": list(col.evidence),
        "pattern_tags": tags,
        "_summary": (f"{len(col.evidence)} MCP tool calls ({deps.planner.name} planner); pattern tags "
                     f"{tags or ['none']}; {len(similar)} similar closed cases retrieved."),
        "_details": {"tool_calls": [{"evidence_id": e["evidence_id"], "tool": e["tool"], "summary": e["summary"]}
                                    for e in col.evidence]},
    }


@traced("Assess uncertainty")
async def assess_uncertainty(state: InvestigationState, runtime: Runtime[AgentDeps]) -> dict[str, Any]:
    results = state["tool_results"]
    col = runtime.context.collector
    assert col is not None
    signals = extract_graph_signals(results, col.evidence_ids)
    prec = precedent_signal(results["similar"], col.evidence_ids["similar"])
    if prec:
        signals.append(prec)
    for f in state.get("followups", []):
        signals.append(followup_signal(f, f["evidence_id"]))
    graph_cats = {LABEL_CATEGORY[k] for k in results if k in LABEL_CATEGORY}
    verified = {f["category"] for f in state.get("followups", [])}
    a = policy.assess(state["alert"]["risk_score"], signals, graph_cats, verified)
    a["round"] = state.get("rounds", 0)
    return {
        "signals": signals, "assessment": a, "assessments": [*state.get("assessments", []), a],
        "_summary": (f"p_fraud={a['p_fraud']:.2f}, confidence={a['confidence']:.2f} "
                     f"(coverage {a['components']['evidence_coverage']:.2f}, conflict "
                     f"{a['components']['signal_conflict']:.2f}); {len(signals)} signals."),
        "_details": {"assessment": a, "signals": [{"name": s["name"], "contribution": s["contribution"]}
                                                   for s in signals]},
    }


@traced("Next best action")
async def next_best_action(state: InvestigationState, runtime: Runtime[AgentDeps]) -> dict[str, Any]:
    deps = runtime.context
    ctx = state["tool_results"]["context"]
    aggregate = max(ctx["stats"]["customer_amount_24h"], ctx["transaction"]["amount"])
    nba = policy.choose_action(state["assessment"], state["signals"], state["pattern_tags"], aggregate,
                               deps.threshold, state.get("rounds", 0), deps.max_rounds,
                               state.get("requests_made", []))
    log = list(state.get("nba_log", []))
    nba.update({
        "phase": "initial" if not log else "updated",
        "round": state.get("rounds", 0),
        "p_fraud": state["assessment"]["p_fraud"],
        "confidence": state["assessment"]["confidence"],
        "logged_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    })
    log.append(nba)
    return {"nba_log": log,
            "_summary": f"[{nba['phase']}] {nba['action']}: {nba['rationale']}",
            "_details": {"nba": nba}}


@traced("Gather more evidence")
async def gather_more_evidence(state: InvestigationState, runtime: Runtime[AgentDeps]) -> dict[str, Any]:
    deps = runtime.context
    col = deps.collector
    assert col is not None
    request = state["nba_log"][-1]["evidence_request"]
    items = deps.oracle.request(request)
    followups = list(state.get("followups", []))
    new_evidence = []
    for item in items:
        eid = f"EV-{len(col.evidence) + 1:02d}"
        record = {"evidence_id": eid, "label": f"followup:{request}", "source": item["source"],
                  "tool": None, "summary": item["description"], "graph_elements": [],
                  "category": item["category"], "round": state.get("rounds", 0) + 1}
        col.evidence.append(record)
        new_evidence.append(record)
        followups.append({**item, "evidence_id": eid})
    return {
        "followups": followups,
        "evidence": list(col.evidence),
        "requests_made": [*state.get("requests_made", []), request],
        "rounds": state.get("rounds", 0) + 1,
        "_summary": (f"Requested {request}; received {len(items)} item(s): "
                     + ("; ".join(i["description"] for i in items) if items else "no response")),
        "_details": {"request": request, "received": new_evidence},
    }


@traced("Update case memory")
async def update_case_memory(state: InvestigationState, runtime: Runtime[AgentDeps]) -> dict[str, Any]:
    deps = runtime.context
    final = state["nba_log"][-1]
    a = state["assessment"]
    evidence_by_id = {e["evidence_id"]: e for e in state["evidence"]}
    justification = []
    cited: set[str] = set()
    for s in sorted(state["signals"], key=lambda s: -abs(s["contribution"])):
        cited.update(s["evidence_ids"])
        justification.append({k: s[k] for k in ("name", "direction", "contribution", "description",
                                                 "evidence_ids", "graph_elements")})
    sar = None
    if final["action"] == "BLOCK_AND_FILE_SAR":
        sar = policy.sar_narrative(state["case_id"], state["alert"], state["tool_results"]["context"], a,
                                   state["signals"], state["pattern_tags"])
    decision = {
        "action": final["action"],
        "label": final["label"],
        "p_fraud": a["p_fraud"],
        "confidence": a["confidence"],
        "rationale": final["rationale"],
        "justification": justification,
        "evidence_cited": [evidence_by_id[e] for e in sorted(cited) if e in evidence_by_id],
        "similar_cases": state["tool_results"]["similar"]["cases"][:3],
        "sar_required": sar is not None,
    }
    outcome = {"BLOCK_AND_FILE_SAR": "confirmed_fraud", "BLOCK_TRANSACTION": "confirmed_fraud",
               "ALLOW_TRANSACTION": "false_positive"}.get(final["action"], "escalated")
    memory = {
        "status": "closed" if outcome != "escalated" else "escalated",
        "outcome": outcome,
        "decision": final["action"],
        "confidence": a["confidence"],
        "summary": final["rationale"],
        "pattern_tags": state["pattern_tags"],
        "sar_filed": sar is not None,
        "evidence_ids": sorted(cited),
        "closed_ts": state["tool_results"]["context"]["transaction"]["ts"],
    }
    write = await deps.gateway.call("update_case_memory", {"case_id": state["case_id"], "memory": memory})
    return {
        "decision": decision, "sar": sar, "memory_write": {**write, "memory": memory},
        "_summary": f"Case {state['case_id']} written back to graph as {memory['status']} ({final['action']}).",
        "_details": {"memory": memory},
    }


def route_after_nba(state: InvestigationState) -> str:
    return "update_case_memory" if state["nba_log"][-1]["terminal"] else "gather_more_evidence"


def build_graph():
    g = StateGraph(InvestigationState, context_schema=AgentDeps)
    g.add_node("trigger", trigger)
    g.add_node("investigate", investigate)
    g.add_node("assess_uncertainty", assess_uncertainty)
    g.add_node("next_best_action", next_best_action)
    g.add_node("gather_more_evidence", gather_more_evidence)
    g.add_node("update_case_memory", update_case_memory)
    g.add_edge(START, "trigger")
    g.add_edge("trigger", "investigate")
    g.add_edge("investigate", "assess_uncertainty")
    g.add_edge("assess_uncertainty", "next_best_action")
    g.add_conditional_edges("next_best_action", route_after_nba,
                            ["gather_more_evidence", "update_case_memory"])
    g.add_edge("gather_more_evidence", "assess_uncertainty")
    g.add_edge("update_case_memory", END)
    return g.compile()


INVESTIGATION_GRAPH = build_graph()
