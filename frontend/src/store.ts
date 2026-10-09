// frontend/src/store.ts - Central State Store with Phase 3 Autonomy & What-If Mode
import { useState, useEffect } from 'react';

export const INITIAL_SERVICES = {
  postgres: {
    id: "postgres",
    label: "PostgreSQL",
    tier: "data",
    depends_on: [],
    status: "healthy",
    metrics: { mem_mb: 42, mem_limit_mb: 64, cpu_pct: 12, restarts: 0 }
  },
  redis: {
    id: "redis",
    label: "Redis Cache",
    tier: "data",
    depends_on: [],
    status: "healthy",
    metrics: { mem_mb: 18, mem_limit_mb: 128, cpu_pct: 4, restarts: 0 }
  },
  "auth-service": {
    id: "auth-service",
    label: "Auth Service",
    tier: "backend",
    depends_on: ["postgres", "redis"],
    status: "healthy",
    metrics: { mem_mb: 38, mem_limit_mb: 128, cpu_pct: 8, restarts: 0 }
  },
  "payment-service": {
    id: "payment-service",
    label: "Payment Service",
    tier: "backend",
    depends_on: ["postgres"],
    status: "healthy",
    metrics: { mem_mb: 64, mem_limit_mb: 256, cpu_pct: 11, restarts: 0 }
  },
  "api-gateway": {
    id: "api-gateway",
    label: "API Gateway",
    tier: "edge",
    depends_on: ["auth-service", "payment-service"],
    status: "healthy",
    metrics: { mem_mb: 92, mem_limit_mb: 256, cpu_pct: 21, restarts: 0 }
  },
  "web-ui": {
    id: "web-ui",
    label: "Web Storefront",
    tier: "frontend",
    depends_on: ["api-gateway"],
    status: "healthy",
    metrics: { mem_mb: 55, mem_limit_mb: 128, cpu_pct: 15, restarts: 0 }
  }
};

let globalState = {
  services: { ...INITIAL_SERVICES },
  alerts: [] as any[],
  incident: null as any,
  agentSteps: [] as any[],
  stepStatus: {} as Record<number, 'pending' | 'running' | 'done' | 'failed'>,
  metrics: {} as Record<string, any[]>,
  prediction: null as any,
  activeScenario: null as string | null,
  isSimulating: false,
  wsConnected: false,
  autonomyLevel: 2, // Level 1: Strict, Level 2: Balanced, Level 3: Autonomous
  whatIfNode: null as string | null,
  soundMuted: false
};

const listeners = new Set<(state: any) => void>();

function emitChange() {
  listeners.forEach(listener => listener(globalState));
}

export function getState() {
  return globalState;
}

export function useAgnitiaStore() {
  const [state, setState] = useState(globalState);

  useEffect(() => {
    listeners.add(setState);
    return () => { listeners.delete(setState); };
  }, []);

  return state;
}

// Event Reducer: The ONLY place events change state (as per CONTRACT.md)
export function applyWsEvent(event: any) {
  if (!event || !event.type) return;

  const { type, payload } = event;

  switch (type) {
    case 'service_update': {
      if (globalState.services[payload.id]) {
        globalState = {
          ...globalState,
          services: {
            ...globalState.services,
            [payload.id]: {
              ...globalState.services[payload.id],
              ...payload,
              metrics: {
                ...globalState.services[payload.id].metrics,
                ...(payload.metrics || {})
              }
            }
          }
        };
      }
      break;
    }

    case 'alert': {
      globalState = {
        ...globalState,
        alerts: [payload, ...globalState.alerts]
      };
      break;
    }

    case 'metric_point': {
      const currentPoints = globalState.metrics[payload.service] || [];
      const updatedPoints = [...currentPoints.slice(-30), payload];
      const targetService = globalState.services[payload.service];

      globalState = {
        ...globalState,
        metrics: {
          ...globalState.metrics,
          [payload.service]: updatedPoints
        },
        services: targetService ? {
          ...globalState.services,
          [payload.service]: {
            ...targetService,
            metrics: {
              ...targetService.metrics,
              mem_mb: payload.mem_mb ?? targetService.metrics.mem_mb,
              mem_limit_mb: payload.mem_limit_mb ?? targetService.metrics.mem_limit_mb,
              cpu_pct: payload.cpu_pct ?? targetService.metrics.cpu_pct
            }
          }
        } : globalState.services
      };
      break;
    }

    case 'incident_update': {
      // When the backend delivers a terminal status, the scenario playback is
      // complete — re-enable the Inject buttons (mirrors mock-replay end-timeout).
      const terminalStatuses = ['awaiting_approval', 'resolved', 'failed'];
      const isTerminal = terminalStatuses.includes(payload?.status);
      globalState = {
        ...globalState,
        incident: payload,
        isSimulating: isTerminal ? false : globalState.isSimulating,
        activeScenario: isTerminal ? payload?.scenario ?? globalState.activeScenario : globalState.activeScenario,
      };
      break;
    }

    case 'agent_step': {
      globalState = {
        ...globalState,
        agentSteps: [...globalState.agentSteps, { ...payload, id: Date.now() + Math.random(), ts: payload.ts || new Date().toISOString() }]
      };
      break;
    }

    case 'playbook_step': {
      globalState = {
        ...globalState,
        stepStatus: {
          ...globalState.stepStatus,
          [payload.order]: payload.status
        }
      };
      break;
    }

    case 'prediction': {
      globalState = {
        ...globalState,
        prediction: payload
      };
      break;
    }

    case 'reset': {
      resetStore();
      return;
    }

    default:
      console.warn("Unhandled event type:", type, payload);
  }

  emitChange();
}

export function resetStore() {
  globalState = {
    services: JSON.parse(JSON.stringify(INITIAL_SERVICES)),
    alerts: [],
    incident: null,
    agentSteps: [],
    stepStatus: {},
    metrics: {},
    prediction: null,
    activeScenario: null,
    isSimulating: false,
    wsConnected: globalState.wsConnected,
    autonomyLevel: globalState.autonomyLevel,
    whatIfNode: null,
    soundMuted: globalState.soundMuted
  };
  emitChange();
}

export function setWsConnected(status: boolean) {
  globalState = { ...globalState, wsConnected: status };
  emitChange();
}

export function setSimulating(status: boolean, scenarioName: string | null = null) {
  globalState = {
    ...globalState,
    isSimulating: status,
    activeScenario: scenarioName
  };
  emitChange();
}

export function setAutonomyLevel(level: number) {
  globalState = { ...globalState, autonomyLevel: level };
  emitChange();
}

export function setWhatIfNode(nodeId: string | null) {
  globalState = { ...globalState, whatIfNode: nodeId };
  emitChange();
}

export function setSoundMuted(muted: boolean) {
  globalState = { ...globalState, soundMuted: muted };
  emitChange();
}
