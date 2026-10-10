"""Agnitia Model Context Protocol (MCP) Server.

TASK 3.6 (Member 3):
- Exposes Agnitia to Claude Desktop and external assistants via Model Context Protocol (MCP).
- Uses MCP Python SDK (FastMCP / MCPServer) with stdio transport.
- Thin client over REST API using BACKEND_URL (default http://localhost:8000) and httpx.
- Tools:
    1. list_open_incidents(): GET /api/incidents/latest; return [that incident] if not "resolved", else [].
    2. get_incident_summary(): id, status, root_service, impacted_services, rca.root_cause, rca.confidence, playbook diff.
    3. get_blast_radius(service: str): GET /api/blast-radius/{service}.
    4. get_postmortem(incident_id: str): GET /api/incidents/{id}/postmortem, return the markdown.
    5. request_fix(incident_id: str): does NOT approve anything. Returns proposed playbook steps, diff,
       and message "Human approval required: approve in the Agnitia UI or the Telegram bot".
- Returns clear error strings when backend is unreachable, never stack traces.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

try:
    from mcp.server import MCPServer as FastMCP
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        from mcp.server.mcpserver import MCPServer as FastMCP

BACKEND_URL: str = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")

mcp = FastMCP("OpsOracle")


@mcp.tool()
async def list_open_incidents() -> list[dict[str, Any]] | str:
    """Returns currently open (unresolved) incidents from Agnitia."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BACKEND_URL}/api/incidents/latest")
            if resp.status_code != 200:
                return f"Error: Backend returned HTTP {resp.status_code}"
            data = resp.json()
            if not data or not isinstance(data, dict):
                return []
            if data.get("status") != "resolved":
                return [data]
            return []
    except Exception as exc:
        return f"Error: Backend unreachable at {BACKEND_URL} ({exc})"


@mcp.tool()
async def get_incident_summary() -> dict[str, Any] | str:
    """Returns a summary of the latest incident including RCA and playbook diff."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BACKEND_URL}/api/incidents/latest")
            if resp.status_code != 200:
                return f"Error: Backend returned HTTP {resp.status_code}"
            data = resp.json()
            if not data or not isinstance(data, dict):
                return "No active incident found."

            rca = data.get("rca") or {}
            playbook = data.get("playbook") or {}

            return {
                "id": data.get("id"),
                "status": data.get("status"),
                "root_service": data.get("root_service"),
                "impacted_services": data.get("impacted_services", []),
                "rca": {
                    "root_cause": rca.get("root_cause"),
                    "confidence": rca.get("confidence"),
                },
                "root_cause": rca.get("root_cause"),
                "confidence": rca.get("confidence"),
                "diff": playbook.get("diff"),
                "playbook_diff": playbook.get("diff"),
            }
    except Exception as exc:
        return f"Error: Backend unreachable at {BACKEND_URL} ({exc})"


@mcp.tool()
async def get_blast_radius(service: str) -> dict[str, Any] | str:
    """Calculates downstream blast radius and affected users if a service fails."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BACKEND_URL}/api/blast-radius/{service}")
            if resp.status_code != 200:
                return f"Error: Backend returned HTTP {resp.status_code}: {resp.text}"
            return resp.json()
    except Exception as exc:
        return f"Error: Backend unreachable at {BACKEND_URL} ({exc})"


@mcp.tool()
async def get_postmortem(incident_id: str) -> str:
    """Returns the generated markdown postmortem for an incident."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BACKEND_URL}/api/incidents/{incident_id}/postmortem")
            if resp.status_code != 200:
                return f"Error: Backend returned HTTP {resp.status_code}: {resp.text}"
            content_type = resp.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    data = resp.json()
                    if isinstance(data, dict):
                        return data.get("postmortem") or data.get("markdown") or str(data)
                    return str(data)
                except Exception:
                    pass
            return resp.text
    except Exception as exc:
        return f"Error: Backend unreachable at {BACKEND_URL} ({exc})"


@mcp.tool()
async def request_fix(incident_id: str) -> dict[str, Any] | str:
    """Returns proposed remediation steps and diff. Does NOT auto-approve; requires human approval."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BACKEND_URL}/api/incidents/latest")
            if resp.status_code != 200:
                return f"Error: Backend returned HTTP {resp.status_code}"
            data = resp.json()
            if not data or not isinstance(data, dict):
                return f"Error: Incident '{incident_id}' not found."

            current_id = data.get("id")
            if incident_id not in (current_id, "latest", "current"):
                return (
                    f"Error: Incident '{incident_id}' not found. "
                    f"Current active incident is '{current_id}'."
                )

            playbook = data.get("playbook") or {}
            steps = playbook.get("steps", [])
            diff = playbook.get("diff", "")

            return {
                "incident_id": current_id,
                "steps": steps,
                "diff": diff,
                "message": "Human approval required: approve in the OpsOracle UI or the Telegram bot",
            }
    except Exception as exc:
        return f"Error: Backend unreachable at {BACKEND_URL} ({exc})"


if __name__ == "__main__":
    mcp.run(transport="stdio")
