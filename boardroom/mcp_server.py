"""BOARDROOM MCP server — exposes scan() as an MCP tool for Cognis.Studio."""
from __future__ import annotations
from boardroom.core import scan, to_json

def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-boardroom[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print("Install the MCP extra: pip install 'cognis-boardroom[mcp]'")
        return 1
    app = FastMCP("boardroom")

    @app.tool()
    def boardroom_scan(target: str) -> str:
        """Investor-update and KPI one-pager generator from your metrics. Returns JSON findings."""
        return to_json(scan(target))

    app.run()
    return 0
