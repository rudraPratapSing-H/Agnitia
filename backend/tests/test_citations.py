"""Unit tests for Citation Verifier (TASK 2.3)"""

import pytest
from backend.models import RCA, Evidence, LogLine, K8sEvent, MetricPoint
from backend.agents.citations import verify_citations


@pytest.fixture
def sample_telemetry():
    logs = [
        LogLine(line=40, t_s=1.0, text="starting postgres database worker"),
        LogLine(line=41, t_s=2.0, text="allocating query buffer cache memory"),
        LogLine(line=42, t_s=3.0, text="FATAL: out of memory (allocated 67108864 bytes, limit 67108864 bytes)"),
        LogLine(line=43, t_s=4.0, text="server process terminated by signal 9"),
    ]
    events = [
        K8sEvent(t_s=3.5, service="postgres", text="Reason: OOMKilled, Exit Code: 137")
    ]
    metrics = [
        MetricPoint(t_s=1.0, mem_mb=40.0, cpu_pct=10.0),
        MetricPoint(t_s=2.0, mem_mb=55.0, cpu_pct=15.0),
        MetricPoint(t_s=3.0, mem_mb=63.8, cpu_pct=25.0),
        MetricPoint(t_s=3.5, mem_mb=64.0, cpu_pct=30.0),
    ]
    return logs, events, metrics


def test_all_real_citations_verified(sample_telemetry):
    logs, events, metrics = sample_telemetry

    rca = RCA(
        root_cause="PostgreSQL out of memory",
        category="OOMKilled",
        confidence=0.97,
        evidence=[
            Evidence(type="log", source="postgres-0", line=42, text="FATAL: out of memory"),
            Evidence(type="k8s_event", source="postgres-0", text="Reason: OOMKilled, Exit Code: 137"),
            Evidence(type="metric", source="postgres-0", text="memory 63.8Mi of 64Mi limit"),
        ],
    )

    verified_rca = verify_citations(rca, logs, events, metrics)

    # (a) All real citations verified, confidence unchanged, no warning
    assert all(e.verified for e in verified_rca.evidence)
    assert verified_rca.confidence == 0.97
    assert verified_rca.warning is None


def test_planted_fake_log_line(sample_telemetry):
    logs, events, metrics = sample_telemetry

    rca = RCA(
        root_cause="PostgreSQL disk failure",
        category="DiskFailure",
        confidence=0.97,
        evidence=[
            Evidence(type="log", source="postgres-0", line=42, text="FATAL: disk full"),
            Evidence(type="k8s_event", source="postgres-0", text="Reason: OOMKilled, Exit Code: 137"),
        ],
    )

    verified_rca = verify_citations(rca, logs, events, metrics)

    # (b) Planted fake log line flagged, confidence 0.97 becomes 0.77, warning set
    assert verified_rca.evidence[0].verified is False
    assert verified_rca.evidence[1].verified is True
    assert verified_rca.confidence == 0.77
    assert verified_rca.warning is not None
    assert "1 citation(s) could not be verified against the raw data" in verified_rca.warning
    assert "FATAL: disk full" in verified_rca.warning


def test_correct_text_wrong_line_number(sample_telemetry):
    logs, events, metrics = sample_telemetry

    # Text exists at line 42, but evidence claims line 99
    rca = RCA(
        root_cause="PostgreSQL OOM",
        category="OOMKilled",
        confidence=0.95,
        evidence=[
            Evidence(type="log", source="postgres-0", line=99, text="FATAL: out of memory"),
        ],
    )

    verified_rca = verify_citations(rca, logs, events, metrics)

    # (c) Correct text but wrong line number -> flagged
    assert verified_rca.evidence[0].verified is False
    assert verified_rca.confidence == 0.75
    assert verified_rca.warning is not None


