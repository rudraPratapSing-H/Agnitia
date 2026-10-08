"""Unit tests for Pydantic models against CONTRACT.md specifications"""

import json
import re
from pathlib import Path
import pytest
from pydantic import ValidationError

from backend.models import (
    ServiceNode,
    ServiceMetrics,
    Alert,
    Evidence,
    SimilarIncident,
    RCA,
    PlaybookStep,
    Playbook,
    TimelineEntry,
    Incident,
    WsEvent,
    LogLine,
    MetricPoint,
    K8sEvent,
    ActionResult,
    Scenario,
)


def strip_jsonc_comments(text: str) -> str:
    """Removes single-line // comments from JSONC text."""
    lines = []
    for line in text.splitlines():
        # Strip trailing // comments while preserving strings without //
        cleaned = re.sub(r"\s*//.*$", "", line)
        lines.append(cleaned)
    return "\n".join(lines)


# Raw JSONC snippets from CONTRACT.md
SERVICE_NODE_JSONC = """
{
  "id": "postgres",
  "label": "PostgreSQL",
  "tier": "data",                 // data | backend | edge | frontend
  "depends_on": [],
  "status": "healthy",            // healthy | root_cause | impacted | recovering
  "metrics": { "mem_mb": 58, "mem_limit_mb": 64, "cpu_pct": 12, "restarts": 0 }
}
"""

ALERT_JSONC = """
{
  "id": "a-017",
  "ts": "2026-10-09T03:14:09Z",
  "service": "api-gateway",
  "severity": "critical",
  "message": "502 Bad Gateway: upstream auth-service unavailable",
  "incident_id": "INC-104"
}
"""

INCIDENT_JSONC = """
{
  "id": "INC-104",
  "status": "awaiting_approval",  // detected | analyzing | awaiting_approval | healing | resolved
  "scenario": "db_oom",
  "root_service": "postgres",
  "impacted_services": ["auth-service", "payment-service", "api-gateway", "web-ui"],
  "raw_alert_count": 56,
  "started_at": "2026-10-09T03:14:07Z",
  "resolved_at": null,
  "rca": {
    "root_cause": "PostgreSQL was killed for exceeding its 64Mi memory limit",
    "category": "OOMKilled",
    "confidence": 0.97,
    "evidence": [
      { "type": "k8s_event", "source": "postgres-0", "text": "Reason: OOMKilled, Exit Code: 137", "verified": true },
      { "type": "log", "source": "postgres-0", "line": 42, "text": "FATAL: out of memory", "verified": true },
      { "type": "metric", "source": "postgres-0", "text": "memory 63.8Mi of 64Mi limit at 03:14:05", "verified": true }
    ],
    "similar_incident": { "id": "INC-087", "similarity": 0.94 },   // Feature 17, optional
    "warning": null
  },
  "playbook": {
    "diff": "resources.limits.memory: 64Mi -> 256Mi",
    "steps": [
      { "order": 1, "service": "postgres", "action": "patch_memory_limit", "params": { "from": "64Mi", "to": "256Mi" }, "risk": "high", "requires_approval": true, "verify": "port 5432 accepting connections" },
      { "order": 2, "service": "postgres", "action": "wait_for_ready", "params": { "timeout_s": 30 }, "risk": "low", "requires_approval": false, "verify": "readiness probe passes" },
      { "order": 3, "service": "auth-service", "action": "rollout_restart", "risk": "low", "requires_approval": false, "verify": "health endpoint 200" },
      { "order": 4, "service": "payment-service", "action": "rollout_restart", "risk": "low", "requires_approval": false, "verify": "health endpoint 200" },
      { "order": 5, "service": "api-gateway", "action": "verify_health", "risk": "low", "requires_approval": false, "verify": "error rate below 1%" }
    ]
  },
  "timeline": [ { "t_s": 0, "event": "First alert received" } ]
}
"""

WS_EVENT_JSONC = """
{ "type": "agent_step", "ts": "2026-10-09T03:14:11Z", "payload": { "agent": "diagnose", "text": "Reading last 50 log lines from postgres-0", "status": "running" } }
"""


def test_service_node_validation_and_roundtrip():
    clean_json = strip_jsonc_comments(SERVICE_NODE_JSONC)
    raw_data = json.loads(clean_json)

    node = ServiceNode.model_validate(raw_data)
    assert node.id == "postgres"
    assert node.tier == "data"
    assert node.status == "healthy"
    assert node.metrics.mem_mb == 58.0
    assert node.metrics.restarts == 0

    # Round-trip validation
    dumped = node.model_dump()
    node_rt = ServiceNode.model_validate(dumped)
    assert node == node_rt

    # JSON round-trip
    json_rt = node.model_dump_json()
    assert ServiceNode.model_validate_json(json_rt) == node


def test_alert_validation_and_roundtrip():
    clean_json = strip_jsonc_comments(ALERT_JSONC)
    raw_data = json.loads(clean_json)

    alert = Alert.model_validate(raw_data)
    assert alert.id == "a-017"
    assert alert.service == "api-gateway"
    assert alert.severity == "critical"
    assert alert.incident_id == "INC-104"

    # Round-trip validation
    dumped = alert.model_dump()
    alert_rt = Alert.model_validate(dumped)
    assert alert == alert_rt

    json_rt = alert.model_dump_json()
    assert Alert.model_validate_json(json_rt) == alert


