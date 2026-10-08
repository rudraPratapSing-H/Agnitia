"""Unit tests for Planner Agent (TASK 2.2)"""

import subprocess
import sys
import json
import pytest
from backend.models import RCA, Playbook, PlaybookStep, ServiceNode, ServiceMetrics
from backend.agents.planner import (
    plan,
    PlanError,
    DEFAULT_SERVICES,
    _kahn_topo_order,
    build_diff,
)
import backend.agents.llm as llm_module


@pytest.fixture
def sample_rca():
    return RCA(
        root_cause="PostgreSQL was killed for exceeding its 64Mi memory limit",
        category="OOMKilled",
        confidence=0.97,
        evidence=[],
    )


@pytest.fixture
def sample_services():
    return DEFAULT_SERVICES


@pytest.mark.asyncio
async def test_a_shuffled_steps_reordered_by_topology(monkeypatch, sample_rca, sample_services):
    """
    (a) The model returns steps shuffled (api-gateway first, postgres last) ->
    after plan, postgres is first and api-gateway last.
    """
    fake_playbook = Playbook(
        diff=None,
        steps=[
            PlaybookStep(
                order=1,
                service="api-gateway",
                action="verify_health",
                risk="low",
                requires_approval=False,
                verify="error rate below 1%",
            ),
            PlaybookStep(
                order=2,
                service="auth-service",
                action="rollout_restart",
                risk="low",
                requires_approval=False,
                verify="health endpoint 200",
            ),
            PlaybookStep(
                order=3,
                service="payment-service",
                action="rollout_restart",
                risk="low",
                requires_approval=False,
                verify="health endpoint 200",
            ),
            PlaybookStep(
                order=4,
                service="postgres",
                action="patch_memory_limit",
                params={"from": "64Mi", "to": "256Mi"},
                risk="high",
                requires_approval=True,
                verify="port 5432 accepting connections",
            ),
        ],
    )

    async def fake_call_json(prompt, payload, model_cls, **kwargs):
        return fake_playbook

    monkeypatch.setattr(llm_module, "call_json", fake_call_json)

    result = await plan(sample_rca, sample_services)

    # After plan: postgres must be first, api-gateway last
    assert result.steps[0].service == "postgres"
    assert result.steps[-1].service == "api-gateway"
    assert [s.order for s in result.steps] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_b_disallowed_action_raises_plan_error(monkeypatch, sample_rca, sample_services):
    """
    (b) A disallowed action 'delete_pod' raises PlanError.
    """
    fake_playbook = Playbook(
        diff=None,
        steps=[
            PlaybookStep(
                order=1,
                service="postgres",
                action="delete_pod",
                risk="high",
                requires_approval=True,
                verify="pod recreated",
            ),
        ],
    )

    async def fake_call_json(prompt, payload, model_cls, **kwargs):
        return fake_playbook

    monkeypatch.setattr(llm_module, "call_json", fake_call_json)

    with pytest.raises(PlanError) as exc_info:
        await plan(sample_rca, sample_services)

    assert "delete_pod" in str(exc_info.value)


@pytest.mark.asyncio
async def test_c_patch_step_forced_to_high_risk_and_approval(monkeypatch, sample_rca, sample_services):
    """
    (c) A patch step is forced to risk 'high' and requires_approval True even if the fake said low/false.
    """
    fake_playbook = Playbook(
        diff=None,
        steps=[
            PlaybookStep(
                order=1,
                service="postgres",
                action="patch_memory_limit",
                params={"from": "64Mi", "to": "256Mi"},
                risk="low",
                requires_approval=False,
                verify="port 5432 accepting connections",
            ),
            PlaybookStep(
                order=2,
                service="postgres",
                action="patch_cpu_limit",
                params={"from": "100m", "to": "500m"},
                risk="low",
                requires_approval=False,
                verify="cpu limit verified",
            ),
            PlaybookStep(
                order=3,
                service="auth-service",
                action="rollback_deployment",
                risk="low",
                requires_approval=False,
                verify="revision restored",
            ),
            PlaybookStep(
                order=4,
                service="web-ui",
                action="scale_replicas",
                params={"replicas": 3},
                risk="low",
                requires_approval=False,
                verify="replicas healthy",
            ),
        ],
    )

    async def fake_call_json(prompt, payload, model_cls, **kwargs):
        return fake_playbook

    monkeypatch.setattr(llm_module, "call_json", fake_call_json)

    result = await plan(sample_rca, sample_services)

    for step in result.steps:
        assert step.risk == "high"
        assert step.requires_approval is True


@pytest.mark.asyncio
async def test_d_diff_string_for_memory_patch(monkeypatch, sample_rca, sample_services):
    """
    (d) diff string for 64Mi -> 256Mi.
    """
    fake_playbook = Playbook(
        diff="untrusted diff from model",
        steps=[
            PlaybookStep(
                order=1,
                service="postgres",
                action="patch_memory_limit",
                params={"from": "64Mi", "to": "256Mi"},
                risk="high",
                requires_approval=True,
                verify="port 5432 accepting connections",
            ),
        ],
    )

    async def fake_call_json(prompt, payload, model_cls, **kwargs):
        return fake_playbook

    monkeypatch.setattr(llm_module, "call_json", fake_call_json)

    result = await plan(sample_rca, sample_services)
    assert result.diff == "resources.limits.memory: 64Mi -> 256Mi"


