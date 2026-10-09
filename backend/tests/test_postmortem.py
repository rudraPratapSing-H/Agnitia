"""Unit tests for Postmortem Generator (Task 3.4).

Tests:
(a) Output is under 400 words.
(b) A fake answer containing an invented service name fails validation and triggers the fallback.
(c) The fallback contains every section header and the incident id.
(d) An unresolved incident does not crash.
(e) LLM timeout -> fallback.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from backend.agents import llm
from backend.agents.llm import LLMError, LLMTimeout
from backend.agents.postmortem import (
    _calc_duration_s,
    _fallback_postmortem,
    _validate_postmortem,
    write_postmortem,
)
from backend.models import Incident

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE_PATH = FIXTURES_DIR / "incident_db_oom_resolved.json"


@pytest.fixture
def resolved_incident() -> Incident:
    """Loads the resolved db_oom fixture."""
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return Incident.model_validate(data)


VALID_MARKDOWN_POSTMORTEM = """# Incident Postmortem: INC-104

## Summary
At 2026-10-09T03:14:07Z, Agnitia correlated 56 alerts into incident INC-104 for postgres. The incident was resolved at 2026-10-09T03:14:45Z.

## Impact
- **Impacted services (4)**: auth-service, payment-service, api-gateway, web-ui
- **Duration**: 38s

## Timeline
- **+0.0s**: First alert received
- **+0.5s**: Alerts correlated into INC-104 (root: postgres)
- **+4.2s**: RCA completed: OOMKilled isolated on postgres-0
- **+12.0s**: Playbook approved by sre-lead
- **+38.0s**: Incident resolved: all services healthy

## Root cause
PostgreSQL was killed for exceeding its 64Mi memory limit.
Evidence:
- Reason: OOMKilled, Exit Code: 137
- Line 42: FATAL: out of memory
- Memory 63.8Mi of 64Mi limit at 03:14:05

## Resolution steps
1. patch_memory_limit on postgres from 64Mi to 256Mi
2. wait_for_ready on postgres (timeout 30)
3. rollout_restart on auth-service
4. rollout_restart on payment-service
5. verify_health on api-gateway

## What went well
Topological correlation quickly identified postgres as the root failure. Automated dependency ordering ensured clean recovery.

## Action items
1. **Platform engineer**: Increase standard memory limits for database deployments.
2. **Site Reliability Engineer**: Create saturation alerting at 80% threshold.
3. **Software engineer**: Implement connection pool backoff in dependent services.
"""


# ── (a) Output under 400 words ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_postmortem_output_under_400_words(monkeypatch, resolved_incident):
    """(a) Test that write_postmortem returns markdown under 400 words with required headers."""
    async def fake_call_text(prompt, payload, *, timeout_s=8.0):
        return VALID_MARKDOWN_POSTMORTEM

    monkeypatch.setattr(llm, "call_text", fake_call_text)

    result = await write_postmortem(resolved_incident)

    word_count = len(result.split())
    assert word_count <= 400
    assert "INC-104" in result
    for header in [
        "Summary",
        "Impact",
        "Timeline",
        "Root cause",
        "Resolution steps",
        "What went well",
        "Action items",
    ]:
        assert header.lower() in result.lower(), f"Missing required header: {header}"


# ── (b) Invented service name triggers fallback ───────────────────────────────


@pytest.mark.asyncio
async def test_invented_service_name_triggers_fallback(monkeypatch, resolved_incident):
    """(b) A fake answer containing an invented service name fails validation and triggers fallback."""
    fake_hallucinated_text = VALID_MARKDOWN_POSTMORTEM.replace(
        "web-ui", "billing-service"
    )

    call_count = 0

    async def fake_call_text(prompt, payload, *, timeout_s=8.0):
        nonlocal call_count
        call_count += 1
        return fake_hallucinated_text

    monkeypatch.setattr(llm, "call_text", fake_call_text)

    result = await write_postmortem(resolved_incident)

    # Initial call + 1 retry = 2 calls
    assert call_count == 2
    # The returned output must be the fallback, and MUST NOT contain the hallucinated service
    assert "billing-service" not in result
    assert "INC-104" in result
    assert "Action items" in result


# ── (c) Fallback contains every section header and incident id ────────────────


def test_fallback_contains_every_header_and_incident_id(resolved_incident):
    """(c) The fallback contains every required section header and the incident ID."""
    facts = resolved_incident.model_dump(mode="json")
    facts["duration_s"] = _calc_duration_s(resolved_incident.started_at, resolved_incident.resolved_at)
    facts["impacted_count"] = len(resolved_incident.impacted_services)

    fallback = _fallback_postmortem(resolved_incident, facts)

    assert "INC-104" in fallback
    for header in [
        "## Summary",
        "## Impact",
        "## Timeline",
        "## Root cause",
        "## Resolution steps",
        "## What went well",
        "## Action items",
    ]:
        assert header.lower() in fallback.lower(), f"Fallback missing header: {header}"

    assert len(fallback.split()) <= 400
    # Fallback itself passes factual validation against facts
    assert _validate_postmortem(fallback, facts) is True


# ── (d) Unresolved incident does not crash ───────────────────────────────────


@pytest.mark.asyncio
async def test_unresolved_incident_does_not_crash(monkeypatch, resolved_incident):
    """(d) An unresolved incident does not crash, duration is handled gracefully."""
    unresolved_inc = resolved_incident.model_copy(deep=True)
    unresolved_inc.resolved_at = None
    unresolved_inc.status = "analyzing"

    async def fake_call_text(prompt, payload, *, timeout_s=8.0):
        # Verify facts has duration_s as None
        assert payload.get("duration_s") is None
        raise LLMError("Simulated offline fallback")

    monkeypatch.setattr(llm, "call_text", fake_call_text)

    result = await write_postmortem(unresolved_inc)

    assert "INC-104" in result
    assert "unresolved" in result.lower() or "ongoing" in result.lower()
    assert len(result.split()) <= 400


# ── (e) LLM timeout -> fallback ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_llm_timeout_triggers_fallback(monkeypatch, resolved_incident):
    """(e) LLM timeout triggers the fallback template without crashing."""
    async def fake_timeout(prompt, payload, *, timeout_s=8.0):
        raise LLMTimeout("Model timed out after 8.0s")

    monkeypatch.setattr(llm, "call_text", fake_timeout)

    result = await write_postmortem(resolved_incident)

    assert "INC-104" in result
    assert "## Root cause" in result
    assert len(result.split()) <= 400


# ── Additional edge cases ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invented_number_triggers_fallback(monkeypatch, resolved_incident):
    """An invented number outside Action items triggers fallback."""
    hallucinated_number_text = VALID_MARKDOWN_POSTMORTEM.replace(
        "56 alerts", "9999 alerts"
    )

    async def fake_call_text(prompt, payload, *, timeout_s=8.0):
        return hallucinated_number_text

    monkeypatch.setattr(llm, "call_text", fake_call_text)

    result = await write_postmortem(resolved_incident)
    assert "9999" not in result
    assert "INC-104" in result


@pytest.mark.asyncio
async def test_validation_retry_success(monkeypatch, resolved_incident):
    """If first call fails validation but retry succeeds, returns retry result."""
    attempts = 0

    async def fake_call_text(prompt, payload, *, timeout_s=8.0):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return "Too short"  # Fails validation
        return VALID_MARKDOWN_POSTMORTEM  # Succeeds on retry

    monkeypatch.setattr(llm, "call_text", fake_call_text)

    result = await write_postmortem(resolved_incident)
    assert attempts == 2
    assert "Topological correlation quickly identified" in result