def test_incident_validation_and_roundtrip():
    clean_json = strip_jsonc_comments(INCIDENT_JSONC)
    raw_data = json.loads(clean_json)

    incident = Incident.model_validate(raw_data)
    assert incident.id == "INC-104"
    assert incident.status == "awaiting_approval"
    assert incident.scenario == "db_oom"
    assert incident.root_service == "postgres"
    assert len(incident.impacted_services) == 4
    assert incident.raw_alert_count == 56

    assert incident.rca is not None
    assert incident.rca.category == "OOMKilled"
    assert incident.rca.confidence == 0.97
    assert len(incident.rca.evidence) == 3
    assert incident.rca.evidence[0].verified is True
    assert incident.rca.evidence[1].line == 42
    assert incident.rca.similar_incident is not None
    assert incident.rca.similar_incident.id == "INC-087"
    assert incident.rca.warning is None

    assert incident.playbook is not None
    assert incident.playbook.diff == "resources.limits.memory: 64Mi -> 256Mi"
    assert len(incident.playbook.steps) == 5
    assert incident.playbook.steps[0].risk == "high"
    assert incident.playbook.steps[0].requires_approval is True
    assert incident.playbook.steps[2].params is None

    assert len(incident.timeline) == 1
    assert incident.timeline[0].event == "First alert received"

    # Round-trip validation
    dumped = incident.model_dump()
    incident_rt = Incident.model_validate(dumped)
    assert incident == incident_rt

    json_rt = incident.model_dump_json()
    assert Incident.model_validate_json(json_rt) == incident


def test_ws_event_validation_and_roundtrip():
    clean_json = strip_jsonc_comments(WS_EVENT_JSONC)
    raw_data = json.loads(clean_json)

    event = WsEvent.model_validate(raw_data)
    assert event.type == "agent_step"
    assert event.payload["agent"] == "diagnose"
    assert event.payload["status"] == "running"

    # Round-trip validation
    dumped = event.model_dump()
    event_rt = WsEvent.model_validate(dumped)
    assert event == event_rt

    json_rt = event.model_dump_json()
    assert WsEvent.model_validate_json(json_rt) == event


def test_extra_fields_forbidden():
    # ServiceNode extra field
    with pytest.raises(ValidationError):
        ServiceNode(
            id="test",
            label="Test",
            tier="backend",
            metrics=ServiceMetrics(mem_mb=10, mem_limit_mb=64, cpu_pct=5, restarts=0),
            unknown_extra_field="bad",
        )

    # Alert extra field
    with pytest.raises(ValidationError):
        Alert(
            id="a-1",
            ts="2026-10-09T03:14:09Z",
            service="web-ui",
            severity="error",
            message="err",
            bad_field=True,
        )

    # Evidence extra field
    with pytest.raises(ValidationError):
        Evidence(
            type="log",
            source="postgres-0",
            text="fatal error",
            fake_field="disallowed",
        )


def test_supporting_types():
    # LogLine
    log = LogLine(line=42, t_s=6.0, text="FATAL: out of memory")
    assert log.line == 42
    assert LogLine.model_validate(log.model_dump()) == log

    # MetricPoint
    mp = MetricPoint(t_s=0.5, mem_mb=40.0, cpu_pct=12.0)
    assert mp.mem_mb == 40.0
    assert MetricPoint.model_validate(mp.model_dump()) == mp

    # K8sEvent
    ev = K8sEvent(t_s=6.0, service="postgres", text="Reason: OOMKilled, Exit Code: 137")
    assert ev.service == "postgres"
    assert K8sEvent.model_validate(ev.model_dump()) == ev

    # ActionResult
    res = ActionResult(ok=True, message="Memory patched")
    assert res.ok is True
    assert ActionResult.model_validate(res.model_dump()) == res


def test_extract_and_validate_contract_file():
    """Reads CONTRACT.md directly from disk, extracts all jsonc blocks, and asserts they validate."""
    contract_path = Path(__file__).resolve().parent.parent.parent / "CONTRACT.md"
    assert contract_path.exists(), "CONTRACT.md not found in repo root"

    content = contract_path.read_text(encoding="utf-8")
    blocks = re.findall(r"```jsonc\s*\n(.*?)\n```", content, re.DOTALL)
    assert len(blocks) >= 4, "Expected at least 4 jsonc blocks in CONTRACT.md"

    # Block 0: Service node
    node_data = json.loads(strip_jsonc_comments(blocks[0]))
    ServiceNode.model_validate(node_data)

    # Block 1: Alert
    alert_data = json.loads(strip_jsonc_comments(blocks[1]))
    Alert.model_validate(alert_data)

    # Block 2: Incident
    incident_data = json.loads(strip_jsonc_comments(blocks[2]))
    Incident.model_validate(incident_data)

    # Block 3: WsEvent
    ws_data = json.loads(strip_jsonc_comments(blocks[3]))
    WsEvent.model_validate(ws_data)

    # Block 4: Scenario (from Interfaces section)
    if len(blocks) >= 5:
        scenario_data = json.loads(strip_jsonc_comments(blocks[4]))
        Scenario.model_validate(scenario_data)
