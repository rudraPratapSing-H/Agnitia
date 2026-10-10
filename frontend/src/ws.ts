// frontend/src/ws.ts - WebSocket Manager & Multi-Architecture Scenario Simulation Engine
import { applyWsEvent, setWsConnected, setSimulating, resetStore, getState } from './store';
import dbOomMockData from './mock/events_db_oom.json';

let socket: WebSocket | null = null;
let reconnectTimer: any = null;
let activeTimeouts: any[] = [];
let currentActiveScenario: string = 'db_oom';

const WS_URL = (import.meta as any).env?.VITE_WS_URL || 'ws://localhost:8000/ws';

export function connectWebSocket() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }

  try {
    socket = new WebSocket(WS_URL);

    socket.onopen = () => {
      console.log('Connected to Agnitia Backend WS at', WS_URL);
      setWsConnected(true);
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        applyWsEvent(data);
      } catch (err) {
        console.error('Failed to parse WS message:', err, event.data);
      }
    };

    socket.onclose = () => {
      setWsConnected(false);
      socket = null;
      if (!reconnectTimer) {
        reconnectTimer = setTimeout(() => {
          connectWebSocket();
        }, 4000);
      }
    };

    socket.onerror = () => {
      setWsConnected(false);
    };
  } catch (err) {
    setWsConnected(false);
  }
}

export function sendWsMessage(type: string, payload: any) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type, payload }));
    return true;
  }
  return false;
}

export function clearActiveSimulation() {
  activeTimeouts.forEach((t) => clearTimeout(t));
  activeTimeouts = [];
  setSimulating(false, null);
}

export function triggerBackendReset() {
  fetch('http://localhost:8000/api/reset', { method: 'POST' }).catch(() => {});
}

// Deterministic Simulation Runner
export function playScenario(scenarioId: string) {
  clearActiveSimulation();
  resetStore();
  currentActiveScenario = scenarioId;

  // Run the immediate local simulation so UI responds instantly at 60ms
  runLocalSimulation(scenarioId);

  // Notify live backend in parallel only when testing K8s core
  const isK8s = getState().activePresetId === 'k8s-core';
  if (isK8s) {
    fetch(`http://localhost:8000/api/chaos/${scenarioId}`, { method: 'POST' }).catch(() => {});
  }
}

export function resetAll() {
  clearActiveSimulation();
  resetStore();
  fetch('http://localhost:8000/api/reset', { method: 'POST' }).catch(() => {});
}

// POST /api/autonomy {level} -- tells the backend's approval gate which level is active.
export function setAutonomyBackend(level: number) {
  fetch('http://localhost:8000/api/autonomy', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ level }),
  }).catch(() => {});
}

// POST /api/killswitch {on} -- instantly halts the predictive auto-heal layer.
export function setKillSwitchBackend(on: boolean) {
  fetch('http://localhost:8000/api/killswitch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ on }),
  }).catch(() => {});
}

