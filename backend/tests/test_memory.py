"""Unit tests for Incident Memory Matching (Task 3.5).

Tests:
(a) An OOMKilled-on-postgres RCA matches INC-087 with the highest score.
(b) A CrashLoopBackOff RCA on payment-service does not match INC-087.
(c) A missing file returns None (never raises).
(d) Ties pick the first entry in the file.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from backend.agents import memory
from backend.agents.memory import (
    clear_cache,
    find_similar,
    jaccard,
    tokenize,
)
from backend.models import RCA

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
TEST_FIXTURE_PATH = FIXTURES_DIR / "past_incidents_test.json"


@pytest.fixture(autouse=True)
def setup_memory_fixture(monkeypatch):
    """Point PAST_INCIDENTS_PATH to past_incidents_test.json and clear cache."""
    clear_cache()
    monkeypatch.setattr(memory, "PAST_INCIDENTS_PATH", TEST_FIXTURE_PATH)
    yield
    clear_cache()


# ── (a) OOMKilled on postgres matches INC-087 ────────────────────────────────


def test_oomkilled_postgres_matches_inc_087():
    """(a) An OOMKilled-on-postgres RCA matches INC-087 with score >= 0.6."""
    rca = RCA(
        root_cause="PostgreSQL was killed for exceeding its 64Mi memory limit",
        category="OOMKilled",
        confidence=0.97,
    )

    match = find_similar(rca, "postgres")
    assert match is not None
    assert match.id == "INC-087"
    assert match.similarity >= 0.6
    assert match.similarity == 0.86


def test_oomkilled_postgres_db_oom_scenario_variant():
    """Variant with the real simulator/cached text also matches INC-087."""
    rca = RCA(
        root_cause="The postgres-0 pod exceeded its memory limit and was terminated with exit code 137 (OOMKilled).",
        category="OOMKilled",
        confidence=1.0,
    )

    match = find_similar(rca, "postgres")
    assert match is not None
    assert match.id == "INC-087"
    assert match.similarity >= 0.6


# ── (b) CrashLoopBackOff on payment-service does not match INC-087 ─────────────


def test_crashloop_payment_service_does_not_match_inc_087():
    """(b) A CrashLoopBackOff RCA on payment-service does not match INC-087."""
    rca = RCA(
        root_cause="The payment-service failed to start due to missing environment variable, causing CrashLoopBackOff.",
        category="CrashLoopBackOff",
        confidence=0.95,
    )

    match = find_similar(rca, "payment-service")
    # Must NOT match INC-087 (which is postgres OOMKilled)
    if match is not None:
        assert match.id != "INC-087"


# ── (c) Missing or invalid file returns None ──────────────────────────────────


def test_missing_file_returns_none(monkeypatch, tmp_path):
    """(c) A missing file returns None and never raises an exception."""
    missing_path = tmp_path / "does_not_exist.json"
    monkeypatch.setattr(memory, "PAST_INCIDENTS_PATH", missing_path)

    rca = RCA(
        root_cause="PostgreSQL was killed for exceeding its 64Mi memory limit",
        category="OOMKilled",
        confidence=0.97,
    )

    result = find_similar(rca, "postgres")
    assert result is None


def test_corrupted_file_returns_none(monkeypatch, tmp_path):
    """A corrupted/invalid JSON file returns None and never raises."""
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("NOT VALID JSON {{{", encoding="utf-8")
    monkeypatch.setattr(memory, "PAST_INCIDENTS_PATH", corrupt_file)

    rca = RCA(
        root_cause="PostgreSQL was killed for exceeding its 64Mi memory limit",
        category="OOMKilled",
        confidence=0.97,
    )

    result = find_similar(rca, "postgres")
    assert result is None


# ── (d) Ties pick the first entry in the file ─────────────────────────────────


def test_ties_pick_first_entry(monkeypatch, tmp_path):
    """(d) When two past incidents yield identical scores, the first entry is chosen."""
    tied_incidents = [
        {
            "id": "TIE-001",
            "title": "PostgreSQL memory exhaustion A",
            "root_service": "postgres",
            "category": "OOMKilled",
            "root_cause": "PostgreSQL was killed for exceeding its 64Mi memory limit",
            "keywords": ["postgres", "oomkilled", "memory", "limit"],
        },
        {
            "id": "TIE-002",
            "title": "PostgreSQL memory exhaustion B",
            "root_service": "postgres",
            "category": "OOMKilled",
            "root_cause": "PostgreSQL was killed for exceeding its 64Mi memory limit",
            "keywords": ["postgres", "oomkilled", "memory", "limit"],
        },
    ]
    tied_file = tmp_path / "tied_incidents.json"
    tied_file.write_text(json.dumps(tied_incidents), encoding="utf-8")
    monkeypatch.setattr(memory, "PAST_INCIDENTS_PATH", tied_file)

    rca = RCA(
        root_cause="PostgreSQL was killed for exceeding its 64Mi memory limit",
        category="OOMKilled",
        confidence=0.97,
    )

    match = find_similar(rca, "postgres")
    assert match is not None
    assert match.id == "TIE-001"


# ── Helper functions: Tokenizer & Jaccard ─────────────────────────────────────


def test_tokenizer_drops_stop_words_and_splits_non_alphanumeric():
    """Tokenizer lower-cases, splits on non-alphanumerics, and drops the 11 stop words."""
    text = "The postgres was killed for its 64Mi limit, and a memory bug on web-ui of 137 by root to data in container!"
    tokens = tokenize(text)

    # Stop words dropped: the, was, for, its, a, of, by, to, in, on, and
    for sw in ["the", "was", "for", "its", "a", "of", "by", "to", "in", "on", "and"]:
        assert sw not in tokens

    # Expected tokens
    for expected in ["postgres", "killed", "64mi", "limit", "memory", "bug", "web", "ui", "137", "root", "data", "container"]:
        assert expected in tokens


def test_jaccard_similarity_calculation():
    """Jaccard correctly computes intersection over union."""
    set1 = {"postgres", "memory", "oom"}
    set2 = {"postgres", "memory", "crash"}
    # intersection: {postgres, memory} = 2
    # union: {postgres, memory, oom, crash} = 4
    # jaccard = 2/4 = 0.5
    assert jaccard(set1, set2) == 0.5

    assert jaccard(set(), set2) == 0.0
    assert jaccard(set(), set()) == 0.0


def test_score_below_threshold_returns_none(monkeypatch, tmp_path):
    """An incident scoring below 0.6 returns None."""
    unrelated_incidents = [
        {
            "id": "INC-999",
            "title": "Unrelated redis error",
            "root_service": "redis",
            "category": "NetworkTimeout",
            "root_cause": "Packet loss across redis cluster",
            "keywords": ["redis", "network", "timeout"],
        }
    ]
    unrelated_file = tmp_path / "unrelated.json"
    unrelated_file.write_text(json.dumps(unrelated_incidents), encoding="utf-8")
    monkeypatch.setattr(memory, "PAST_INCIDENTS_PATH", unrelated_file)

    rca = RCA(
        root_cause="PostgreSQL memory allocation failure",
        category="OOMKilled",
        confidence=0.9,
    )

    match = find_similar(rca, "postgres")
    assert match is None
