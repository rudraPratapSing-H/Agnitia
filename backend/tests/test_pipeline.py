"""Tests for the agent pipeline and its demo-mode fallback (tasks 2.1 + 2.4)."""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import backend.agents.pipeline as pipeline
from backend.agents import llm
from backend.agents.planner import DEFAULT_SERVICES
from backend.models import Incident, K8sEvent, LogLine, MetricPoint, Playbook, RCA

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_DIR = REPO_ROOT / "backend" / "scenarios"

CACHED_ROOT_CAUSE = "PostgreSQL was killed for exceeding its 64Mi memory limit"
LIVE_ROOT_CAUSE = "PostgreSQL exceeded its 64Mi memory limit and was OOMKilled (fake model)"


# ── fakes ────────────────────────────────────────────────────────────────────


class FakeAdapter:
    """Reads backend/scenarios/<id>.json and serves it like a finished incident."""

    def __init__(self, scenario: str = "db_oom"):
        self.data = json.loads((SCENARIOS_DIR / f"{scenario}.json").read_text(encoding="utf-8"))

    async def list_services(self):
        return [s.model_copy(deep=True) for s in DEFAULT_SERVICES]

    async def get_logs(self, service, lines=50):
        return [LogLine.model_validate(x) for x in self.data["logs"].get(service, [])][-lines:]

    async def get_metrics(self, service):
        return [MetricPoint.model_validate(x) for x in self.data["metrics"].get(service, [])]

    async def get_events(self, service):
        return [K8sEvent.model_validate(x) for x in self.data["events"] if x["service"] == service]

    async def apply_action(self, step):
        raise NotImplementedError

    async def probe(self, service):
        return True


def live_rca(*, planted_fake_log: bool = False) -> RCA:
    log_text = "FATAL: planted line that never happened" if planted_fake_log else "FATAL: out of memory"
    return RCA.model_validate(
        {
            "root_cause": LIVE_ROOT_CAUSE,
            "category": "OOMKilled",
            "confidence": 0.97,
            "evidence": [
                {"type": "k8s_event", "source": "postgres-0", "text": "Reason: OOMKilled, Exit Code: 137"},
                {"type": "log", "source": "postgres-0", "line": 42, "text": log_text},
                {"type": "metric", "source": "postgres-0", "text": "memory 64.0Mi of 64Mi limit"},
            ],
            "similar_incident": {"id": "INC-999", "similarity": 0.99},  # invented: must be discarded
        }
    )


def live_playbook() -> Playbook:
    """Deliberately misordered: the planner must put postgres first."""
    return Playbook.model_validate(
        {
            "steps": [
                {"order": 1, "service": "auth-service", "action": "rollout_restart", "verify": "health 200"},
                {"order": 2, "service": "postgres", "action": "patch_memory_limit",
                 "params": {"from": "64Mi", "to": "256Mi"}, "verify": "port 5432 accepting connections"},
                {"order": 3, "service": "postgres", "action": "wait_for_ready", "params": {"timeout_s": 30}},
                {"order": 4, "service": "payment-service", "action": "rollout_restart"},
                {"order": 5, "service": "api-gateway", "action": "verify_health"},
            ]
        }
    )


class FakeLLM:
    """Stands in for llm.call_json. behaviour: ok | raise | sleep; fail_on limits it to a model class."""

    def __init__(self, behaviour="ok", fail_on=None, planted_fake_log=False):
        self.behaviour = behaviour
        self.fail_on = fail_on
        self.planted_fake_log = planted_fake_log
        self.calls = []

    async def __call__(self, system_prompt, payload, model_cls, *, timeout_s=4.0):
        self.calls.append(model_cls.__name__)
        if self.behaviour != "ok" and self.fail_on in (None, model_cls.__name__):
            if self.behaviour == "raise":
                raise llm.LLMError("boom")
            await asyncio.sleep(5)
        if model_cls is RCA:
            return live_rca(planted_fake_log=self.planted_fake_log)
        return live_playbook()


# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def env(monkeypatch):
    """Hermetic: no real LLM, instant pacing, DEMO_MODE=auto, events captured."""
    monkeypatch.setenv("DEMO_MODE", "auto")
    monkeypatch.setattr(pipeline, "STEP_PACE_S", (0.0, 0.0))
    fake = FakeLLM("raise")  # safe default: a test that forgets to install its own fake never hits the network
    monkeypatch.setattr(llm, "call_json", fake)
    events = []

    async def fake_emit(event_type, payload):
        events.append((event_type, payload))

    monkeypatch.setattr(pipeline, "emit", fake_emit)
    return events


