import os
import sys

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from app.config import BACKEND_DIR
from app.mcp_server.gateway import ToolCallError, ToolNotAllowedError, open_gateway
from app.mcp_server.server import ALLOWED_TOOLS, EVIDENCE_TOOLS


async def test_gateway_exposes_only_typed_evidence_tools(provider):
    async with open_gateway(provider) as gw:
        names = {t["name"] for t in await gw.list_tools()}
        assert names == set(EVIDENCE_TOOLS)
        assert {"get_transaction_context", "get_customer_history", "find_related_entities"} <= names
        all_tools = await gw.client.list_tools()
        for t in all_tools.tools:
            props = t.input_schema.get("properties", {})
            assert not any(p in props for p in ("query", "gsql", "sql")), t.name


async def test_gateway_rejects_unlisted_tools(provider):
    async with open_gateway(provider) as gw:
        with pytest.raises(ToolNotAllowedError):
            await gw.call("run_gsql", {"query": "INTERPRET QUERY () { }"})


async def test_gateway_records_calls_and_errors(provider, scenarios):
    async with open_gateway(provider) as gw:
        ctx = await gw.call("get_transaction_context", {"transaction_id": scenarios["HHGOA-003"].focal_txn_id})
        assert ctx["transaction"]["amount"] == 2400.0
        with pytest.raises(ToolCallError):
            await gw.call("get_transaction_context", {"transaction_id": "T-does-not-exist"})
        assert [c.ok for c in gw.calls] == [True, False]


async def test_stdio_transport_round_trip(scenarios):
    params = StdioServerParameters(command=sys.executable, args=["-m", "app.mcp_server"],
                                   cwd=str(BACKEND_DIR), env={**os.environ, "GRAPH_BACKEND": "mock"})
    async with Client(params) as client:
        tools = await client.list_tools()
        assert {t.name for t in tools.tools} == set(ALLOWED_TOOLS)
        res = await client.call_tool("find_similar_cases",
                                     {"transaction_id": scenarios["HHGOA-001"].focal_txn_id,
                                      "pattern_tags": ["device_sharing"]})
        assert not res.is_error
