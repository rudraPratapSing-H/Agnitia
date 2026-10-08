"""Tests for backend/adapters/k8s.py (task 3.2).

The kubernetes client is fully mocked: no real cluster is touched. These tests assert
action translation (the k8s API calls an apply_action produces) and the K8sEvent text
format; real cluster behaviour is verified manually per the task spec.
"""

from types import SimpleNamespace
from typing import Any, List

import pytest
import pytest_asyncio

from backend.adapters.k8s import K8sAdapter
from backend.models import PlaybookStep


class FakeAppsV1Api:
    def __init__(self) -> None:
        self.patch_calls: List[tuple] = []

    def patch_namespaced_stateful_set(self, name, namespace, body):
        self.patch_calls.append((name, namespace, body))
        return SimpleNamespace()


class FakeCoreV1Api:
    def __init__(self) -> None:
        self.pod = _healthy_pod()
        self.events = SimpleNamespace(items=[])
        self.log_text = "2026-10-09T00:00:06.000000Z FATAL: out of memory\n"

    def read_namespaced_pod(self, name, namespace):
        return self.pod

    def read_namespaced_pod_log(self, name, namespace, previous=False, timestamps=True, tail_lines=50):
        return self.log_text

    def list_namespaced_event(self, namespace, field_selector=None):
        return self.events

    def connect_get_namespaced_pod_exec(self, *a, **kw):
        raise AssertionError("use kubernetes.stream.stream, not the raw connect_ call")


def _container_status(restart_count=0, terminated=None):
    return SimpleNamespace(restart_count=restart_count, last_state=SimpleNamespace(terminated=terminated))


def _healthy_pod():
    return SimpleNamespace(
        status=SimpleNamespace(
            conditions=[SimpleNamespace(type="Ready", status="True")],
            container_statuses=[_container_status()],
        )
    )


def _oom_pod():
    terminated = SimpleNamespace(reason="OOMKilled", exit_code=137)
    return SimpleNamespace(
        status=SimpleNamespace(
            conditions=[SimpleNamespace(type="Ready", status="False")],
            container_statuses=[_container_status(restart_count=1, terminated=terminated)],
        )
    )


@pytest_asyncio.fixture
async def adapter(monkeypatch):
    import backend.adapters.k8s as k8s_mod

    monkeypatch.setattr(k8s_mod.config, "load_kube_config", lambda context=None: None)
    fake_core = FakeCoreV1Api()
    fake_apps = FakeAppsV1Api()
    monkeypatch.setattr(k8s_mod.client, "CoreV1Api", lambda: fake_core)
    monkeypatch.setattr(k8s_mod.client, "AppsV1Api", lambda: fake_apps)

    async def fake_read_mem(self):
        return 66.0

    monkeypatch.setattr(k8s_mod.K8sAdapter, "_read_postgres_mem_mb", fake_read_mem)
    monkeypatch.setattr(k8s_mod, "subprocess", SimpleNamespace(run=lambda *a, **kw: None))

    adp = K8sAdapter()
    adp.on_alerts_complete = None
    yield adp, fake_core, fake_apps


# ── apply_action: action translation ────────────────────────────────────────


async def test_patch_memory_limit_patches_the_statefulset(adapter):
    adp, _core, apps = adapter
    step = PlaybookStep(order=1, service="postgres", action="patch_memory_limit",
                         params={"from": "64Mi", "to": "256Mi"})

    result = await adp.apply_action(step)

    assert result.ok
    assert len(apps.patch_calls) == 1
    name, namespace, body = apps.patch_calls[0]
    assert name == "postgres" and namespace == "agnitia"
    container = body["spec"]["template"]["spec"]["containers"][0]
    assert container["name"] == "postgres"
    assert container["resources"]["limits"]["memory"] == "256Mi"
    assert adp._postgres.metrics.mem_limit_mb == 256.0


async def test_rollout_restart_uses_annotation_never_deletes_pod(adapter):
    adp, core, apps = adapter
    step = PlaybookStep(order=1, service="postgres", action="rollout_restart")

    result = await adp.apply_action(step)

    assert result.ok
    name, namespace, body = apps.patch_calls[0]
    annotations = body["spec"]["template"]["metadata"]["annotations"]
    assert "kubectl.kubernetes.io/restartedAt" in annotations
    assert not hasattr(core, "delete_namespaced_pod_called")


async def test_blocked_action_is_never_sent_to_the_cluster(adapter):
    adp, _core, apps = adapter
    step = PlaybookStep(order=1, service="postgres", action="delete_pod")

    result = await adp.apply_action(step)

    assert not result.ok
    assert "not in ALLOWED_ACTIONS" in result.message
    assert apps.patch_calls == []


async def test_non_postgres_action_delegates_to_inner_simulator(adapter):
    adp, _core, apps = adapter
    step = PlaybookStep(order=1, service="auth-service", action="rollout_restart")

    result = await adp.apply_action(step)

    assert result.ok
    assert apps.patch_calls == []  # the real cluster was never touched


# ── probe ────────────────────────────────────────────────────────────────────