def test_whitespace_differences(sample_telemetry):
    logs, events, metrics = sample_telemetry

    # Text has irregular whitespace and newlines
    rca = RCA(
        root_cause="PostgreSQL OOM",
        category="OOMKilled",
        confidence=0.90,
        evidence=[
            Evidence(type="log", source="postgres-0", line=42, text="FATAL:   out \t of \n memory"),
            Evidence(type="k8s_event", source="postgres-0", text="Reason:  OOMKilled,   Exit Code: 137"),
        ],
    )

    verified_rca = verify_citations(rca, logs, events, metrics)

    # (d) Whitespace differences -> still verified
    assert verified_rca.evidence[0].verified is True
    assert verified_rca.evidence[1].verified is True
    assert verified_rca.confidence == 0.90
    assert verified_rca.warning is None


def test_wrong_metric_number(sample_telemetry):
    logs, events, metrics = sample_telemetry

    # Metrics contain 63.8 and 64.0, but evidence claims 999.0
    rca = RCA(
        root_cause="PostgreSQL memory anomaly",
        category="OOMKilled",
        confidence=0.95,
        evidence=[
            Evidence(type="metric", source="postgres-0", text="memory 999.0Mi exceeded"),
        ],
    )

    verified_rca = verify_citations(rca, logs, events, metrics)

    # (e) Wrong metric number -> flagged
    assert verified_rca.evidence[0].verified is False
    assert verified_rca.confidence == 0.75
    assert verified_rca.warning is not None


def test_input_rca_unchanged(sample_telemetry):
    logs, events, metrics = sample_telemetry

    rca = RCA(
        root_cause="PostgreSQL crash",
        category="OOMKilled",
        confidence=0.97,
        evidence=[
            Evidence(type="log", source="postgres-0", line=42, text="FATAL: disk full", verified=False),
        ],
    )

    original_confidence = rca.confidence
    original_warning = rca.warning
    original_ev_verified = rca.evidence[0].verified

    verified_rca = verify_citations(rca, logs, events, metrics)

    # (f) Input RCA object is unchanged after call
    assert rca is not verified_rca
    assert rca.confidence == original_confidence == 0.97
    assert rca.warning == original_warning is None
    assert rca.evidence[0].verified == original_ev_verified is False


def test_confidence_never_below_zero(sample_telemetry):
    logs, events, metrics = sample_telemetry

    rca = RCA(
        root_cause="PostgreSQL crash",
        category="OOMKilled",
        confidence=0.10,
        evidence=[
            Evidence(type="log", source="postgres-0", line=42, text="FATAL: disk full"),
        ],
    )

    verified_rca = verify_citations(rca, logs, events, metrics)

    # (g) Confidence never goes below 0.0
    assert verified_rca.confidence == 0.0


def test_short_evidence_text_unverified(sample_telemetry):
    logs, events, metrics = sample_telemetry

    # Shorter than 5 characters after normalising (e.g. " OOM ") -> 3 chars
    rca = RCA(
        root_cause="PostgreSQL crash",
        category="OOMKilled",
        confidence=0.90,
        evidence=[
            Evidence(type="k8s_event", source="postgres-0", text=" OOM "),
        ],
    )

    verified_rca = verify_citations(rca, logs, events, metrics)

    # Text shorter than 5 chars -> counts as not verified
    assert verified_rca.evidence[0].verified is False
    assert verified_rca.confidence == 0.70


def test_empty_evidence_list(sample_telemetry):
    logs, events, metrics = sample_telemetry

    rca = RCA(
        root_cause="PostgreSQL crash",
        category="OOMKilled",
        confidence=0.85,
        evidence=[],
    )

    verified_rca = verify_citations(rca, logs, events, metrics)

    # Empty evidence list: change nothing except warning = "No evidence cited"
    assert verified_rca.confidence == 0.85
    assert verified_rca.warning == "No evidence cited"


