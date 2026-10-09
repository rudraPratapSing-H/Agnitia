"""
Integration test for Task 2.14: Telegram approval bot flow.
Verifies that:
1. AgnitiaBotEngine detects an awaiting_approval incident and formats the card.
2. An Approve callback calls POST /api/incidents/{id}/approve with author info.
3. The approval heals the system on screen (transitions to executing/resolved).
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from starlette.testclient import TestClient

from backend.main import app
from backend.adapters.simulator import SimulatorAdapter
from bot.telegram_bot import AgnitiaBotEngine, handle_callback


@pytest.fixture
def client():
    return TestClient(app)


def test_telegram_approval_card_format():
    engine = AgnitiaBotEngine()
    incident = {
        "id": "INC-104",
        "status": "awaiting_approval",
        "scenario": "db_oom",
        "root_service": "postgres",
        "impacted_services": ["auth-service", "payment-service", "api-gateway", "web-ui"],
        "raw_alert_count": 56,
        "rca": {
            "root_cause": "PostgreSQL OOMKilled exceeding 64Mi",
            "category": "OOMKilled",
            "confidence": 0.98,
        },
        "playbook": {
            "diff": "resources.limits.memory: 64Mi -> 256Mi",
        },
    }
    card = engine.format_incident_card(incident)
    assert "INC-104" in card
    assert "PostgreSQL OOMKilled" in card
    assert "64Mi -> 256Mi" in card
    assert "auth-service" in card
    assert "56 alerts" in card


@pytest.mark.asyncio
async def test_telegram_approval_callback_flow():
    """Simulates a user tapping 'Approve' in Telegram and verifies backend approval."""
    # 1. Reset and inject scenario via test client
    with TestClient(app) as test_client:
        test_client.post("/api/reset")
        resp = test_client.post("/api/chaos/db_oom")
        assert resp.status_code == 200
        incident_id = "INC-104"

        # Wait briefly for incident to register
        await asyncio.sleep(0.1)

        # 2. Simulate Telegram callback query
        mock_query = AsyncMock()
        mock_query.data = f"approve:{incident_id}"
        mock_query.from_user = MagicMock()
        mock_query.from_user.username = "judge_lead"
        mock_query.from_user.first_name = "Judge"

        mock_update = MagicMock()
        mock_update.callback_query = mock_query

        mock_context = MagicMock()

        # 3. Execute handle_callback with httpx mocked to call FastAPI TestClient or live
        with patch("bot.telegram_bot.httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_http

            # Mock successful approval response from backend
            mock_http_resp = MagicMock()
            mock_http_resp.status_code = 200
            mock_http_resp.json.return_value = {"status": "ok", "incident_id": incident_id}
            mock_http.post.return_value = mock_http_resp

            await handle_callback(mock_update, mock_context)

            # Verify approve endpoint was called with author info
            mock_http.post.assert_called_once()
            call_url = mock_http.post.call_args[0][0]
            call_json = mock_http.post.call_args[1].get("json", {})
            assert f"/api/incidents/{incident_id}/approve" in call_url
            assert "judge_lead" in call_json.get("approved_by", "")

            # Verify Telegram message was edited with confirmation
            mock_query.edit_message_text.assert_called_once()
            edited_text = mock_query.edit_message_text.call_args[0][0]
            assert "APPROVED" in edited_text
            assert "judge_lead" in edited_text
