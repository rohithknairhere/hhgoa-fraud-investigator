"""Run the HHGOA TigerGraph MCP server over stdio: `python -m app.mcp_server`."""

from app.graph.factory import create_provider
from app.mcp_server.server import build_mcp_server

if __name__ == "__main__":
    build_mcp_server(create_provider()).run("stdio")
