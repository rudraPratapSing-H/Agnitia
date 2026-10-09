"""Unit tests for Task 3.9: Past incidents data and memory matching"""

import json
from pathlib import Path
import pytest
from backend.agents.memory import match_similar_incident, PAST_INCIDENTS_PATH


def test_past_incidents_json_exists_and_has_five_incidents():
    assert PAST_INCIDENTS_PATH.exists()
    with open(PAST_INCIDENTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) >= 5, f"Expected at least 5 incidents, found {len(data)}"
    
    # Must include INC-087
    inc_087 = next((i for i in data if i["id"] == "INC-087"), None)
    assert inc_087 is not None, "INC-087 must be present in past_incidents.json"
    assert inc_087["root_service"] == "postgres"
    assert "137" in inc_087["summary"] or "137" in inc_087["similarity_keywords"]


def test_match_similar_incident_db_oom():
    match = match_similar_incident("postgres", "Postgres OOMKilled with exit code 137 out of memory")
    assert match is not None
    assert match.id == "INC-087"
    assert match.similarity == 0.94


def test_match_similar_incident_payment():
    match = match_similar_incident("payment-service", "CrashLoopBackOff config error stripe env")
    assert match is not None
    assert match.id == "INC-072"
    assert match.similarity > 0.5
