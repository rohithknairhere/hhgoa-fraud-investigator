"""Evidence planners: decide which MCP tools to call during the GraphRAG step.

* DeterministicPlanner — fixed, auditable investigation playbook (default; no API key needed).
* ClaudePlanner — Claude chooses tools from the MCP tool list. It can only reach
  the graph through the allowlisted MCP tools; it never sees or writes GSQL.
  Scoring and the final decision stay deterministic either way.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from app.mcp_server.gateway import MCPToolGateway

log = logging.getLogger(__name__)

REQUIRED_LABELS = ("context", "history", "related_device", "related_ip", "related_customer")


class EvidenceCollector:
    """Accumulates tool results under stable labels and mints evidence records."""

    def __init__(self, gateway: MCPToolGateway) -> None:
        self.gateway = gateway
        self.results: dict[str, Any] = {}
        self.evidence: list[dict[str, Any]] = []
        self.evidence_ids: dict[str, str] = {}

    async def call(self, label: str | None, tool: str, args: dict[str, Any], origin: str) -> dict[str, Any]:
        payload = await self.gateway.call(tool, args)
        label = label or _label_for(tool, payload)
        record = self.gateway.calls[-1]
        eid = f"EV-{len(self.evidence) + 1:02d}"
        self.results[label] = payload
        self.evidence_ids[label] = eid
        self.evidence.append({
            "evidence_id": eid,
            "label": label,
            "source": "tigergraph-mcp",
            "tool": tool,
            "mcp_call_id": record.call_id,
            "arguments": args,
            "latency_ms": record.latency_ms,
            "origin": origin,
            "summary": _summarise(label, payload),
            "graph_elements": _elements(label, payload),
        })
        return payload


def _label_for(tool: str, payload: dict[str, Any]) -> str:
    if tool == "get_transaction_context":
        return "context"
    if tool == "get_customer_history":
        return "history"
    if tool == "find_similar_cases":
        return "similar"
    root_type = (payload.get("root") or {}).get("type", "entity").lower()
    return f"related_{root_type}"


def _summarise(label: str, p: dict[str, Any]) -> str:
    if label == "context":
        s, t = p["stats"], p["transaction"]
        return (f"Txn {t['id']} ${t['amount']:,.2f}; device cards={s['device_distinct_cards']}, "
                f"IP cards={s['ip_distinct_cards']}, card 1h velocity={s['card_txn_count_1h']}, "
                f"near-threshold 24h={s['near_threshold_count_24h']}")
    if label == "history":
        return (f"{p['txn_count']} baseline txns, avg ${p['avg_amount'] or 0:,.2f}, "
                f"{p['chargeback_count']} chargebacks, {len(p['known_device_ids'])} known devices, "
                f"countries {p['known_ip_countries']}")
    if label == "similar":
        return f"{len(p['cases'])} similar closed cases for tags {p['query_tags']}"
    counts = ", ".join(f"{k}={v}" for k, v in p.get("counts", {}).items())
    return (f"{p['hops']}-hop neighbourhood of {p['root']['id']}: {counts}; "
            f"fraud txns={len(p['fraud_transactions'])}, confirmed cases={len(p['confirmed_fraud_cases'])}")


def _elements(label: str, p: dict[str, Any]) -> list[str]:
    if label == "context":
        return [p[k]["id"] for k in ("transaction", "card", "device", "ip", "customer") if p.get(k)]
    if label == "history":
        return [p["customer"]["id"], *p.get("known_device_ids", [])]
    if label == "similar":
        return [c["case_id"] for c in p["cases"]]
    return [p["root"]["id"], *p["fraud_transactions"], *p["confirmed_fraud_cases"]]


class Planner(Protocol):
    name: str

    async def gather(self, collector: EvidenceCollector, alert: dict[str, Any]) -> None: ...


async def run_playbook(collector: EvidenceCollector, alert: dict[str, Any], origin: str) -> None:
    """Fill any required evidence label that is still missing."""
    r = collector.results
    if "context" not in r:
        await collector.call("context", "get_transaction_context", {"transaction_id": alert["transaction_id"]}, origin)
    ctx = r["context"]
    ts = ctx["transaction"]["ts"]
    if "history" not in r:
        await collector.call("history", "get_customer_history",
                             {"customer_id": ctx["customer"]["id"], "as_of_ts": ts}, origin)
    for label, key in (("related_device", "device"), ("related_ip", "ip"), ("related_customer", "customer")):
        if label not in r:
            await collector.call(label, "find_related_entities",
                                 {"entity_id": ctx[key]["id"], "hops": 2, "as_of_ts": ts}, origin)


class DeterministicPlanner:
    name = "deterministic"

    async def gather(self, collector: EvidenceCollector, alert: dict[str, Any]) -> None:
        await run_playbook(collector, alert, origin="playbook")


class ClaudePlanner:
    """Claude-directed evidence gathering over the MCP evidence tools (manual tool-use loop)."""

    name = "claude"
    SYSTEM = (
        "You are a fraud investigator working a case in a TigerGraph fraud graph built from the IEEE-CIS "
        "dataset. Use the provided tools to gather evidence about the alerted transaction: its context, the "
        "customer's baseline history, and the neighbourhoods of its device, IP and customer. You can only access "
        "the graph through these tools. Stop calling tools once you have enough evidence and reply with a "
        "two-sentence summary of what looks suspicious or benign."
    )

    def __init__(self, model: str, max_turns: int = 8) -> None:
        from anthropic import AsyncAnthropic

        self.client = AsyncAnthropic()
        self.model = model
        self.max_turns = max_turns

    async def gather(self, collector: EvidenceCollector, alert: dict[str, Any]) -> None:
        import anthropic

        tools = await collector.gateway.list_tools(evidence_only=True)
        tools = [t for t in tools if t["name"] != "find_similar_cases"]  # retrieved after signal tagging
        messages: list[dict[str, Any]] = [{"role": "user", "content": (
            f"Alert {alert['rule']} (risk score {alert['risk_score']:.2f}) on transaction "
            f"{alert['transaction_id']} for case {alert['case_id']}. Investigate.")}]
        try:
            for _ in range(self.max_turns):
                response = await self.client.beta.messages.create(
                    model=self.model,
                    max_tokens=16000,
                    system=self.SYSTEM,
                    thinking={"type": "adaptive"},
                    tools=tools,
                    messages=messages,
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                )
                if response.stop_reason != "tool_use":
                    break
                messages.append({"role": "assistant", "content": response.content})
                results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    try:
                        payload = await collector.call(None, block.name, dict(block.input), origin="claude")
                        content, is_error = json.dumps(payload)[:20000], False
                    except Exception as exc:  # surfaced back to the model as a tool error
                        content, is_error = f"Error: {exc}", True
                    results.append({"type": "tool_result", "tool_use_id": block.id,
                                    "content": content, "is_error": is_error})
                messages.append({"role": "user", "content": results})
        except (anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
            log.warning("Claude planner unavailable (%s); continuing with playbook", exc)
        # Guarantee minimum evidence coverage regardless of what the model chose.
        await run_playbook(collector, alert, origin="runtime-supplement")


def make_planner(kind: str, model: str) -> Planner:
    if kind == "claude":
        return ClaudePlanner(model)
    return DeterministicPlanner()
