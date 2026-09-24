"""HHGOA TigerGraph MCP server.

Exposes a closed set of typed, read-only investigation tools over the graph
plus one write tool for case memory. Tools call installed GSQL queries (or the
mock provider) — there is deliberately no tool that accepts raw GSQL/SQL.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from app.graph.base import GraphProvider

SERVER_NAME = "hhgoa-tigergraph"

# Tools an LLM planner may call. Case-memory writes stay with the agent runtime.
EVIDENCE_TOOLS = (
    "get_transaction_context",
    "get_customer_history",
    "find_related_entities",
    "find_similar_cases",
)
MEMORY_TOOLS = ("update_case_memory",)
ALLOWED_TOOLS = EVIDENCE_TOOLS + MEMORY_TOOLS


def build_mcp_server(provider: GraphProvider) -> MCPServer:
    server = MCPServer(
        SERVER_NAME,
        instructions=(
            "Fraud-investigation tools over the HHGOA_IEEE TigerGraph. All tools are typed, "
            "parameterised calls to installed queries; raw GSQL is not accepted."
        ),
    )

    @server.tool()
    def get_transaction_context(transaction_id: str) -> dict[str, Any]:
        """Return the transaction with its card, device, IP and customer, plus graph statistics
        (distinct cards per device/IP, 1h card velocity, 24h customer totals, near-threshold
        counts and fraud-labelled neighbouring transactions), all as of the transaction time."""
        return provider.get_transaction_context(transaction_id)

    @server.tool()
    def get_customer_history(customer_id: str, as_of_ts: int | None = None,
                             lookback_days: int = 365) -> dict[str, Any]:
        """Return the customer's baseline behaviour before `as_of_ts` (excluding the final 24h):
        transaction count, average/max amount, chargebacks, known devices and countries, days
        since last activity and prior closed cases."""
        return provider.get_customer_history(customer_id, as_of_ts, lookback_days)

    @server.tool()
    def find_related_entities(entity_id: str, hops: int = 2, as_of_ts: int | None = None,
                              limit: int = 50) -> dict[str, Any]:
        """Breadth-first expansion (1-3 hops) from any vertex id, returning related entities,
        per-type counts, fraud-labelled transactions and confirmed-fraud cases in the neighbourhood."""
        return provider.find_related_entities(entity_id, hops, as_of_ts, limit)

    @server.tool()
    def find_similar_cases(transaction_id: str, pattern_tags: list[str], k: int = 5) -> dict[str, Any]:
        """GraphRAG retrieval of closed cases similar to this transaction, scored by shared
        entities (card/device/IP/customer) and pattern-tag overlap."""
        return provider.find_similar_cases(transaction_id, pattern_tags, k)

    @server.tool()
    def update_case_memory(case_id: str, memory: dict[str, Any]) -> dict[str, Any]:
        """Persist the investigation outcome (status, decision, confidence, summary, pattern tags,
        SAR flag, evidence ids) onto the Case vertex so future investigations can retrieve it."""
        return provider.update_case_memory(case_id, memory)

    return server
