"""MCP server — exposes the Capital platform as agent tools.

The server wraps the engine's REST API: each tool is one authenticated HTTP
call. The API token (`CAPITAL_MCP_TOKEN`) carries a role, so the API itself
enforces which tools an agent may actually use — a read-only token's
manage/trade calls come back as a 403:

- *Read* (any token): get_portfolio, get_positions, get_trade_history,
  list_strategies.
- *Manage* (user/admin token): set_allocation, enable_strategy,
  analyze_and_decide.
- *Trade* (admin token only): set_mode, close_strategy.

Run as a stdio MCP server: `python mcp_server.py`.
"""

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

BASE_URL = os.environ.get("CAPITAL_API_URL", "http://localhost:8000")
TOKEN = os.environ.get("CAPITAL_MCP_TOKEN", "")

mcp = FastMCP("capital")

_http: httpx.Client | None = None


def _client() -> httpx.Client:
    global _http
    if _http is None:
        _http = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=30.0,
        )
    return _http


def configure(client: httpx.Client) -> None:
    """Override the HTTP client — used by tests to target the ASGI app."""
    global _http
    _http = client


def _request(method: str, path: str, **kwargs: Any) -> Any:
    """One authenticated API call. Errors come back as `{"error": ...}`."""
    try:
        response = _client().request(method, path, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else {}
    except httpx.HTTPStatusError as exc:
        return {"error": f"{exc.response.status_code}: {exc.response.text}"}
    except httpx.HTTPError as exc:
        return {"error": f"request failed: {exc}"}


# -- read tools -------------------------------------------------------------


@mcp.tool()
def get_portfolio() -> Any:
    """Portfolio accounting summary — equity, PnL, fees, allocation."""
    return _request("GET", "/api/portfolio/summary")


@mcp.tool()
def get_positions() -> Any:
    """All currently open positions across strategies."""
    return _request("GET", "/api/portfolio/positions")


@mcp.tool()
def get_trade_history(limit: int = 100) -> Any:
    """The transaction log, newest-first."""
    return _request("GET", "/api/history/trades", params={"limit": limit})


@mcp.tool()
def list_strategies() -> Any:
    """Every registered strategy with its allocation, state and PnL."""
    return _request("GET", "/api/strategies")


# -- manage tools -----------------------------------------------------------


@mcp.tool()
def set_allocation(strategy: str, allocated: str) -> Any:
    """Set a strategy's capital allocation (quote currency)."""
    return _request(
        "PATCH", f"/api/strategies/{strategy}/allocation", json={"allocated": allocated}
    )


@mcp.tool()
def enable_strategy(strategy: str, enabled: bool) -> Any:
    """Enable or disable a strategy."""
    return _request(
        "PATCH", f"/api/strategies/{strategy}/enabled", json={"enabled": enabled}
    )


@mcp.tool()
def analyze_and_decide(task: str) -> Any:
    """Ask the configured LLM to analyze a task and recommend an action."""
    return _request("POST", "/api/ai/analyze", json={"task": task})


# -- trade tools (admin token only) -----------------------------------------


@mcp.tool()
def set_mode(mode: str, confirm: bool = False) -> Any:
    """Switch the trading mode (sim / testnet / live)."""
    return _request(
        "PUT", "/api/settings/mode", json={"mode": mode, "confirm": confirm}
    )


@mcp.tool()
def close_strategy(strategy: str) -> Any:
    """Close every open position held by a strategy."""
    return _request("POST", f"/api/strategies/{strategy}/close")


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