@pytest.mark.asyncio
async def test_e_wait_for_ready_stays_after_postgres_patch(monkeypatch, sample_rca, sample_services):
    """
    (e) wait_for_ready stays right after its postgres patch step.
    """
    fake_playbook = Playbook(
        diff=None,
        steps=[
            PlaybookStep(
                order=1,
                service="api-gateway",
                action="verify_health",
                risk="low",
                requires_approval=False,
                verify="error rate below 1%",
            ),
            PlaybookStep(
                order=2,
                service="postgres",
                action="patch_memory_limit",
                params={"from": "64Mi", "to": "256Mi"},
                risk="high",
                requires_approval=True,
                verify="port 5432 accepting connections",
            ),
            PlaybookStep(
                order=3,
                service="postgres",
                action="wait_for_ready",
                params={"timeout_s": 30},
                risk="low",
                requires_approval=False,
                verify="readiness probe passes",
            ),
            PlaybookStep(
                order=4,
                service="auth-service",
                action="rollout_restart",
                risk="low",
                requires_approval=False,
                verify="health endpoint 200",
            ),
        ],
    )

    async def fake_call_json(prompt, payload, model_cls, **kwargs):
        return fake_playbook

    monkeypatch.setattr(llm_module, "call_json", fake_call_json)

    result = await plan(sample_rca, sample_services)

    # Postgres patch is order 1, wait_for_ready is order 2 right after it
    assert result.steps[0].service == "postgres"
    assert result.steps[0].action == "patch_memory_limit"
    assert result.steps[0].order == 1

    assert result.steps[1].service == "postgres"
    assert result.steps[1].action == "wait_for_ready"
    assert result.steps[1].order == 2

    # wait_for_ready remains low risk
    assert result.steps[1].risk == "low"
    assert result.steps[1].requires_approval is False


@pytest.mark.asyncio
async def test_unknown_service_placed_last(monkeypatch, sample_rca, sample_services):
    """Unknown service not in topology graph is placed at the end."""
    fake_playbook = Playbook(
        diff=None,
        steps=[
            PlaybookStep(
                order=1,
                service="external-service",
                action="verify_health",
                risk="low",
                requires_approval=False,
                verify="check external",
            ),
            PlaybookStep(
                order=2,
                service="postgres",
                action="patch_memory_limit",
                params={"from": "64Mi", "to": "256Mi"},
                risk="high",
                requires_approval=True,
                verify="port 5432 accepting connections",
            ),
        ],
    )

    async def fake_call_json(prompt, payload, model_cls, **kwargs):
        return fake_playbook

    monkeypatch.setattr(llm_module, "call_json", fake_call_json)

    result = await plan(sample_rca, sample_services)
    assert result.steps[0].service == "postgres"
    assert result.steps[1].service == "external-service"


def test_diff_builder_scenarios():
    # Patch CPU limit
    step_cpu = PlaybookStep(
        order=1,
        service="postgres",
        action="patch_cpu_limit",
        params={"from": "500m", "to": "2000m"},
        risk="high",
        requires_approval=True,
        verify="cpu limit check",
    )
    assert build_diff([step_cpu]) == "resources.limits.cpu: 500m -> 2000m"

    # Rollback deployment
    step_rb = PlaybookStep(
        order=1,
        service="auth-service",
        action="rollback_deployment",
        risk="high",
        requires_approval=True,
        verify="status 200",
    )
    assert build_diff([step_rb]) == "rollback: previous revision of auth-service"

    # Rollout restart only
    step_rr1 = PlaybookStep(
        order=1,
        service="auth-service",
        action="rollout_restart",
        risk="low",
        requires_approval=False,
        verify="health 200",
    )
    step_rr2 = PlaybookStep(
        order=2,
        service="payment-service",
        action="rollout_restart",
        risk="low",
        requires_approval=False,
        verify="health 200",
    )
    assert build_diff([step_rr1, step_rr2]) == "No configuration change: rollout restart of auth-service, payment-service"


def test_fallback_kahn_topo_order(sample_services):
    ordered = _kahn_topo_order(sample_services)
    # Dependencies must precede dependents
    assert ordered.index("postgres") < ordered.index("auth-service")
    assert ordered.index("postgres") < ordered.index("payment-service")
    assert ordered.index("auth-service") < ordered.index("api-gateway")
    assert ordered.index("api-gateway") < ordered.index("web-ui")


def test_cli_execution():
    """Verify python -m backend.agents.planner --scenario db_oom runs and prints valid playbook JSON."""
    res = subprocess.run(
        [sys.executable, "-m", "backend.agents.planner", "--scenario", "db_oom"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(res.stdout)
    assert "diff" in data
    assert "steps" in data
    assert len(data["steps"]) >= 1
    # Verify topological order: postgres first
    assert data["steps"][0]["service"] == "postgres"