def test_log_without_line_number_verified(sample_telemetry):
    logs, events, metrics = sample_telemetry

    rca = RCA(
        root_cause="PostgreSQL OOM",
        category="OOMKilled",
        confidence=0.90,
        evidence=[
            Evidence(type="log", source="postgres-0", line=None, text="server process terminated"),
        ],
    )

    verified_rca = verify_citations(rca, logs, events, metrics)
    assert verified_rca.evidence[0].verified is True
    assert verified_rca.confidence == 0.90
    assert verified_rca.warning is None


def test_case_sensitivity(sample_telemetry):
    logs, events, metrics = sample_telemetry

    # Text matches in lowercase but not exact case ("fatal: out of memory" vs "FATAL: out of memory")
    rca = RCA(
        root_cause="PostgreSQL OOM",
        category="OOMKilled",
        confidence=0.90,
        evidence=[
            Evidence(type="log", source="postgres-0", line=42, text="fatal: out of memory"),
        ],
    )

    verified_rca = verify_citations(rca, logs, events, metrics)
    assert verified_rca.evidence[0].verified is False
    assert verified_rca.confidence == 0.70
    assert verified_rca.warning is not None


def test_multiple_failures_penalty_applied_once(sample_telemetry):
    logs, events, metrics = sample_telemetry

    rca = RCA(
        root_cause="PostgreSQL failure",
        category="OOMKilled",
        confidence=0.95,
        evidence=[
            Evidence(type="log", source="postgres-0", line=42, text="FATAL: disk full"),
            Evidence(type="metric", source="postgres-0", text="memory 999.0Mi exceeded"),
        ],
    )

    verified_rca = verify_citations(rca, logs, events, metrics)
    # Penalty of 0.2 applied ONCE even when two citations fail
    assert verified_rca.confidence == 0.75
    assert verified_rca.warning is not None
    assert "2 citation(s) could not be verified against the raw data" in verified_rca.warning
    assert "FATAL: disk full" in verified_rca.warning
    assert "memory 999.0Mi exceeded" in verified_rca.warning


def test_metric_cpu_pct_and_boundary(sample_telemetry):
    logs, events, metrics = sample_telemetry

    # Telemetry has cpu_pct=25.0 and mem_mb=63.8
    # 25.05 is within +-0.1 of 25.0
    # 63.7 is within +-0.1 of 63.8 (testing float representation precision)
    rca = RCA(
        root_cause="PostgreSQL resource spike",
        category="OOMKilled",
        confidence=0.90,
        evidence=[
            Evidence(type="metric", source="postgres-0", text="cpu reached 25.05% at peak"),
            Evidence(type="metric", source="postgres-0", text="memory 63.7Mi observed"),
        ],
    )

    verified_rca = verify_citations(rca, logs, events, metrics)
    assert verified_rca.evidence[0].verified is True
    assert verified_rca.evidence[1].verified is True
    assert verified_rca.confidence == 0.90
    assert verified_rca.warning is None


def test_metric_without_number_unverified(sample_telemetry):
    logs, events, metrics = sample_telemetry

    rca = RCA(
        root_cause="PostgreSQL crash",
        category="OOMKilled",
        confidence=0.90,
        evidence=[
            Evidence(type="metric", source="postgres-0", text="memory exhausted without numbers"),
        ],
    )

    verified_rca = verify_citations(rca, logs, events, metrics)
    assert verified_rca.evidence[0].verified is False
    assert verified_rca.confidence == 0.70
    assert verified_rca.warning is not None


def test_deep_copy_evidence_isolation(sample_telemetry):
    logs, events, metrics = sample_telemetry

    ev = Evidence(type="log", source="postgres-0", line=42, text="FATAL: disk full", verified=False)
    rca = RCA(
        root_cause="PostgreSQL crash",
        category="OOMKilled",
        confidence=0.90,
        evidence=[ev],
    )

    verified_rca = verify_citations(rca, logs, events, metrics)
    # Mutating verified_rca evidence directly does not affect input rca
    verified_rca.evidence[0].verified = True
    assert rca.evidence[0].verified is False
    assert rca.evidence[0] is not verified_rca.evidence[0]