@pytest.fixture
def install_llm(monkeypatch):
    def _install(*args, **kwargs):
        fake = FakeLLM(*args, **kwargs)
        monkeypatch.setattr(llm, "call_json", fake)
        return fake

    return _install


def make_incident(**overrides) -> Incident:
    data = dict(
        id="INC-104",
        status="analyzing",
        scenario="db_oom",
        root_service="postgres",
        impacted_services=["auth-service", "payment-service", "api-gateway", "web-ui"],
        raw_alert_count=56,
        started_at="2026-10-09T03:14:07Z",
    )
    data.update(overrides)
    return Incident(**data)


def run(incident=None, adapter=None):
    return asyncio.run(pipeline.run_pipeline(incident or make_incident(), adapter or FakeAdapter()))


def pipeline_log(caplog):
    lines = [r.getMessage() for r in caplog.records if r.name == "agnitia.pipeline"]
    return [m for m in lines if m.startswith("pipeline source=")]


def assert_complete(result):
    assert result.status == "awaiting_approval"
    assert result.rca is not None and result.playbook is not None
    assert result.playbook.steps[0].service == "postgres"
    assert result.playbook.steps[0].action == "patch_memory_limit"
    assert [s.order for s in result.playbook.steps] == list(range(1, len(result.playbook.steps) + 1))
    assert result.playbook.diff == "resources.limits.memory: 64Mi -> 256Mi"


# ── (a) live success ─────────────────────────────────────────────────────────


def test_a_live_success(env, install_llm, caplog):
    caplog.set_level(logging.INFO, logger="agnitia.pipeline")
    fake = install_llm("ok")
    original = make_incident(status="detected")

    result = run(original)

    assert_complete(result)
    assert result.rca.root_cause == LIVE_ROOT_CAUSE
    assert all(e.verified for e in result.rca.evidence)
    assert result.rca.confidence == 0.97 and result.rca.warning is None
    assert fake.calls == ["RCA", "Playbook"]
    assert result.rca.similar_incident is None or result.rca.similar_incident.id != "INC-999"
    assert result.rca.similar_incident is not None and result.rca.similar_incident.id == "INC-087"
    # input is not mutated
    assert original.status == "detected" and original.rca is None and original.playbook is None
    lines = pipeline_log(caplog)
    assert len(lines) == 1 and lines[0].startswith("pipeline source=live reason=ok total_ms=")


# ── (b) the LLM raises -> cache ──────────────────────────────────────────────


def test_b_diagnose_error_uses_cache(env, install_llm, caplog):
    caplog.set_level(logging.INFO, logger="agnitia.pipeline")
    fake = install_llm("raise")

    result = run()

    assert_complete(result)
    assert result.rca.root_cause == CACHED_ROOT_CAUSE
    assert all(e.verified for e in result.rca.evidence)
    assert result.rca.similar_incident is not None and result.rca.similar_incident.id == "INC-087"
    assert fake.calls == ["RCA"]
    lines = pipeline_log(caplog)
    assert len(lines) == 1 and lines[0].startswith("pipeline source=cache reason=diagnose_error")


def test_b2_plan_error_discards_live_diagnosis(env, install_llm, caplog):
    """rca and playbook must always come from the same source."""
    caplog.set_level(logging.INFO, logger="agnitia.pipeline")
    fake = install_llm("raise", fail_on="Playbook")

    result = run()

    assert fake.calls == ["RCA", "Playbook"]
    assert_complete(result)
    assert result.rca.root_cause == CACHED_ROOT_CAUSE  # not the live one
    assert all(e.verified for e in result.rca.evidence)
    assert pipeline_log(caplog)[0].startswith("pipeline source=cache reason=plan_error")


# ── (c) the LLM is too slow -> cache ─────────────────────────────────────────


def test_c_timeout_uses_cache(env, install_llm, monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="agnitia.pipeline")
    monkeypatch.setattr(pipeline, "LLM_TIMEOUT_S", 0.1)
    install_llm("sleep")

    t0 = time.monotonic()
    result = run()

    assert time.monotonic() - t0 < 3
    assert_complete(result)
    assert result.rca.root_cause == CACHED_ROOT_CAUSE
    assert pipeline_log(caplog)[0].startswith("pipeline source=cache reason=diagnose_timeout")


def test_c2_plan_timeout_uses_cache(env, install_llm, monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="agnitia.pipeline")
    monkeypatch.setattr(pipeline, "LLM_TIMEOUT_S", 0.1)
    install_llm("sleep", fail_on="Playbook")

    result = run()

    assert_complete(result)
    assert result.rca.root_cause == CACHED_ROOT_CAUSE
    assert pipeline_log(caplog)[0].startswith("pipeline source=cache reason=plan_timeout")