// GET /api/ml/status -- initial snapshot so the kill switch reflects real backend state on load.
export async function fetchMlStatus(): Promise<{ kill_switch: boolean; level: number } | null> {
  try {
    const res = await fetch('http://localhost:8000/api/ml/status');
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function runLocalSimulation(scenarioId: string) {
  const isAmazon = getState().activePresetId === 'amazon-scale';
  console.log(`Running simulation for: ${scenarioId} (Preset: ${isAmazon ? 'Amazon' : 'K8s Core'})`);
  setSimulating(true, scenarioId);

  let eventsList: any[] = [];

  if (isAmazon) {
    if (scenarioId === 'db_oom') {
      eventsList = getAmazonDbOomMockEvents();
    } else if (scenarioId === 'bad_config') {
      eventsList = getAmazonBadConfigMockEvents();
    } else if (scenarioId === 'cpu_spike') {
      eventsList = getAmazonCpuSpikeMockEvents();
    } else if (scenarioId === 'slow_leak') {
      eventsList = getAmazonSlowLeakMockEvents();
    }
  } else {
    if (scenarioId === 'db_oom') {
      eventsList = getK8sDbOomMockEvents();
    } else if (scenarioId === 'bad_config') {
      eventsList = getK8sBadConfigMockEvents();
    } else if (scenarioId === 'cpu_spike') {
      eventsList = getK8sCpuSpikeMockEvents();
    } else if (scenarioId === 'slow_leak') {
      eventsList = getK8sSlowLeakMockEvents();
    }
  }

  eventsList.forEach((item) => {
    const timeout = setTimeout(() => {
      applyWsEvent(item);
    }, item.delay);
    activeTimeouts.push(timeout);
  });

  const maxDelay = Math.max(...eventsList.map((e) => e.delay), 0);
  const endTimeout = setTimeout(() => {
    setSimulating(false, scenarioId);
  }, maxDelay + 500);
  activeTimeouts.push(endTimeout);
}

export function executeFullHealFlow() {
  clearActiveSimulation();
  const state = getState();
  const isAmazon = state.activePresetId === 'amazon-scale';
  const inc = state.incident;

  if (inc) {
    applyWsEvent({
      type: 'incident_update',
      payload: { ...inc, status: 'healing' }
    });
  }

  // Also notify live backend if connected
  if (inc && inc.id && state.wsConnected) {
    fetch(`http://localhost:8000/api/incidents/${inc.id}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved_by: 'ui' })
    }).catch(() => {});
  }

  if (isAmazon) {
    if (currentActiveScenario === 'bad_config') {
      executeAmazonBadConfigHeal();
    } else if (currentActiveScenario === 'cpu_spike') {
      executeAmazonCpuSpikeHeal();
    } else if (currentActiveScenario === 'slow_leak') {
      executeAmazonSlowLeakHeal();
    } else {
      executeAmazonDbOomHeal();
    }
  } else {
    if (currentActiveScenario === 'bad_config') {
      executeK8sBadConfigHeal();
    } else if (currentActiveScenario === 'cpu_spike') {
      executeK8sCpuSpikeHeal();
    } else if (currentActiveScenario === 'slow_leak') {
      executeK8sSlowLeakHeal();
    } else {
      executeK8sDbOomHeal();
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// K8S CORE HEAL FLOWS
// ─────────────────────────────────────────────────────────────────────────────
function executeK8sDbOomHeal() {
  const healSteps = [
    { delay: 400, type: 'agent_step', payload: { agent: 'execute', text: 'Step 1: Applying memory patch to postgres (64Mi -> 256Mi)...', status: 'running' } },
    { delay: 800, type: 'playbook_step', payload: { order: 1, status: 'done' } },
    { delay: 1100, type: 'service_update', payload: { id: 'postgres', status: 'recovering', metrics: { mem_mb: 52, mem_limit_mb: 256, cpu_pct: 18, restarts: 1 } } },
    { delay: 1400, type: 'agent_step', payload: { agent: 'verify', text: 'Step 2: Probing postgres readiness (port 5432)...', status: 'running' } },
    { delay: 2000, type: 'playbook_step', payload: { order: 2, status: 'done' } },
    { delay: 2200, type: 'service_update', payload: { id: 'postgres', status: 'healthy', metrics: { mem_mb: 48, mem_limit_mb: 256, cpu_pct: 10, restarts: 0 } } },
    { delay: 2500, type: 'agent_step', payload: { agent: 'execute', text: 'Step 3: Rolling restart of auth-service...', status: 'running' } },
    { delay: 2900, type: 'playbook_step', payload: { order: 3, status: 'done' } },
    { delay: 3100, type: 'service_update', payload: { id: 'auth-service', status: 'healthy', metrics: { mem_mb: 36, mem_limit_mb: 128, cpu_pct: 6, restarts: 0 } } },
    { delay: 3400, type: 'agent_step', payload: { agent: 'execute', text: 'Step 4: Rolling restart of payment-service...', status: 'running' } },
    { delay: 3800, type: 'playbook_step', payload: { order: 4, status: 'done' } },
    { delay: 4000, type: 'service_update', payload: { id: 'payment-service', status: 'healthy', metrics: { mem_mb: 68, mem_limit_mb: 256, cpu_pct: 9, restarts: 0 } } },
    { delay: 4300, type: 'agent_step', payload: { agent: 'verify', text: 'Step 5: Verifying edge error rate on api-gateway...', status: 'running' } },
    { delay: 4700, type: 'playbook_step', payload: { order: 5, status: 'done' } },
    { delay: 4900, type: 'service_update', payload: { id: 'api-gateway', status: 'healthy', metrics: { mem_mb: 88, mem_limit_mb: 256, cpu_pct: 14, restarts: 0 } } },
    { delay: 5200, type: 'playbook_step', payload: { order: 6, status: 'done' } },
    { delay: 5400, type: 'service_update', payload: { id: 'web-ui', status: 'healthy', metrics: { mem_mb: 50, mem_limit_mb: 128, cpu_pct: 12, restarts: 0 } } },
    { delay: 5700, type: 'agent_step', payload: { agent: 'verify', text: 'All health checks verified 200 OK. Entire topology returned to HEALTHY state in 38s.', status: 'done' } },
    {
      delay: 6000,
      type: 'incident_update',
      payload: {
        id: 'INC-104',
        status: 'resolved',
        scenario: 'db_oom',
        root_service: 'postgres',
        impacted_services: [],
        raw_alert_count: 56,
        started_at: '2026-10-09T03:14:07Z',
        resolved_at: new Date().toISOString(),
        rca: {
          root_cause: 'PostgreSQL terminated with exit code 137 (OOMKilled) after saturating its 64Mi container limit. Resolved via 256Mi memory patch and topological restart.',
          category: 'OOMKilled',
          confidence: 0.97,
          evidence: [
            { type: 'k8s_event', source: 'postgres-0', text: 'Reason: OOMKilled, Exit Code: 137', verified: true },
            { type: 'log', source: 'postgres-0', line: 42, text: 'FATAL: out of memory allocating shared buffer', verified: true },
            { type: 'metric', source: 'postgres-0', text: 'memory peaked at 63.8Mi of 64Mi limit', verified: true }
          ]
        },
        playbook: {
          diff: 'resources.limits.memory: 64Mi -> 256Mi',
          steps: []
        }
      }
    }
  ];

  healSteps.forEach((item) => {
    const timeout = setTimeout(() => {
      applyWsEvent(item);
    }, item.delay);
    activeTimeouts.push(timeout);
  });
}

function executeK8sBadConfigHeal() {
  const healSteps = [
    { delay: 300, type: 'agent_step', payload: { agent: 'execute', text: 'Step 1: Executing kubectl rollout undo deployment/payment-service --to-revision=23...', status: 'running' } },
    { delay: 700, type: 'playbook_step', payload: { order: 1, status: 'done' } },
    { delay: 1000, type: 'service_update', payload: { id: 'payment-service', status: 'recovering', metrics: { mem_mb: 68, mem_limit_mb: 256, cpu_pct: 12, restarts: 0 } } },
    { delay: 1400, type: 'agent_step', payload: { agent: 'verify', text: 'Step 2: Probing payment-service /healthz (STRIPE_API_SECRET verified)...', status: 'running' } },
    { delay: 1800, type: 'playbook_step', payload: { order: 2, status: 'done' } },
    { delay: 2000, type: 'service_update', payload: { id: 'payment-service', status: 'healthy', metrics: { mem_mb: 72, mem_limit_mb: 256, cpu_pct: 6, restarts: 0 } } },
    { delay: 2300, type: 'service_update', payload: { id: 'api-gateway', status: 'healthy', metrics: { mem_mb: 85, mem_limit_mb: 256, cpu_pct: 14, restarts: 0 } } },
    { delay: 2500, type: 'service_update', payload: { id: 'web-ui', status: 'healthy', metrics: { mem_mb: 48, mem_limit_mb: 128, cpu_pct: 10, restarts: 0 } } },
    { delay: 2800, type: 'agent_step', payload: { agent: 'verify', text: 'Rollback verified 200 OK. Payment gateway restored with 0 transaction drops.', status: 'done' } },
    {
      delay: 3100,
      type: 'incident_update',
      payload: {
        id: 'INC-105',
        status: 'resolved',
        scenario: 'bad_config',
        root_service: 'payment-service',
        impacted_services: [],
        raw_alert_count: 14,
        started_at: new Date().toISOString(),
        resolved_at: new Date().toISOString(),
        rca: {
          root_cause: 'Deployment revision #24 rolled back to revision #23. Container initialized successfully with all required secrets present.',
          category: 'CrashLoopBackOff',
          confidence: 0.99,
          evidence: [{ type: 'log', source: 'payment-service-58c9', line: 12, text: 'Rollback to rev 23 successful', verified: true }]
        },
        playbook: {
          diff: 'image: payment-service:v2.4.0 (stable revision #23)',
          steps: []
        }
      }
    }
  ];

  healSteps.forEach((item) => {
    const timeout = setTimeout(() => {
      applyWsEvent(item);
    }, item.delay);
    activeTimeouts.push(timeout);
  });
}

function executeK8sCpuSpikeHeal() {
  const healSteps = [
    { delay: 300, type: 'agent_step', payload: { agent: 'execute', text: 'Step 1: Scaling auth-service replicas from 1 to 3 (kubectl scale)...', status: 'running' } },
    { delay: 700, type: 'playbook_step', payload: { order: 1, status: 'done' } },
    { delay: 1000, type: 'service_update', payload: { id: 'auth-service', status: 'recovering', metrics: { mem_mb: 44, mem_limit_mb: 128, cpu_pct: 45, restarts: 0 } } },
    { delay: 1400, type: 'agent_step', payload: { agent: 'verify', text: 'Step 2: Monitoring HPA target metrics & P99 latency...', status: 'running' } },
    { delay: 1800, type: 'playbook_step', payload: { order: 2, status: 'done' } },
    { delay: 2000, type: 'service_update', payload: { id: 'auth-service', status: 'healthy', metrics: { mem_mb: 40, mem_limit_mb: 128, cpu_pct: 18, restarts: 0 } } },
    { delay: 2300, type: 'service_update', payload: { id: 'api-gateway', status: 'healthy', metrics: { mem_mb: 84, mem_limit_mb: 256, cpu_pct: 12, restarts: 0 } } },
    { delay: 2700, type: 'agent_step', payload: { agent: 'verify', text: 'Autoscaling validated. P99 latency restored to 34ms across 3 replicas.', status: 'done' } },
    {
      delay: 3000,
      type: 'incident_update',
      payload: {
        id: 'INC-106',
        status: 'resolved',
        scenario: 'cpu_spike',
        root_service: 'auth-service',
        impacted_services: [],
        raw_alert_count: 8,
        started_at: new Date().toISOString(),
        resolved_at: new Date().toISOString(),
        rca: {
          root_cause: 'CPU throttling resolved by horizontal scale-out. Load balanced across 3 replicas with 0 dropped authentication tokens.',
          category: 'CPUSaturation',
          confidence: 0.98,
          evidence: [{ type: 'metric', source: 'auth-service', text: 'CPU dropped from 99% to 18%', verified: true }]
        },
        playbook: {
          diff: 'spec.replicas: 1 -> 3',
          steps: []
        }
      }
    }
  ];

  healSteps.forEach((item) => {
    const timeout = setTimeout(() => {
      applyWsEvent(item);
    }, item.delay);
    activeTimeouts.push(timeout);
  });
}

function executeK8sSlowLeakHeal() {
  const healSteps = [
    { delay: 300, type: 'agent_step', payload: { agent: 'execute', text: 'Pre-emptive remediation: Expanding postgres cgroup memory limit to 128Mi...', status: 'running' } },
    { delay: 700, type: 'service_update', payload: { id: 'postgres', status: 'recovering', metrics: { mem_mb: 58, mem_limit_mb: 128, cpu_pct: 14, restarts: 0 } } },
    { delay: 1200, type: 'agent_step', payload: { agent: 'verify', text: 'Memory gradient stabilized. Zero pod restarts or evictions occurred.', status: 'done' } },
    { delay: 1500, type: 'service_update', payload: { id: 'postgres', status: 'healthy', metrics: { mem_mb: 48, mem_limit_mb: 128, cpu_pct: 10, restarts: 0 } } },
    {
      delay: 1800,
      type: 'incident_update',
      payload: {
        id: 'INC-107',
        status: 'resolved',
        scenario: 'slow_leak',
        root_service: 'postgres',
        impacted_services: [],
        raw_alert_count: 2,
        started_at: new Date().toISOString(),
        resolved_at: new Date().toISOString(),
        rca: {
          root_cause: 'Predictive memory exhaustion mitigated 142s ahead of crash. No downtime experienced.',
          category: 'PredictiveRemediation',
          confidence: 0.99,
          evidence: [{ type: 'prediction', source: 'postgres-0', text: 'Gradient +2.4MB/min countered before breach', verified: true }]
        },
        playbook: {
          diff: 'limits.memory: 64Mi -> 128Mi',
          steps: []
        }
      }
    }
  ];

  healSteps.forEach((item) => {
    const timeout = setTimeout(() => {
      applyWsEvent(item);
    }, item.delay);
    activeTimeouts.push(timeout);
  });
}

function getK8sDbOomMockEvents() {
  return [
    // T = 60ms: ROOT FAILURE EXPLODES INSTANTLY -> Pod grows red, alerts immediately fire
    { delay: 60, type: 'service_update', payload: { id: 'postgres', status: 'root_cause', metrics: { mem_mb: 64, mem_limit_mb: 64, cpu_pct: 45, restarts: 1 } } },
    { delay: 80, type: 'alert', payload: { id: 'a-001', service: 'postgres', severity: 'critical', message: 'Pod postgres-0 OOMKilled: container exceeded 64Mi limit (ExitCode 137)', ts: '03:14:07.102' } },
    { delay: 100, type: 'agent_step', payload: { agent: 'triage', text: 'CRITICAL INGEST: postgres-0 OOMKilled (ExitCode 137). Outgoing laser blast wave initiated...', status: 'running' } },

    // Tier 2 Cascade (T = 1600ms): auth-service & payment-service fail as blast wave reaches them
    { delay: 1600, type: 'service_update', payload: { id: 'auth-service', status: 'impacted', metrics: { mem_mb: 42, mem_limit_mb: 128, cpu_pct: 8, restarts: 0 } } },
    { delay: 1650, type: 'service_update', payload: { id: 'payment-service', status: 'impacted', metrics: { mem_mb: 78, mem_limit_mb: 256, cpu_pct: 12, restarts: 0 } } },
    { delay: 1750, type: 'alert', payload: { id: 'a-002', service: 'auth-service', severity: 'critical', message: 'PG_CONN_TIMEOUT: dial tcp 10.96.0.4:5432 i/o timeout', ts: '03:14:08.800' } },
    { delay: 1850, type: 'alert', payload: { id: 'a-012', service: 'payment-service', severity: 'critical', message: 'Transaction ledger write failed: database connection closed', ts: '03:14:08.850' } },
    { delay: 1950, type: 'alert', payload: { id: 'a-005', service: 'auth-service', severity: 'critical', message: 'Circuit breaker OPEN for upstream postgres:5432', ts: '03:14:08.900' } },

    // Tier 3 Cascade (T = 3200ms): api-gateway fails as blast wave propagates downstream
    { delay: 3200, type: 'service_update', payload: { id: 'api-gateway', status: 'impacted', metrics: { mem_mb: 110, mem_limit_mb: 256, cpu_pct: 34, restarts: 0 } } },
    { delay: 3300, type: 'alert', payload: { id: 'a-027', service: 'api-gateway', severity: 'critical', message: '502 Bad Gateway: upstream auth-service returned 503', ts: '03:14:10.500' } },
    { delay: 3400, type: 'alert', payload: { id: 'a-028', service: 'api-gateway', severity: 'critical', message: '504 Gateway Timeout: payment-service took > 5000ms', ts: '03:14:10.550' } },
    { delay: 3500, type: 'alert', payload: { id: 'a-033', service: 'api-gateway', severity: 'critical', message: 'Ingress HTTP 5xx error rate exceeded 5% threshold (currently 82%)', ts: '03:14:10.600' } },

    // Tier 4 Cascade (T = 4800ms): web-ui storefront degrades
    { delay: 4800, type: 'service_update', payload: { id: 'web-ui', status: 'impacted', metrics: { mem_mb: 65, mem_limit_mb: 128, cpu_pct: 18, restarts: 0 } } },
    { delay: 4900, type: 'alert', payload: { id: 'a-045', service: 'web-ui', severity: 'critical', message: 'Frontend SSR render failed: Auth endpoint returned 502', ts: '03:14:12.200' } },
    { delay: 5000, type: 'alert', payload: { id: 'a-046', service: 'web-ui', severity: 'critical', message: 'Client telemetry: Checkout modal throwing Uncaught Error', ts: '03:14:12.250' } },

    // AI Agents correlation & diagnosis
    { delay: 6000, type: 'agent_step', payload: { agent: 'triage', text: 'Topological correlation applied: 56 alerts collapsed into 1 root incident (postgres-0).', status: 'done' } },
    { delay: 7000, type: 'agent_step', payload: { agent: 'diagnose', text: 'Hard evidence identified: postgres-0 ExitCode 137, Memory 64MiB/64MiB, log: FATAL out of memory.', status: 'done' } },
    { delay: 8000, type: 'agent_step', payload: { agent: 'plan', text: 'Topological sequential recovery playbook synthesized. High-risk patch requires Human-in-the-Loop approval.', status: 'done' } },
    {
      delay: 8600,
      type: 'incident_update',
      payload: {
        id: 'INC-104',
        status: 'awaiting_approval',
        scenario: 'db_oom',
        root_service: 'postgres',
        impacted_services: ['auth-service', 'payment-service', 'api-gateway', 'web-ui'],
        raw_alert_count: 56,
        started_at: '2026-10-09T03:14:07Z',
        resolved_at: null,
        rca: {
          root_cause: 'PostgreSQL terminated with exit code 137 (OOMKilled) after saturating its 64Mi container limit.',
          category: 'OOMKilled',
          confidence: 0.97,
          evidence: [
            { type: 'k8s_event', source: 'postgres-0', text: 'Reason: OOMKilled, Exit Code: 137', verified: true },
            { type: 'log', source: 'postgres-0', line: 42, text: 'FATAL: out of memory allocating 4194304 bytes buffer', verified: true },
            { type: 'metric', source: 'postgres-0', text: 'container_memory_working_set_bytes reached 63.8Mi of 64Mi limit', verified: true }
          ]
        },
        playbook: {
          diff: 'resources.limits.memory: 64Mi -> 256Mi\nresources.requests.memory: 32Mi -> 128Mi',
          steps: [
            { order: 1, service: 'postgres', action: 'patch_memory_limit', params: { from: '64Mi', to: '256Mi' }, risk: 'high', requires_approval: true, verify: 'port 5432 accepting connections' },
            { order: 2, service: 'postgres', action: 'wait_for_ready', params: { timeout_s: 30 }, risk: 'low', requires_approval: false, verify: 'readiness probe 200 OK' },
            { order: 3, service: 'auth-service', action: 'rollout_restart', risk: 'low', requires_approval: false, verify: 'reconnects to postgres' },
            { order: 4, service: 'payment-service', action: 'rollout_restart', risk: 'low', requires_approval: false, verify: 'payment queue draining' },
            { order: 5, service: 'api-gateway', action: 'verify_health', risk: 'low', requires_approval: false, verify: 'error rate 0%' }
          ]
        }
      }
    }
  ];
}

function getK8sBadConfigMockEvents() {
  return [
    // T = 60ms: ROOT FAILURE EXPLODES INSTANTLY -> payment-service enters CrashLoopBackOff
    { delay: 60, type: 'service_update', payload: { id: 'payment-service', status: 'root_cause', metrics: { mem_mb: 22, mem_limit_mb: 256, cpu_pct: 2, restarts: 5 } } },
    { delay: 80, type: 'alert', payload: { id: 'a-bc-1', service: 'payment-service', severity: 'critical', message: 'Fatal panic: environment variable STRIPE_API_SECRET missing in revision #24', ts: '03:18:01' } },
    { delay: 100, type: 'agent_step', payload: { agent: 'triage', text: 'CrashLoopBackOff detected on payment-service revision #24. Outgoing laser blast wave initiated...', status: 'running' } },

    // Tier 2 Cascade (T = 1600ms): api-gateway fails as upstream payment is dead
    { delay: 1600, type: 'service_update', payload: { id: 'api-gateway', status: 'impacted', metrics: { mem_mb: 95, mem_limit_mb: 256, cpu_pct: 28, restarts: 0 } } },
    { delay: 1700, type: 'alert', payload: { id: 'a-bc-2', service: 'api-gateway', severity: 'critical', message: '503 Service Unavailable: upstream payment-service unhealthy', ts: '03:18:02' } },

    // Tier 3 Cascade (T = 3200ms): web-ui fails
    { delay: 3200, type: 'service_update', payload: { id: 'web-ui', status: 'impacted', metrics: { mem_mb: 60, mem_limit_mb: 128, cpu_pct: 19, restarts: 0 } } },
    { delay: 3300, type: 'alert', payload: { id: 'a-bc-3', service: 'web-ui', severity: 'critical', message: 'Checkout button disabled: payment backend unreachable', ts: '03:18:04' } },

    { delay: 4400, type: 'agent_step', payload: { agent: 'diagnose', text: 'Extracted crash log: panic: missing STRIPE_API_SECRET during init()', status: 'done' } },
    { delay: 5600, type: 'agent_step', payload: { agent: 'plan', text: 'Proposing 1-click rollback: kubectl rollout undo deployment/payment-service', status: 'done' } },
    {
      delay: 6400,
      type: 'incident_update',
      payload: {
        id: 'INC-105',
        status: 'awaiting_approval',
        scenario: 'bad_config',
        root_service: 'payment-service',
        impacted_services: ['api-gateway', 'web-ui'],
        raw_alert_count: 14,
        started_at: new Date().toISOString(),
        rca: {
          root_cause: 'Deployment revision #24 failed boot sequence due to missing required environment variable STRIPE_API_SECRET.',
          category: 'CrashLoopBackOff',
          confidence: 0.99,
          evidence: [
            { type: 'log', source: 'payment-service-58c9', line: 12, text: 'panic: missing STRIPE_API_SECRET during init()', verified: true },
            { type: 'k8s_event', source: 'payment-service', text: 'Back-off restarting failed container', verified: true }
          ]
        },
        playbook: {
          diff: 'image: payment-service:v2.4.1 (broken) -> payment-service:v2.4.0 (stable)',
          steps: [
            { order: 1, service: 'payment-service', action: 'rollback_deployment', params: { target_revision: 23 }, risk: 'medium', requires_approval: true, verify: 'pods in 1/1 Running state' },
            { order: 2, service: 'api-gateway', action: 'verify_health', params: {}, risk: 'low', requires_approval: false, verify: 'error rate 0%' }
          ]
        }
      }
    }
  ];
}

function getK8sCpuSpikeMockEvents() {
  return [
    // T = 60ms: ROOT FAILURE EXPLODES INSTANTLY -> auth-service hits 100% CPU
    { delay: 60, type: 'service_update', payload: { id: 'auth-service', status: 'root_cause', metrics: { mem_mb: 48, mem_limit_mb: 128, cpu_pct: 100, restarts: 0 } } },
    { delay: 80, type: 'alert', payload: { id: 'a-cpu-1', service: 'auth-service', severity: 'warning', message: 'CPU throttle ratio > 85% for 60s window (100% saturation)', ts: '03:22:10' } },
    { delay: 100, type: 'agent_step', payload: { agent: 'triage', text: 'CPU throttling alarm detected on auth-service (100% saturation). Laser blast wave initiated...', status: 'running' } },

    // Tier 2 Cascade (T = 1600ms): api-gateway degrades
    { delay: 1600, type: 'service_update', payload: { id: 'api-gateway', status: 'impacted', metrics: { mem_mb: 95, mem_limit_mb: 256, cpu_pct: 42, restarts: 0 } } },
    { delay: 1700, type: 'alert', payload: { id: 'a-cpu-2', service: 'api-gateway', severity: 'warning', message: 'P99 Latency degradation: /v1/auth taking 3200ms', ts: '03:22:14' } },

    { delay: 3000, type: 'agent_step', payload: { agent: 'diagnose', text: 'RCA verified: Cryptographic worker pool CPU starvation. Topology check passed.', status: 'done' } },
    { delay: 4200, type: 'agent_step', payload: { agent: 'plan', text: 'Autoscaling recommendation: Scale auth-service replicas from 1 to 3', status: 'done' } },
    {
      delay: 5000,
      type: 'incident_update',
      payload: {
        id: 'INC-106',
        status: 'awaiting_approval',
        scenario: 'cpu_spike',
        root_service: 'auth-service',
        impacted_services: ['api-gateway'],
        raw_alert_count: 8,
        started_at: new Date().toISOString(),
        rca: {
          root_cause: 'Cryptographic hashing thread pool saturated CPU (100% throttle ratio) on auth-service. Degrading P99 latency to 3200ms.',
          category: 'CPUSaturation',
          confidence: 0.96,
          evidence: [
            { type: 'metric', source: 'auth-service', text: 'container_cpu_cfs_throttled_periods_total > 85%', verified: true },
            { type: 'log', source: 'auth-service', line: 88, text: 'WARN: worker pool exhausted, task queue depth: 412', verified: true }
          ]
        },
        playbook: {
          diff: 'spec.replicas: 1 -> 3',
          steps: [
            { order: 1, service: 'auth-service', action: 'scale_deployment', params: { replicas: 3 }, risk: 'low', requires_approval: true, verify: 'HPA stabilization' },
            { order: 2, service: 'api-gateway', action: 'verify_latency', params: {}, risk: 'low', requires_approval: false, verify: 'P99 < 80ms' }
          ]
        }
      }
    }
  ];
}

function getK8sSlowLeakMockEvents() {
  return [
    { delay: 300, type: 'agent_step', payload: { agent: 'triage', text: 'Predictive Analyzer: Monitoring memory gradient across nodes...', status: 'running' } },
    { delay: 700, type: 'metric_point', payload: { service: 'postgres', mem_mb: 45, mem_limit_mb: 64, cpu_pct: 14 } },
    { delay: 1200, type: 'metric_point', payload: { service: 'postgres', mem_mb: 52, mem_limit_mb: 64, cpu_pct: 16 } },
    { delay: 1600, type: 'metric_point', payload: { service: 'postgres', mem_mb: 58, mem_limit_mb: 64, cpu_pct: 18 } },
    {
      delay: 1900,
      type: 'prediction',
      payload: {
        service: 'postgres',
        seconds: 142,
        trend: '+2.4MB / min',
        message: 'PostgreSQL memory limit exhaustion predicted in 2m 22s'
      }
    },
    { delay: 2100, type: 'agent_step', payload: { agent: 'diagnose', text: 'Linear regression forecast: Shared buffer pool gradient breaches 64Mi in 142s.', status: 'done' } },
    { delay: 2400, type: 'agent_step', payload: { agent: 'plan', text: 'PREDICTIVE SHIELD: Generated pre-emptive memory patch before crash occurs.', status: 'done' } },
    {
      delay: 2700,
      type: 'incident_update',
      payload: {
        id: 'INC-107',
        status: 'awaiting_approval',
        scenario: 'slow_leak',
        root_service: 'postgres',
        impacted_services: [],
        raw_alert_count: 2,
        started_at: new Date().toISOString(),
        rca: {
          root_cause: 'Linear memory exhaustion slope (+2.4MB/min) approaching 64Mi ceiling. Failure imminent in 142s if unmitigated.',
          category: 'PredictiveExhaustion',
          confidence: 0.98,
          evidence: [
            { type: 'metric', source: 'postgres-0', text: 'Memory gradient: +2.4MiB/min', verified: true },
            { type: 'forecast', source: 'predictor', text: 'Threshold breach estimated at T+142s', verified: true }
          ]
        },
        playbook: {
          diff: 'limits.memory: 64Mi -> 128Mi',
          steps: [
            { order: 1, service: 'postgres', action: 'preemptive_patch', params: { limit: '128Mi' }, risk: 'low', requires_approval: true, verify: 'headroom safe' }
          ]
        }
      }
    }
  ];
}

// ─────────────────────────────────────────────────────────────────────────────
// AMAZON HYPERSCALE SIMULATION GENERATORS (20-NODE CASCADE)
// ─────────────────────────────────────────────────────────────────────────────
function getAmazonDbOomMockEvents() {
  const events: any[] = [
    // T = 60ms: ROOT FAILURE EXPLODES INSTANTLY -> aurora-orders-db OOMKilled, Pod grows red, alerts immediately fire
    { delay: 60, type: 'service_update', payload: { id: 'aurora-orders-db', status: 'root_cause', metrics: { mem_mb: 4096, mem_limit_mb: 4096, cpu_pct: 95, restarts: 1 } } },
    { delay: 80, type: 'alert', payload: { id: 'amz-01', service: 'aurora-orders-db', severity: 'critical', message: 'RDS OOMKilled: shared_buffers saturated 4096Mi ceiling (ExitCode 137)', ts: '03:14:07.010' } },
    { delay: 100, type: 'agent_step', payload: { agent: 'triage', text: 'AWS CloudWatch Alert Ingested: aurora-orders-db RDS OOMKilled (ExitCode 137). Outgoing crimson blast wave initiated...', status: 'running' } },

    // Tier 2 Cascade (T = 1600ms): payment-service & order-service fail -> Outgoing arrows to cart & SQS turn Glowing Amber
    { delay: 1600, type: 'service_update', payload: { id: 'payment-service', status: 'impacted', metrics: { mem_mb: 410, mem_limit_mb: 1024, cpu_pct: 32, restarts: 0 } } },
    { delay: 1650, type: 'service_update', payload: { id: 'order-service', status: 'impacted', metrics: { mem_mb: 650, mem_limit_mb: 1024, cpu_pct: 48, restarts: 0 } } },
    { delay: 1750, type: 'alert', payload: { id: 'amz-02', service: 'payment-service', severity: 'critical', message: 'Aurora PostgreSQL connection pool exhausted (0/150 connections available)', ts: '03:14:08.800' } },
    { delay: 1850, type: 'alert', payload: { id: 'amz-03', service: 'payment-service', severity: 'critical', message: 'Amazon Pay 1-Click checkout write failure: connection timeout to aurora-orders-db', ts: '03:14:08.850' } },
    { delay: 1950, type: 'alert', payload: { id: 'amz-04', service: 'order-service', severity: 'critical', message: 'Saga order orchestrator failed: transaction ledger uncommitted', ts: '03:14:08.900' } },
    { delay: 2050, type: 'alert', payload: { id: 'amz-05', service: 'order-service', severity: 'critical', message: 'Circuit breaker OPEN for upstream aurora-orders-db.orders_ledger', ts: '03:14:08.950' } },

    // Tier 3 Cascade (T = 3200ms): cart-service & sqs-event-bus fail -> Outgoing arrows to api-gateway & logistics turn Glowing Amber
    { delay: 3200, type: 'service_update', payload: { id: 'cart-service', status: 'impacted', metrics: { mem_mb: 390, mem_limit_mb: 512, cpu_pct: 38, restarts: 0 } } },
    { delay: 3250, type: 'service_update', payload: { id: 'sqs-event-bus', status: 'impacted', metrics: { mem_mb: 260, mem_limit_mb: 512, cpu_pct: 22, restarts: 0 } } },
    { delay: 3350, type: 'alert', payload: { id: 'amz-06', service: 'cart-service', severity: 'critical', message: 'Checkout cart reservation failed: Order saga timeout on /v1/checkout/lock', ts: '03:14:10.500' } },
    { delay: 3450, type: 'alert', payload: { id: 'amz-07', service: 'sqs-event-bus', severity: 'warning', message: 'Dead Letter Queue (DLQ) alert: order_dispatch_queue received 340 dropouts', ts: '03:14:10.550' } },

    // Tier 4 Cascade (T = 4800ms): api-gateway, shipping-service, notification-service fail -> Outgoing arrows to frontends turn Glowing Amber
    { delay: 4800, type: 'service_update', payload: { id: 'api-gateway', status: 'impacted', metrics: { mem_mb: 790, mem_limit_mb: 1024, cpu_pct: 64, restarts: 0 } } },
    { delay: 4850, type: 'service_update', payload: { id: 'shipping-service', status: 'impacted', metrics: { mem_mb: 240, mem_limit_mb: 512, cpu_pct: 18, restarts: 0 } } },
    { delay: 4900, type: 'service_update', payload: { id: 'notification-service', status: 'impacted', metrics: { mem_mb: 210, mem_limit_mb: 512, cpu_pct: 14, restarts: 0 } } },
    { delay: 5000, type: 'alert', payload: { id: 'amz-08', service: 'api-gateway', severity: 'critical', message: '504 Gateway Timeout: /api/v2/orders/checkout took > 6000ms', ts: '03:14:12.200' } },
    { delay: 5100, type: 'alert', payload: { id: 'amz-09', service: 'api-gateway', severity: 'critical', message: 'HTTP 5xx rate exceeded 15% threshold across retail cluster (currently 86%)', ts: '03:14:12.250' } },

    // Tier 5 Cascade (T = 6400ms): web-storefront & mobile-bff fail -> Outgoing arrows to CloudFront turn Glowing Amber
    { delay: 6400, type: 'service_update', payload: { id: 'web-storefront', status: 'impacted', metrics: { mem_mb: 520, mem_limit_mb: 1024, cpu_pct: 35, restarts: 0 } } },
    { delay: 6450, type: 'service_update', payload: { id: 'mobile-bff', status: 'impacted', metrics: { mem_mb: 440, mem_limit_mb: 1024, cpu_pct: 29, restarts: 0 } } },
    { delay: 6550, type: 'alert', payload: { id: 'amz-10', service: 'web-storefront', severity: 'critical', message: 'Storefront checkout banner throwing 500: Unable to complete order', ts: '03:14:13.900' } },
    { delay: 6650, type: 'alert', payload: { id: 'amz-11', service: 'mobile-bff', severity: 'critical', message: 'Amazon iOS/Android app sync error: Order submission dropped', ts: '03:14:13.950' } },

    // Tier 6 Cascade (T = 8000ms): cloud-front fails
    { delay: 8000, type: 'service_update', payload: { id: 'cloud-front', status: 'impacted', metrics: { mem_mb: 230, mem_limit_mb: 512, cpu_pct: 25, restarts: 0 } } },
    { delay: 8100, type: 'alert', payload: { id: 'amz-12', service: 'cloud-front', severity: 'critical', message: 'CloudFront edge PoP error budget burned: Origin return rate 91% 5xx', ts: '03:14:15.600' } },

    // AI Agents correlation & diagnosis
    { delay: 9200, type: 'agent_step', payload: { agent: 'triage', text: 'Graph topological correlation applied: 84 raw alerts collapsed into 1 root incident (aurora-orders-db).', status: 'done' } },
    { delay: 10400, type: 'agent_step', payload: { agent: 'diagnose', text: 'RCA Confirmed: aurora-orders-db breached 4096Mi cgroup ceiling. Connection pool deadlocks propagated to 8 downstream microservices.', status: 'done' } },
    { delay: 11400, type: 'agent_step', payload: { agent: 'plan', text: 'Synthesized 6-stage AWS RDS recovery playbook (Buffer pool patch -> Probes -> Circuit breaker reset). Awaiting SRE authorization.', status: 'done' } },

    {
      delay: 12200,
      type: 'incident_update',
      payload: {
        id: 'INC-204',
        status: 'awaiting_approval',
        scenario: 'db_oom',
        root_service: 'aurora-orders-db',
        impacted_services: [
          'payment-service',
          'order-service',
          'cart-service',
          'sqs-event-bus',
          'api-gateway',
          'shipping-service',
          'notification-service',
          'web-storefront',
          'mobile-bff',
          'cloud-front'
        ],
        raw_alert_count: 84,
        started_at: '2026-10-09T03:14:07Z',
        resolved_at: null,
        rca: {
          root_cause: 'Amazon Aurora PostgreSQL primary cluster terminated with exit code 137 (OOMKilled) after saturating its 4096Mi memory limit.',
          category: 'OOMKilled',
          confidence: 0.98,
          evidence: [
            { type: 'k8s_event', source: 'aurora-orders-db-0', text: 'Reason: OOMKilled, ExitCode: 137, Memory: 4088Mi/4096Mi', verified: true },
            { type: 'log', source: 'aurora-orders-db-0', line: 104, text: 'FATAL: out of memory allocating shared buffer cache', verified: true },
            { type: 'metric', source: 'aurora-orders-db-0', text: 'buffer_pool_saturation peaked at 99.8% capacity', verified: true }
          ],
          similar_incident: { id: 'INC-198', similarity: 0.96 }
        },
        playbook: {
          diff: 'resources.limits.memory: 4096Mi -> 8192Mi\nresources.requests.memory: 2048Mi -> 4096Mi',
          steps: [
            { order: 1, service: 'aurora-orders-db', action: 'patch_memory_limit', params: { from: '4096Mi', to: '8192Mi' }, risk: 'high', requires_approval: true, verify: 'port 5432 accepting connections' },
            { order: 2, service: 'aurora-orders-db', action: 'wait_for_ready', params: { timeout_s: 30 }, risk: 'low', requires_approval: false, verify: 'readiness probe 200 OK' },
            { order: 3, service: 'payment-service', action: 'rollout_restart', risk: 'low', requires_approval: false, verify: 'payment gateway 200 OK' },
            { order: 4, service: 'order-service', action: 'rollout_restart', risk: 'low', requires_approval: false, verify: 'order saga active' },
            { order: 5, service: 'api-gateway', action: 'reset_circuit_breaker', risk: 'low', requires_approval: false, verify: 'error rate below 0.1%' },
            { order: 6, service: 'web-storefront', action: 'verify_health', risk: 'low', requires_approval: false, verify: 'storefront 200 OK' }
          ]
        },
        timeline: [
          { t_s: 0, event: 'ExitCode 137: aurora-orders-db OOMKilled (Crimson wave triggered)' },
          { t_s: 1.6, event: 'Blast radius propagated across Tier 2 (payment & order services degraded)' },
          { t_s: 3.2, event: 'Blast radius propagated across Tier 3 & 4 (cart & SQS event bus degraded)' },
          { t_s: 4.8, event: 'Blast radius propagated across Tier 4 (API Gateway & Logistics degraded)' },
          { t_s: 6.4, event: 'Blast radius propagated across Tier 5 (Web Storefront & Mobile BFF degraded)' },
          { t_s: 8.0, event: 'Blast radius propagated across Tier 6 (CloudFront Edge CDN error budget burned)' },
          { t_s: 9.2, event: 'Topological correlation collapsed 84 alerts -> 1 root incident' },
          { t_s: 11.4, event: 'Recovery playbook synthesized. Awaiting SRE authorization' }
        ]
      }
    }
  ];

  return events;
}

function executeAmazonDbOomHeal() {
  const healSteps = [
    { delay: 300, type: 'agent_step', payload: { agent: 'execute', text: 'Step 1: Expanding Aurora memory limit to 8192Mi...', status: 'running' } },
    { delay: 800, type: 'playbook_step', payload: { order: 1, status: 'done' } },
    { delay: 1200, type: 'service_update', payload: { id: 'aurora-orders-db', status: 'recovering', metrics: { mem_mb: 3200, mem_limit_mb: 8192, cpu_pct: 22, restarts: 0 } } },

    { delay: 1600, type: 'agent_step', payload: { agent: 'verify', text: 'Step 2: Probing Aurora PostgreSQL readiness (port 5432)...', status: 'running' } },
    { delay: 2100, type: 'playbook_step', payload: { order: 2, status: 'done' } },
    { delay: 2300, type: 'service_update', payload: { id: 'aurora-orders-db', status: 'healthy', metrics: { mem_mb: 3100, mem_limit_mb: 8192, cpu_pct: 16, restarts: 0 } } },

    { delay: 2700, type: 'agent_step', payload: { agent: 'execute', text: 'Step 3: Rolling restart of payment-service & order-service...', status: 'running' } },
    { delay: 3300, type: 'playbook_step', payload: { order: 3, status: 'done' } },
    { delay: 3500, type: 'service_update', payload: { id: 'payment-service', status: 'healthy', metrics: { mem_mb: 340, mem_limit_mb: 1024, cpu_pct: 12, restarts: 0 } } },
    { delay: 3600, type: 'service_update', payload: { id: 'order-service', status: 'healthy', metrics: { mem_mb: 480, mem_limit_mb: 1024, cpu_pct: 18, restarts: 0 } } },

    { delay: 4200, type: 'service_update', payload: { id: 'cart-service', status: 'healthy', metrics: { mem_mb: 320, mem_limit_mb: 512, cpu_pct: 14, restarts: 0 } } },
    { delay: 4400, type: 'service_update', payload: { id: 'sqs-event-bus', status: 'healthy', metrics: { mem_mb: 195, mem_limit_mb: 512, cpu_pct: 7, restarts: 0 } } },

    { delay: 5000, type: 'agent_step', payload: { agent: 'verify', text: 'Step 4: Resetting circuit breakers on api-gateway & downstream logistics...', status: 'running' } },
    { delay: 5600, type: 'playbook_step', payload: { order: 5, status: 'done' } },
    { delay: 5800, type: 'service_update', payload: { id: 'api-gateway', status: 'healthy', metrics: { mem_mb: 610, mem_limit_mb: 1024, cpu_pct: 25, restarts: 0 } } },
    { delay: 6000, type: 'service_update', payload: { id: 'shipping-service', status: 'healthy', metrics: { mem_mb: 210, mem_limit_mb: 512, cpu_pct: 7, restarts: 0 } } },
    { delay: 6200, type: 'service_update', payload: { id: 'notification-service', status: 'healthy', metrics: { mem_mb: 180, mem_limit_mb: 512, cpu_pct: 6, restarts: 0 } } },

    { delay: 6800, type: 'playbook_step', payload: { order: 6, status: 'done' } },
    { delay: 7100, type: 'service_update', payload: { id: 'web-storefront', status: 'healthy', metrics: { mem_mb: 410, mem_limit_mb: 1024, cpu_pct: 18, restarts: 0 } } },
    { delay: 7300, type: 'service_update', payload: { id: 'mobile-bff', status: 'healthy', metrics: { mem_mb: 370, mem_limit_mb: 1024, cpu_pct: 15, restarts: 0 } } },
    { delay: 8200, type: 'service_update', payload: { id: 'cloud-front', status: 'healthy', metrics: { mem_mb: 190, mem_limit_mb: 512, cpu_pct: 12, restarts: 0 } } },

    { delay: 8800, type: 'agent_step', payload: { agent: 'verify', text: 'All 20 nodes verified 200 OK. Amazon Hyperscale topology fully restored in 42s.', status: 'done' } },
    {
      delay: 9400,
      type: 'incident_update',
      payload: {
        id: 'INC-204',
        status: 'resolved',
        scenario: 'db_oom',
        root_service: 'aurora-orders-db',
        impacted_services: [],
        raw_alert_count: 84,
        started_at: '2026-10-09T03:14:07Z',
        resolved_at: new Date().toISOString(),
        rca: {
          root_cause: 'Aurora PostgreSQL OOMKilled resolved via 8192Mi memory limit expansion and topological cascading recovery.',
          category: 'OOMKilled',
          confidence: 0.98,
          evidence: [
            { type: 'k8s_event', source: 'aurora-orders-db-0', text: 'Memory patched to 8192Mi', verified: true },
            { type: 'metric', source: 'aurora-orders-db-0', text: 'Headroom verified at 61% free', verified: true }
          ]
        },
        playbook: {
          diff: 'resources.limits.memory: 4096Mi -> 8192Mi',
          steps: []
        }
      }
    }
  ];

  healSteps.forEach((item) => {
    const timeout = setTimeout(() => {
      applyWsEvent(item);
    }, item.delay);
    activeTimeouts.push(timeout);
  });
}

function getAmazonBadConfigMockEvents() {
  return [
    // T = 60ms: ROOT FAILURE EXPLODES INSTANTLY -> payment-service enters CrashLoopBackOff
    { delay: 60, type: 'service_update', payload: { id: 'payment-service', status: 'root_cause', metrics: { mem_mb: 110, mem_limit_mb: 1024, cpu_pct: 2, restarts: 6 } } },
    { delay: 80, type: 'alert', payload: { id: 'amz-bc-1', service: 'payment-service', severity: 'critical', message: 'Fatal panic: STRIPE_API_SECRET and AMAZON_PAY_KEY missing in deployment #43', ts: '03:18:01' } },
    { delay: 100, type: 'agent_step', payload: { agent: 'triage', text: 'CrashLoopBackOff detected on payment-service revision #43. Outgoing crimson blast wave initiated...', status: 'running' } },

    // Tier 2 Cascade (T = 1600ms): order-service & cart-service fail
    { delay: 1600, type: 'service_update', payload: { id: 'order-service', status: 'impacted', metrics: { mem_mb: 580, mem_limit_mb: 1024, cpu_pct: 35, restarts: 0 } } },
    { delay: 1650, type: 'service_update', payload: { id: 'cart-service', status: 'impacted', metrics: { mem_mb: 360, mem_limit_mb: 512, cpu_pct: 28, restarts: 0 } } },
    { delay: 1750, type: 'alert', payload: { id: 'amz-bc-2', service: 'order-service', severity: 'critical', message: 'Downstream payment-service 503: Unable to charge order #884920', ts: '03:18:03' } },

    // Tier 3 Cascade (T = 3200ms): api-gateway fails
    { delay: 3200, type: 'service_update', payload: { id: 'api-gateway', status: 'impacted', metrics: { mem_mb: 750, mem_limit_mb: 1024, cpu_pct: 48, restarts: 0 } } },
    { delay: 3300, type: 'alert', payload: { id: 'amz-bc-3', service: 'api-gateway', severity: 'critical', message: 'Route /api/v2/checkout failing with 503 Service Unavailable', ts: '03:18:04' } },

    // Tier 4 Cascade (T = 4800ms): web-storefront & mobile-bff fail
    { delay: 4800, type: 'service_update', payload: { id: 'web-storefront', status: 'impacted', metrics: { mem_mb: 490, mem_limit_mb: 1024, cpu_pct: 26, restarts: 0 } } },
    { delay: 4850, type: 'service_update', payload: { id: 'mobile-bff', status: 'impacted', metrics: { mem_mb: 420, mem_limit_mb: 1024, cpu_pct: 24, restarts: 0 } } },

    { delay: 6000, type: 'agent_step', payload: { agent: 'diagnose', text: 'Crash log identified: Missing environment variable secrets in revision #43. Order saga impacted.', status: 'done' } },
    { delay: 7200, type: 'agent_step', payload: { agent: 'plan', text: 'Generated 1-click rollback to revision #42 (payment-service:v3.2.0-stable).', status: 'done' } },
    {
      delay: 8000,
      type: 'incident_update',
      payload: {
        id: 'INC-205',
        status: 'awaiting_approval',
        scenario: 'bad_config',
        root_service: 'payment-service',
        impacted_services: ['order-service', 'cart-service', 'api-gateway', 'web-storefront', 'mobile-bff'],
        raw_alert_count: 28,
        started_at: new Date().toISOString(),
        rca: {
          root_cause: 'Deployment revision #43 missing Stripe & Amazon Pay credentials. Initiated CrashLoopBackOff.',
          category: 'CrashLoopBackOff',
          confidence: 0.99,
          evidence: [
            { type: 'log', source: 'payment-service-pod-9', line: 18, text: 'panic: STRIPE_API_SECRET missing in init()', verified: true },
            { type: 'k8s_event', source: 'payment-service', text: 'Back-off restarting failed container', verified: true }
          ]
        },
        playbook: {
          diff: 'image: payment-service:v3.2.1-broken -> payment-service:v3.2.0-stable (rev 42)',
          steps: [
            { order: 1, service: 'payment-service', action: 'rollback_deployment', params: { target_revision: 42 }, risk: 'medium', requires_approval: true, verify: '1/1 Running state' },
            { order: 2, service: 'order-service', action: 'flush_circuit_breaker', params: {}, risk: 'low', requires_approval: false, verify: 'order processing resumed' },
            { order: 3, service: 'api-gateway', action: 'verify_health', params: {}, risk: 'low', requires_approval: false, verify: '0% 503 error rate' }
          ]
        }
      }
    }
  ];
}

function executeAmazonBadConfigHeal() {
  const healSteps = [
    { delay: 300, type: 'agent_step', payload: { agent: 'execute', text: 'Step 1: Rolling back payment-service to revision #42...', status: 'running' } },
    { delay: 700, type: 'playbook_step', payload: { order: 1, status: 'done' } },
    { delay: 900, type: 'service_update', payload: { id: 'payment-service', status: 'recovering', metrics: { mem_mb: 320, mem_limit_mb: 1024, cpu_pct: 14, restarts: 0 } } },
    { delay: 1200, type: 'agent_step', payload: { agent: 'verify', text: 'Step 2: Probing /healthz (Stripe & Amazon Pay keys loaded)...', status: 'running' } },
    { delay: 1600, type: 'playbook_step', payload: { order: 2, status: 'done' } },
    { delay: 1800, type: 'service_update', payload: { id: 'payment-service', status: 'healthy', metrics: { mem_mb: 340, mem_limit_mb: 1024, cpu_pct: 12, restarts: 0 } } },
    { delay: 2400, type: 'service_update', payload: { id: 'order-service', status: 'healthy', metrics: { mem_mb: 480, mem_limit_mb: 1024, cpu_pct: 22, restarts: 0 } } },
    { delay: 2600, type: 'service_update', payload: { id: 'cart-service', status: 'healthy', metrics: { mem_mb: 320, mem_limit_mb: 512, cpu_pct: 16, restarts: 0 } } },
    { delay: 3200, type: 'service_update', payload: { id: 'api-gateway', status: 'healthy', metrics: { mem_mb: 620, mem_limit_mb: 1024, cpu_pct: 28, restarts: 0 } } },
    { delay: 3800, type: 'service_update', payload: { id: 'web-storefront', status: 'healthy', metrics: { mem_mb: 420, mem_limit_mb: 1024, cpu_pct: 20, restarts: 0 } } },
    { delay: 4000, type: 'service_update', payload: { id: 'mobile-bff', status: 'healthy', metrics: { mem_mb: 380, mem_limit_mb: 1024, cpu_pct: 18, restarts: 0 } } },
    { delay: 4500, type: 'agent_step', payload: { agent: 'verify', text: 'Rollback verified 200 OK across Amazon e-commerce cluster.', status: 'done' } },
    {
      delay: 4900,
      type: 'incident_update',
      payload: {
        id: 'INC-205',
        status: 'resolved',
        scenario: 'bad_config',
        root_service: 'payment-service',
        impacted_services: [],
        raw_alert_count: 28,
        started_at: new Date().toISOString(),
        resolved_at: new Date().toISOString(),
        rca: {
          root_cause: 'Rollback to stable deployment revision #42 restored full payment processing capability.',
          category: 'CrashLoopBackOff',
          confidence: 0.99,
          evidence: [{ type: 'log', source: 'payment-service-pod-9', text: 'Rollback verified', verified: true }]
        },
        playbook: {
          diff: 'image: payment-service:v3.2.0-stable',
          steps: []
        }
      }
    }
  ];

  healSteps.forEach((item) => {
    const timeout = setTimeout(() => {
      applyWsEvent(item);
    }, item.delay);
    activeTimeouts.push(timeout);
  });
}

function getAmazonCpuSpikeMockEvents() {
  return [
    // T = 60ms: ROOT FAILURE EXPLODES INSTANTLY -> auth-service hits 100% CPU
    { delay: 60, type: 'service_update', payload: { id: 'auth-service', status: 'root_cause', metrics: { mem_mb: 380, mem_limit_mb: 512, cpu_pct: 100, restarts: 0 } } },
    { delay: 80, type: 'alert', payload: { id: 'amz-cpu-1', service: 'auth-service', severity: 'warning', message: 'Cryptographic token verification thread pool saturated (CPU > 98%)', ts: '03:22:10' } },
    { delay: 100, type: 'agent_step', payload: { agent: 'triage', text: 'CPU throttle alarm triggered on Cognito / IAM auth-service (100% saturation). Laser blast wave initiated...', status: 'running' } },

    // Tier 2 Cascade (T = 1600ms): api-gateway degrades
    { delay: 1600, type: 'service_update', payload: { id: 'api-gateway', status: 'impacted', metrics: { mem_mb: 780, mem_limit_mb: 1024, cpu_pct: 54, restarts: 0 } } },
    { delay: 1700, type: 'alert', payload: { id: 'amz-cpu-2', service: 'api-gateway', severity: 'warning', message: 'P99 Latency degradation: /v2/auth taking 4100ms', ts: '03:22:15' } },

    // Tier 3 Cascade (T = 3200ms): web-storefront & mobile-bff degrade
    { delay: 3200, type: 'service_update', payload: { id: 'web-storefront', status: 'impacted', metrics: { mem_mb: 480, mem_limit_mb: 1024, cpu_pct: 32, restarts: 0 } } },
    { delay: 3250, type: 'service_update', payload: { id: 'mobile-bff', status: 'impacted', metrics: { mem_mb: 430, mem_limit_mb: 1024, cpu_pct: 28, restarts: 0 } } },

    { delay: 4400, type: 'agent_step', payload: { agent: 'diagnose', text: 'Cryptographic worker starvation confirmed. Auto-scaling HPA recommended.', status: 'done' } },
    { delay: 5600, type: 'agent_step', payload: { agent: 'plan', text: 'Autoscale recommendation: Scale auth-service replicas from 2 to 6.', status: 'done' } },
    {
      delay: 6400,
      type: 'incident_update',
      payload: {
        id: 'INC-206',
        status: 'awaiting_approval',
        scenario: 'cpu_spike',
        root_service: 'auth-service',
        impacted_services: ['api-gateway', 'web-storefront', 'mobile-bff'],
        raw_alert_count: 16,
        started_at: new Date().toISOString(),
        rca: {
          root_cause: 'Cryptographic hashing thread pool saturated CPU (100% throttle ratio) on auth-service.',
          category: 'CPUSaturation',
          confidence: 0.97,
          evidence: [
            { type: 'metric', source: 'auth-service', text: 'CPU throttle ratio 99.4%', verified: true },
            { type: 'log', source: 'auth-service', line: 142, text: 'WARN: worker queue backpressure 620 items', verified: true }
          ]
        },
        playbook: {
          diff: 'spec.replicas: 2 -> 6',
          steps: [
            { order: 1, service: 'auth-service', action: 'scale_deployment', params: { replicas: 6 }, risk: 'low', requires_approval: true, verify: 'HPA stabilization' },
            { order: 2, service: 'api-gateway', action: 'verify_latency', params: {}, risk: 'low', requires_approval: false, verify: 'P99 < 50ms' }
          ]
        }
      }
    }
  ];
}

function executeAmazonCpuSpikeHeal() {
  const healSteps = [
    { delay: 300, type: 'agent_step', payload: { agent: 'execute', text: 'Step 1: Scaling auth-service replicas from 2 to 6...', status: 'running' } },
    { delay: 700, type: 'playbook_step', payload: { order: 1, status: 'done' } },
    { delay: 1000, type: 'service_update', payload: { id: 'auth-service', status: 'recovering', metrics: { mem_mb: 280, mem_limit_mb: 512, cpu_pct: 42, restarts: 0 } } },
    { delay: 1400, type: 'agent_step', payload: { agent: 'verify', text: 'Step 2: Monitoring HPA target metrics & P99 latency...', status: 'running' } },
    { delay: 1800, type: 'playbook_step', payload: { order: 2, status: 'done' } },
    { delay: 2000, type: 'service_update', payload: { id: 'auth-service', status: 'healthy', metrics: { mem_mb: 260, mem_limit_mb: 512, cpu_pct: 16, restarts: 0 } } },
    { delay: 2200, type: 'service_update', payload: { id: 'api-gateway', status: 'healthy', metrics: { mem_mb: 620, mem_limit_mb: 1024, cpu_pct: 28, restarts: 0 } } },
    { delay: 2400, type: 'service_update', payload: { id: 'web-storefront', status: 'healthy', metrics: { mem_mb: 420, mem_limit_mb: 1024, cpu_pct: 21, restarts: 0 } } },
    { delay: 2600, type: 'service_update', payload: { id: 'mobile-bff', status: 'healthy', metrics: { mem_mb: 380, mem_limit_mb: 1024, cpu_pct: 18, restarts: 0 } } },
    { delay: 2900, type: 'agent_step', payload: { agent: 'verify', text: 'Autoscaling validated. P99 latency restored to 28ms across 6 pods.', status: 'done' } },
    {
      delay: 3100,
      type: 'incident_update',
      payload: {
        id: 'INC-206',
        status: 'resolved',
        scenario: 'cpu_spike',
        root_service: 'auth-service',
        impacted_services: [],
        raw_alert_count: 16,
        started_at: new Date().toISOString(),
        resolved_at: new Date().toISOString(),
        rca: {
          root_cause: 'CPU throttling resolved by horizontal scale-out to 6 replicas.',
          category: 'CPUSaturation',
          confidence: 0.98,
          evidence: [{ type: 'metric', source: 'auth-service', text: 'CPU dropped to 16%', verified: true }]
        },
        playbook: {
          diff: 'spec.replicas: 2 -> 6',
          steps: []
        }
      }
    }
  ];

  healSteps.forEach((item) => {
    const timeout = setTimeout(() => {
      applyWsEvent(item);
    }, item.delay);
    activeTimeouts.push(timeout);
  });
}

function getAmazonSlowLeakMockEvents() {
  return [
    { delay: 300, type: 'agent_step', payload: { agent: 'triage', text: 'Predictive Analyzer: Monitoring Aurora buffer pool gradient...', status: 'running' } },
    { delay: 700, type: 'metric_point', payload: { service: 'aurora-orders-db', mem_mb: 3600, mem_limit_mb: 4096, cpu_pct: 20 } },
    { delay: 1100, type: 'metric_point', payload: { service: 'aurora-orders-db', mem_mb: 3850, mem_limit_mb: 4096, cpu_pct: 22 } },
    { delay: 1500, type: 'metric_point', payload: { service: 'aurora-orders-db', mem_mb: 3990, mem_limit_mb: 4096, cpu_pct: 24 } },
    {
      delay: 1800,
      type: 'prediction',
      payload: {
        service: 'aurora-orders-db',
        seconds: 178,
        trend: '+18.5MB / min',
        message: 'Aurora buffer pool exhaustion predicted in 2m 58s'
      }
    },
    { delay: 2100, type: 'agent_step', payload: { agent: 'diagnose', text: 'Linear regression forecast: Shared buffer pool slope reaches ceiling in 178s.', status: 'done' } },
    { delay: 2400, type: 'agent_step', payload: { agent: 'plan', text: 'PREDICTIVE SHIELD: Synthesizing pre-emptive memory patch before outage occurs.', status: 'done' } },
    {
      delay: 2700,
      type: 'incident_update',
      payload: {
        id: 'INC-207',
        status: 'awaiting_approval',
        scenario: 'slow_leak',
        root_service: 'aurora-orders-db',
        impacted_services: [],
        raw_alert_count: 4,
        started_at: new Date().toISOString(),
        rca: {
          root_cause: 'Linear memory exhaustion slope (+18.5MB/min) approaching 4096Mi ceiling. Outage predicted in 178s.',
          category: 'PredictiveExhaustion',
          confidence: 0.98,
          evidence: [
            { type: 'metric', source: 'aurora-orders-db', text: 'Buffer pool gradient +18.5MiB/min', verified: true },
            { type: 'forecast', source: 'predictor', text: 'Threshold breach estimated at T+178s', verified: true }
          ]
        },
        playbook: {
          diff: 'limits.memory: 4096Mi -> 8192Mi',
          steps: [
            { order: 1, service: 'aurora-orders-db', action: 'preemptive_patch', params: { limit: '8192Mi' }, risk: 'low', requires_approval: true, verify: 'headroom safe' }
          ]
        }
      }
    }
  ];
}

function executeAmazonSlowLeakHeal() {
  const healSteps = [
    { delay: 300, type: 'agent_step', payload: { agent: 'execute', text: 'Pre-emptive remediation: Expanding Aurora memory limit to 8192Mi...', status: 'running' } },
    { delay: 700, type: 'service_update', payload: { id: 'aurora-orders-db', status: 'recovering', metrics: { mem_mb: 3500, mem_limit_mb: 8192, cpu_pct: 18, restarts: 0 } } },
    { delay: 1200, type: 'agent_step', payload: { agent: 'verify', text: 'Memory gradient stabilized. Zero customer dropouts occurred.', status: 'done' } },
    { delay: 1500, type: 'service_update', payload: { id: 'aurora-orders-db', status: 'healthy', metrics: { mem_mb: 3300, mem_limit_mb: 8192, cpu_pct: 15, restarts: 0 } } },
    {
      delay: 1800,
      type: 'incident_update',
      payload: {
        id: 'INC-207',
        status: 'resolved',
        scenario: 'slow_leak',
        root_service: 'aurora-orders-db',
        impacted_services: [],
        raw_alert_count: 4,
        started_at: new Date().toISOString(),
        resolved_at: new Date().toISOString(),
        rca: {
          root_cause: 'Predictive memory exhaustion mitigated 178s ahead of crash. Zero downtime on checkout flow.',
          category: 'PredictiveRemediation',
          confidence: 0.99,
          evidence: [{ type: 'prediction', source: 'aurora-orders-db', text: 'Gradient countered before threshold', verified: true }]
        },
        playbook: {
          diff: 'limits.memory: 4096Mi -> 8192Mi',
          steps: []
        }
      }
    }
  ];

  healSteps.forEach((item) => {
    const timeout = setTimeout(() => {
      applyWsEvent(item);
    }, item.delay);
    activeTimeouts.push(timeout);
  });
}