async def test_probe_postgres_true_when_ready(adapter):
    adp, core, _apps = adapter
    core.pod = _healthy_pod()
    assert await adp.probe("postgres") is True


async def test_probe_postgres_false_when_not_ready(adapter):
    adp, core, _apps = adapter
    core.pod = _oom_pod()
    assert await adp.probe("postgres") is False


# ── get_events: exact simulator text format ────────────────────────────────


async def test_real_oom_event_matches_simulator_text_format(adapter):
    adp, _core, _apps = adapter
    terminated = SimpleNamespace(reason="OOMKilled", exit_code=137)

    await adp._on_real_oom({"id": "db_oom", "root_service": "postgres", "alerts": []}, terminated)

    events = await adp.get_events("postgres")
    assert any(e.text == "Reason: OOMKilled, Exit Code: 137" for e in events)


async def test_get_logs_uses_previous_when_container_restarted(adapter):
    adp, core, _apps = adapter
    core.pod = _oom_pod()  # restart_count=1

    calls = {}
    orig = core.read_namespaced_pod_log

    def spy(name, namespace, previous=False, timestamps=True, tail_lines=50):
        calls["previous"] = previous
        return orig(name, namespace, previous, timestamps, tail_lines)

    core.read_namespaced_pod_log = spy
    logs = await adp.get_logs("postgres")

    assert calls["previous"] is True
    assert logs and logs[0].text == "FATAL: out of memory"
    assert logs[0].line == 1


# ── scenario routing ─────────────────────────────────────────────────────────


async def test_non_db_oom_scenario_delegates_fully_to_inner_simulator(adapter, monkeypatch):
    adp, _core, apps = adapter

    called = {}

    async def fake_inner_inject(scenario_id):
        called["scenario_id"] = scenario_id
        adp._inner._scenario = {"id": scenario_id}
        adp._inner._running_tasks = []
        return "INC-104"

    monkeypatch.setattr(adp._inner, "inject", fake_inner_inject)

    incident_id = await adp.inject("bad_config")

    assert incident_id == "INC-104"
    assert called["scenario_id"] == "bad_config"
    assert apps.patch_calls == []  # the real cluster was never touched


async def test_inject_db_oom_applies_memory_hog_and_starts_poll(adapter, monkeypatch):
    adp, _core, _apps = adapter
    kubectl_calls = []
    monkeypatch.setattr(K8sAdapter, "_run_kubectl", staticmethod(lambda args: kubectl_calls.append(args)))

    async def fast_poll_once(self, scenario):
        self._db_oom_triggered = True  # stop after one iteration

    monkeypatch.setattr(K8sAdapter, "_poll_postgres_once", fast_poll_once)

    incident_id = await adp.inject("db_oom")
    assert incident_id == "INC-104"
    assert adp._scenario is not None and adp._scenario["id"] == "db_oom"

    for task in adp._running_tasks:
        await task

    assert kubectl_calls and kubectl_calls[0][0] == "apply"


# ── reset ────────────────────────────────────────────────────────────────────


async def test_reset_after_db_oom_tears_down_the_real_cluster(adapter, monkeypatch):
    adp, core, apps = adapter
    core.pod = _healthy_pod()  # probe() sees "ready" immediately so reset doesn't hang
    monkeypatch.setattr(K8sAdapter, "_run_kubectl", staticmethod(lambda args: None))

    async def fast_poll_once(self, scenario):
        self._db_oom_triggered = True

    monkeypatch.setattr(K8sAdapter, "_poll_postgres_once", fast_poll_once)

    await adp.inject("db_oom")
    for task in adp._running_tasks:
        await task

    await adp.reset()

    assert apps.patch_calls, "expected the memory limit to be patched back to 64Mi"
    _name, _ns, body = apps.patch_calls[-1]
    container = body["spec"]["template"]["spec"]["containers"][0]
    assert container["resources"]["limits"]["memory"] == "64Mi"
    assert adp._scenario is None
    assert adp._postgres.metrics.mem_limit_mb == 64.0


async def test_reset_without_db_oom_never_touches_the_real_cluster(adapter, monkeypatch):
    adp, _core, apps = adapter

    async def fake_inner_inject(scenario_id):
        adp._inner._scenario = {"id": scenario_id}
        adp._inner._running_tasks = []
        return "INC-104"

    monkeypatch.setattr(adp._inner, "inject", fake_inner_inject)

    await adp.inject("bad_config")
    await adp.reset()

    assert apps.patch_calls == []


async def test_second_inject_while_running_raises(adapter, monkeypatch):
    adp, _core, _apps = adapter
    monkeypatch.setattr(K8sAdapter, "_run_kubectl", staticmethod(lambda args: None))

    async def never_finishes(self, scenario):
        import asyncio
        await asyncio.sleep(10)

    monkeypatch.setattr(K8sAdapter, "_poll_postgres_once", never_finishes)

    await adp.inject("db_oom")
    with pytest.raises(RuntimeError):
        await adp.inject("db_oom")

    for task in adp._running_tasks:
        task.cancel()