# ── (d) DEMO_MODE=cache -> zero LLM calls; the mode is read on every call ────


def test_d_cache_mode_makes_no_llm_calls(env, install_llm, monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="agnitia.pipeline")
    fake = install_llm("ok")
    monkeypatch.setenv("DEMO_MODE", "cache")

    result = run()

    assert fake.calls == []
    assert_complete(result)
    assert result.rca.root_cause == CACHED_ROOT_CAUSE
    assert pipeline_log(caplog)[0].startswith("pipeline source=cache reason=demo_mode_cache")

    monkeypatch.setenv("DEMO_MODE", "auto")  # next call picks the new mode up
    result = run()
    assert fake.calls == ["RCA", "Playbook"]
    assert result.rca.root_cause == LIVE_ROOT_CAUSE


@pytest.mark.parametrize("scenario", ["db_oom", "bad_config", "cpu_spike", "slow_leak"])
def test_d2_every_cached_scenario_completes_offline(env, install_llm, monkeypatch, scenario):
    fake = install_llm("ok")
    monkeypatch.setenv("DEMO_MODE", "cache")
    data = json.loads((SCENARIOS_DIR / f"{scenario}.json").read_text(encoding="utf-8"))
    incident = make_incident(scenario=scenario, root_service=data["root_service"], impacted_services=[])

    result = run(incident, FakeAdapter(scenario))

    assert fake.calls == []
    assert result.status == "awaiting_approval"
    assert result.rca is not None and result.playbook is not None and result.playbook.steps
    assert {s.risk for s in result.playbook.steps} <= {"low", "high"}
    assert all(s.requires_approval for s in result.playbook.steps if s.risk == "high")


# ── (e) a planted fake citation ──────────────────────────────────────────────


def test_e_planted_fake_log_line_drops_confidence(env, install_llm):
    install_llm("ok", planted_fake_log=True)

    result = run()

    assert result.status == "awaiting_approval" and result.playbook is not None
    assert result.rca.confidence == pytest.approx(0.77)
    assert result.rca.warning and "planted line that never happened" in result.rca.warning
    assert [e.verified for e in result.rca.evidence] == [True, False, True]
    verify_done = [p for t, p in env if p["agent"] == "verify" and p["status"] == "done"][0]
    assert verify_done["text"] == "Checked 3 citations against the raw data: 2 verified, 1 not found in the raw data"


# ── (f) no cache + live failure ──────────────────────────────────────────────


def test_f_no_cache_and_live_failure(env, install_llm, monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="agnitia.pipeline")
    monkeypatch.setattr(pipeline, "CACHE_DIR", tmp_path)  # empty: no cache for any scenario
    install_llm("raise")
    original = make_incident(status="detected")

    result = run(original)

    assert result.status == "analyzing"
    assert result.rca is None and result.playbook is None
    assert result.model_dump() == original.model_copy(update={"status": "analyzing"}).model_dump()
    last = env[-1]
    assert last[0] == "agent_step" and last[1]["status"] == "failed"
    assert last[1]["text"] == "No analysis available for this scenario"
    assert pipeline_log(caplog)[0].startswith("pipeline source=none reason=diagnose_error:LLMError_no_cache")


def test_f2_plan_failure_without_cache(env, install_llm, monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "CACHE_DIR", tmp_path)
    install_llm("raise", fail_on="Playbook")

    result = run()

    assert result.status == "analyzing" and result.rca is None and result.playbook is None
    assert env[-1][1]["status"] == "failed" and env[-1][1]["agent"] == "plan"


def test_f3_live_mode_never_uses_the_cache(env, install_llm, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "live")
    install_llm("raise")

    result = run()

    assert result.status == "analyzing" and result.rca is None
    assert env[-1][1]["status"] == "failed"


