"""MCP client gateway used by the agent.

All graph access from the agent flows through here: tool names are checked
against an allowlist, every call is recorded for the audit trail, and results
are decoded from the MCP wire format.
"""

from __future__ import annotations

import json
import os
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from app.config import BACKEND_DIR
from app.graph.base import GraphProvider
from app.mcp_server.server import ALLOWED_TOOLS, EVIDENCE_TOOLS, build_mcp_server


class ToolNotAllowedError(PermissionError):
    pass


class ToolCallError(RuntimeError):
    pass


@dataclass
class ToolCallRecord:
    call_id: str
    tool: str
    arguments: dict[str, Any]
    ok: bool
    latency_ms: float
    error: str | None = None


@dataclass
class MCPToolGateway:
    client: Client
    allowed: tuple[str, ...] = ALLOWED_TOOLS
    calls: list[ToolCallRecord] = field(default_factory=list)

    async def list_tools(self, evidence_only: bool = True) -> list[dict[str, Any]]:
        names = EVIDENCE_TOOLS if evidence_only else self.allowed
        listed = await self.client.list_tools()
        return [
            {"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
            for t in listed.tools if t.name in names
        ]

    async def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool not in self.allowed:
            raise ToolNotAllowedError(f"tool '{tool}' is not in the MCP allowlist")
        started = time.perf_counter()
        call_id = f"mcp-{len(self.calls) + 1:03d}"
        result = await self.client.call_tool(tool, arguments)
        latency = round((time.perf_counter() - started) * 1000, 2)
        text = "".join(getattr(c, "text", "") for c in result.content)
        if result.is_error:
            self.calls.append(ToolCallRecord(call_id, tool, arguments, False, latency, text))
            raise ToolCallError(f"{tool} failed: {text}")
        self.calls.append(ToolCallRecord(call_id, tool, arguments, True, latency))
        payload = result.structured_content or json.loads(text)
        # Structured tool results may be wrapped as {"result": ...}.
        if isinstance(payload, dict) and set(payload) == {"result"}:
            payload = payload["result"]
        return payload


@asynccontextmanager
async def open_gateway(provider: GraphProvider | None = None) -> AsyncIterator[MCPToolGateway]:
    """Connect to the MCP server.

    MCP_TRANSPORT=stdio launches `python -m app.mcp_server` as a subprocess (the
    same process layout a desktop MCP host would use); the default connects to
    an in-process server instance over the MCP protocol.
    """
    if os.getenv("MCP_TRANSPORT", "inprocess") == "stdio":
        target: Any = StdioServerParameters(
            command=sys.executable, args=["-m", "app.mcp_server"], cwd=str(BACKEND_DIR),
        )
    else:
        if provider is None:
            from app.graph.factory import create_provider

            provider = create_provider()
        target = build_mcp_server(provider)
    async with Client(target) as client:
        yield MCPToolGateway(client=client)
