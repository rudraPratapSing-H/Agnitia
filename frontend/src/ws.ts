// frontend/src/ws.ts - WebSocket Manager & 4-Scenario Deterministic Replayer
import { applyWsEvent, setWsConnected, setSimulating, resetStore } from './store';
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

// Deterministic Mock Event Replayer for All 4 Scenarios
export function playScenario(scenarioId: string) {
  clearActiveSimulation();
  resetStore();
  currentActiveScenario = scenarioId;

  // Run the immediate local simulation so UI responds instantly
  runLocalSimulation(scenarioId);

  // Notify live backend in parallel
  fetch(`http://localhost:8000/api/chaos/${scenarioId}`, { method: 'POST' }).catch(() => {});
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

function runLocalSimulation(scenarioId: string) {
  console.log(`Running standalone deterministic simulation for: ${scenarioId}`);
  setSimulating(true, scenarioId);

  let eventsList: any[] = [];

  if (scenarioId === 'db_oom') {
    eventsList = dbOomMockData.events;
  } else if (scenarioId === 'bad_config') {
    eventsList = getBadConfigMockEvents();
  } else if (scenarioId === 'cpu_spike') {
    eventsList = getCpuSpikeMockEvents();
  } else if (scenarioId === 'slow_leak') {
    eventsList = getSlowLeakMockEvents();
  } else {
    eventsList = dbOomMockData.events;
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

  if (currentActiveScenario === 'bad_config') {
    executeBadConfigHeal();
  } else if (currentActiveScenario === 'cpu_spike') {
    executeCpuSpikeHeal();
  } else if (currentActiveScenario === 'slow_leak') {
    executeSlowLeakHeal();
  } else {
    executeDbOomHeal();
  }
}

// 1. DB OOM Heal Flow
function executeDbOomHeal() {
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
          diff: "resources.limits.memory: 64Mi -> 256Mi",
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

// 2. Bad Config Heal Flow
function executeBadConfigHeal() {
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
          evidence: [
            { type: 'log', source: 'payment-service-58c9', line: 12, text: 'Rollback to rev 23 successful', verified: true }
          ]
        },
        playbook: {
          diff: "image: payment-service:v2.4.0 (stable revision #23)",
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

// 3. CPU Spike Heal Flow
function executeCpuSpikeHeal() {
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
          evidence: [
            { type: 'metric', source: 'auth-service', text: 'CPU dropped from 99% to 18%', verified: true }
          ]
        },
        playbook: {
          diff: "spec.replicas: 1 -> 3",
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

// 4. Slow Leak Heal Flow
function executeSlowLeakHeal() {
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
          evidence: [
            { type: 'prediction', source: 'postgres-0', text: 'Gradient +2.4MB/min countered before breach', verified: true }
          ]
        },
        playbook: {
          diff: "limits.memory: 64Mi -> 128Mi",
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

function getBadConfigMockEvents() {
  return [
    { delay: 300, type: 'agent_step', payload: { agent: 'triage', text: 'CrashLoopBackOff detected on payment-service...', status: 'running' } },
    { delay: 600, type: 'service_update', payload: { id: 'payment-service', status: 'root_cause', metrics: { mem_mb: 22, mem_limit_mb: 256, cpu_pct: 2, restarts: 5 } } },
    { delay: 800, type: 'service_update', payload: { id: 'api-gateway', status: 'impacted', metrics: { mem_mb: 95, mem_limit_mb: 256, cpu_pct: 28, restarts: 0 } } },
    { delay: 900, type: 'service_update', payload: { id: 'web-ui', status: 'impacted', metrics: { mem_mb: 60, mem_limit_mb: 128, cpu_pct: 19, restarts: 0 } } },
    { delay: 1000, type: 'alert', payload: { id: 'a-bc-1', service: 'payment-service', severity: 'critical', message: 'Fatal panic: environment variable STRIPE_API_SECRET missing in revision #24', ts: '03:18:01' } },
    { delay: 1200, type: 'alert', payload: { id: 'a-bc-2', service: 'api-gateway', severity: 'critical', message: '503 Service Unavailable: upstream payment-service unhealthy', ts: '03:18:02' } },
    { delay: 1400, type: 'agent_step', payload: { agent: 'diagnose', text: 'Extracted crash log: panic: missing STRIPE_API_SECRET during init()', status: 'done' } },
    { delay: 1800, type: 'agent_step', payload: { agent: 'plan', text: 'Proposing 1-click rollback: kubectl rollout undo deployment/payment-service', status: 'done' } },
    {
      delay: 2200,
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
          diff: "image: payment-service:v2.4.1 (broken) -> payment-service:v2.4.0 (stable)",
          steps: [
            { order: 1, service: 'payment-service', action: 'rollback_deployment', params: { target_revision: 23 }, risk: 'medium', requires_approval: true, verify: 'pods in 1/1 Running state' },
            { order: 2, service: 'api-gateway', action: 'verify_health', params: {}, risk: 'low', requires_approval: false, verify: 'error rate 0%' }
          ]
        }
      }
    }
  ];
}

function getCpuSpikeMockEvents() {
  return [
    { delay: 300, type: 'agent_step', payload: { agent: 'triage', text: 'CPU throttling alarm detected on auth-service (100% saturation)...', status: 'running' } },
    { delay: 600, type: 'service_update', payload: { id: 'auth-service', status: 'root_cause', metrics: { mem_mb: 48, mem_limit_mb: 128, cpu_pct: 99, restarts: 0 } } },
    { delay: 800, type: 'alert', payload: { id: 'a-cpu-1', service: 'auth-service', severity: 'warning', message: 'CPU throttle ratio > 85% for 60s window', ts: '03:22:10' } },
    { delay: 1000, type: 'service_update', payload: { id: 'api-gateway', status: 'impacted', metrics: { mem_mb: 95, mem_limit_mb: 256, cpu_pct: 42, restarts: 0 } } },
    { delay: 1200, type: 'alert', payload: { id: 'a-cpu-2', service: 'api-gateway', severity: 'warning', message: 'P99 Latency degradation: /v1/auth taking 3200ms', ts: '03:22:14' } },
    { delay: 1500, type: 'agent_step', payload: { agent: 'diagnose', text: 'RCA verified: Cryptographic worker pool CPU starvation. Topology check passed.', status: 'done' } },
    { delay: 1800, type: 'agent_step', payload: { agent: 'plan', text: 'Autoscaling recommendation: Scale auth-service replicas from 1 to 3', status: 'done' } },
    {
      delay: 2200,
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
          diff: "spec.replicas: 1 -> 3",
          steps: [
            { order: 1, service: 'auth-service', action: 'scale_deployment', params: { replicas: 3 }, risk: 'low', requires_approval: true, verify: 'HPA stabilization' },
            { order: 2, service: 'api-gateway', action: 'verify_latency', params: {}, risk: 'low', requires_approval: false, verify: 'P99 < 80ms' }
          ]
        }
      }
    }
  ];
}

function getSlowLeakMockEvents() {
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
          diff: "limits.memory: 64Mi -> 128Mi",
          steps: [
            { order: 1, service: 'postgres', action: 'preemptive_patch', params: { limit: '128Mi' }, risk: 'low', requires_approval: true, verify: 'headroom safe' }
          ]
        }
      }
    }
  ];
}
