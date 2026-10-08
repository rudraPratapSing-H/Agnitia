"""Agnitia Model Context Protocol (MCP) Server

Exposes tools for external LLM assistants (e.g. Claude Desktop) to query active incidents,
inspect topology, and trigger remediation playbooks.
"""

import httpx

AGNITIA_URL = "http://localhost:8000"


async def list_open_incidents():
    """Returns the currently active incident in Agnitia."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{AGNITIA_URL}/api/incidents/latest")
            return resp.json()
        except Exception as e:
            return {"error": str(e)}


async def approve_incident_playbook(incident_id: str):
    """Authorizes the recovery playbook for an incident."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{AGNITIA_URL}/api/incidents/{incident_id}/approve",
                json={"approved_by": "mcp-agent"},
            )
            return resp.json()
        except Exception as e:
            return {"error": str(e)}


async def get_service_blast_radius(service: str):
    """Calculates downstream services affected if a service fails."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{AGNITIA_URL}/api/blast-radius/{service}")
            return resp.json()
        except Exception as e:
            return {"error": str(e)}


if __name__ == "__main__":
    print("Agnitia MCP Server initialized. Ready for tool calls.")
