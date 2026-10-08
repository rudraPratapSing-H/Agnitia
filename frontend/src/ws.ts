// frontend/src/ws.js - WebSocket Manager & Standalone Mock Event Replayer
import { applyWsEvent, setWsConnected, setSimulating, resetStore } from './store';
import dbOomMockData from './mock/events_db_oom.json';

let socket = null;
let reconnectTimer = null;
let activeTimeouts = [];

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
      // Attempt silent auto-reconnect every 4s
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

export function sendWsMessage(type, payload) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type, payload }));
    return true;
  }
  return false;
}

export function clearActiveSimulation() {
  activeTimeouts.forEach(t => clearTimeout(t));
  activeTimeouts = [];
  setSimulating(false, null);
}

// Deterministic Mock Event Replayer for Zero-Backend Standalone Demo
export function playScenario(scenarioId: string) {
  clearActiveSimulation();
  resetStore();

  const isLiveConnected = socket && socket.readyState === WebSocket.OPEN;

  // If live backend is connected, trigger backend injection endpoint
  if (isLiveConnected) {
    fetch(`http://localhost:8000/api/chaos/${scenarioId}`, { method: 'POST' })
      .then(res => {
        if (!res.ok) {
          console.warn('Backend injection returned error status, falling back to local simulator');
          runLocalSimulation(scenarioId);
        }
      })
      .catch(() => {
        console.warn('Backend unreachable, falling back to local simulator');
        runLocalSimulation(scenarioId);
      });
    return;
  }

  runLocalSimulation(scenarioId);
}

function runLocalSimulation(scenarioId: string) {

  // Otherwise, use client-side deterministic simulator (Guaranteed demo safety!)
  console.log(`Running standalone deterministic simulation for: ${scenarioId}`);
  setSimulating(true, scenarioId);

  let eventsList = [];

  if (scenarioId === 'db_oom') {
    eventsList = dbOomMockData.events;
  } else if (scenarioId === 'bad_config') {
    // Generated scenario for bad config
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

  // End simulation marker
  const maxDelay = Math.max(...eventsList.map(e => e.delay), 0);
  const endTimeout = setTimeout(() => {
    setSimulating(false, scenarioId);
  }, maxDelay + 500);
  activeTimeouts.push(endTimeout);
}

export function executeFullHealFlow() {
  clearActiveSimulation();
  
  // Sequential healing animation (Topological Order)
  const healSteps = [
    { delay: 400, type: 'agent_step', payload: { agent: 'execute', text: 'Executing Step 1: Patching postgres memory limit (64Mi -> 256Mi)...', status: 'running' } },
    { delay: 800, type: 'playbook_step', payload: { order: 1, status: 'done' } },
    { delay: 1100, type: 'service_update', payload: { id: 'postgres', status: 'recovering', metrics: { mem_mb: 52, mem_limit_mb: 256, cpu_pct: 18, restarts: 1 } } },
    
    { delay: 1400, type: 'agent_step', payload: { agent: 'verify', text: 'Step 2: Awaiting postgres readiness probe (port 5432)...', status: 'running' } },
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
            { "type": "k8s_event", "source": "postgres-0", "text": "Reason: OOMKilled, Exit Code: 137", "verified": true },
            { "type": "log", "source": "postgres-0", "line": 42, "text": "FATAL: out of memory", "verified": true },
            { "type": "metric", "source": "postgres-0", "text": "memory peaked at 63.8Mi of 64Mi limit", "verified": true }
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
    { delay: 1500, type: 'agent_step', payload: { agent: 'plan', text: 'Autoscaling recommendation: Scale auth-service replicas from 1 to 3', status: 'done' } }
  ];
}

function getSlowLeakMockEvents() {
  return [
    { delay: 300, type: 'agent_step', payload: { agent: 'triage', text: 'Predictive Analyzer: Monitoring memory gradient across nodes...', status: 'running' } },
    { delay: 800, type: 'metric_point', payload: { service: 'postgres', mem_mb: 45, mem_limit_mb: 64, cpu_pct: 14 } },
    { delay: 1400, type: 'metric_point', payload: { service: 'postgres', mem_mb: 52, mem_limit_mb: 64, cpu_pct: 16 } },
    { delay: 2000, type: 'metric_point', payload: { service: 'postgres', mem_mb: 58, mem_limit_mb: 64, cpu_pct: 18 } },
    {
      delay: 2400,
      type: 'prediction',
      payload: {
        service: 'postgres',
        seconds: 142,
        trend: '+2.4MB / min',
        message: 'PostgreSQL memory limit exhaustion predicted in 2m 22s'
      }
    },
    { delay: 2600, type: 'agent_step', payload: { agent: 'plan', text: 'PREDICTIVE SHIELD: Generated pre-emptive memory patch before crash occurs.', status: 'done' } }
  ];
}

export function triggerBackendReset() {
  fetch('http://localhost:8000/api/reset', { method: 'POST' }).catch(() => {});
}