def test_f4_cache_mode_without_cache_fails_cleanly(env, install_llm, monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_MODE", "cache")
    monkeypatch.setattr(pipeline, "CACHE_DIR", tmp_path)
    fake = install_llm("ok")

    result = run(make_incident(scenario="no_such_scenario"))

    assert fake.calls == []
    assert result.status == "analyzing" and result.rca is None
    assert env[-1][1]["status"] == "failed"


def test_f5_never_raises_when_adapter_and_emit_break(env, install_llm, monkeypatch):
    class BrokenAdapter(FakeAdapter):
        async def get_logs(self, service, lines=50):
            raise ConnectionError("cluster gone")

        async def list_services(self):
            raise ConnectionError("cluster gone")

    async def broken_emit(event_type, payload):
        raise RuntimeError("socket closed")

    monkeypatch.setattr(pipeline, "emit", broken_emit)
    install_llm("ok")

    result = run(adapter=BrokenAdapter())  # evidence missing -> cache; citations flagged honestly

    assert result.status == "awaiting_approval"
    assert result.rca.root_cause == CACHED_ROOT_CAUSE
    assert result.rca.confidence == pytest.approx(0.77)


# ── (g) event order and content ──────────────────────────────────────────────


def stage_of(payload):
    agent, text = payload["agent"], payload["text"]
    if agent == "triage":
        return "triage"
    if agent == "diagnose" and text.startswith(("Reading", "Checking the memory")):
        return "evidence"
    return agent


def collapsed(events):
    stages = []
    for event_type, payload in events:
        assert event_type == "agent_step"
        stage = stage_of(payload)
        if not stages or stages[-1] != stage:
            stages.append(stage)
    return stages


def test_g_event_order_live(env, install_llm):
    install_llm("ok")
    run()
    assert collapsed(env) == ["triage", "evidence", "diagnose", "verify", "plan"]


def test_g2_event_order_cache(env, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "cache")
    run()
    assert collapsed(env) == ["triage", "evidence", "diagnose", "verify", "plan"]


def test_g3_steps_have_real_counts_and_no_source(env, install_llm):
    install_llm("ok")
    run()
    texts = [p["text"] for _, p in env]
    assert "Grouping 56 alerts using the dependency map" in texts
    assert "No dependency of postgres is alerting, so postgres is the root; 4 downstream services impacted" in texts
    assert "Reading 50 log lines from postgres-0" in texts
    assert "Reading 1 Kubernetes events for postgres-0" in texts
    assert any(t.startswith("Checking the memory trend: 13 metric points from postgres-0, peak 64Mi") for t in texts)
    assert "Checked 3 citations against the raw data: 3 verified" in texts
    assert any(t.startswith("Recovery plan ready: 5 steps (resources.limits.memory: 64Mi -> 256Mi)") for t in texts)
    for _, p in env:
        assert set(p) == {"agent", "text", "status"}
        assert p["status"] in ("running", "done", "failed")
        assert "cache" not in p["text"].lower() and "live" not in p["text"].lower()
    # every stage starts "running" and ends "done"
    for agent in ("triage", "diagnose", "verify", "plan"):
        statuses = [p["status"] for _, p in env if p["agent"] == agent]
        assert statuses[0] == "running" and statuses[-1] == "done"


def test_g4_live_and_cache_runs_look_identical(env, install_llm, monkeypatch):
    install_llm("ok")
    run()
    live_shape = [(p["agent"], p["status"]) for _, p in env]
    env.clear()
    monkeypatch.setenv("DEMO_MODE", "cache")
    run()
    assert [(p["agent"], p["status"]) for _, p in env] == live_shape


def test_g5_steps_are_paced(env, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "cache")
    monkeypatch.setattr(pipeline, "STEP_PACE_S", (0.05, 0.05))
    t0 = time.monotonic()
    run()
    assert time.monotonic() - t0 >= 0.05 * (len(env) - 1) * 0.9


# ── ported from the old stub's tests ─────────────────────────────────────────


def test_triage_text_without_alert_count(env, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "cache")
    run(make_incident(raw_alert_count=0, impacted_services=[]))
    assert env[0][1] == {"agent": "triage", "text": "Grouping alerts using the dependency map", "status": "running"}
    assert env[1][1]["text"] == "No dependency of postgres is alerting, so postgres is the root"
    assert env[1][1]["status"] == "done"


def test_diagnosis_step_names_the_category(env, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "cache")
    run()
    done = [p for _, p in env if p["agent"] == "diagnose" and p["status"] == "done"][-1]
    assert "OOMKilled" in done["text"]


# ── importing must not need an LLM key or SDK ────────────────────────────────


def test_import_needs_no_key_and_no_sdk():
    code = (
        "import sys; sys.modules['google'] = None\n"  # makes 'import google...' raise ImportError
        "import backend.agents.pipeline\n"
        "assert 'backend.agents.llm' not in sys.modules\n"
    )
    clean_env = {k: v for k, v in os.environ.items() if k not in ("LLM_API_KEY", "LLM_MODEL", "DEMO_MODE")}
    proc = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, env=clean_env, capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, proc.stderr
