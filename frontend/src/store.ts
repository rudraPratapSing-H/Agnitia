// frontend/src/store.ts - Central State Store with Architecture Preset Switching
import { useState, useEffect } from 'react';
import { PresetId, PRESETS } from './presets';

export const INITIAL_SERVICES = PRESETS['k8s-core'].initialServices;

let globalState = {
  activePresetId: 'k8s-core' as PresetId,
  services: JSON.parse(JSON.stringify(PRESETS['k8s-core'].initialServices)) as Record<string, any>,
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
  listeners.forEach((listener) => listener(globalState));
}

export function getState() {
  return globalState;
}

export function useAgnitiaStore() {
  const [state, setState] = useState(globalState);

  useEffect(() => {
    listeners.add(setState);
    return () => {
      listeners.delete(setState);
    };
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
        services: targetService
          ? {
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
            }
          : globalState.services
      };
      break;
    }

    case 'incident_update': {
      globalState = {
        ...globalState,
        incident: payload
      };
      break;
    }

    case 'agent_step': {
      globalState = {
        ...globalState,
        agentSteps: [
          ...globalState.agentSteps,
          { ...payload, id: Date.now() + Math.random(), ts: payload.ts || new Date().toISOString() }
        ]
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
      console.warn('Unhandled event type:', type, payload);
  }

  emitChange();
}

export function setActivePreset(presetId: PresetId) {
  if (globalState.activePresetId === presetId) return;
  globalState.activePresetId = presetId;
  resetStore(presetId);
}

export function resetStore(presetIdOverride?: PresetId) {
  const presetId = presetIdOverride || globalState.activePresetId || 'k8s-core';
  const targetPreset = PRESETS[presetId] || PRESETS['k8s-core'];

  globalState = {
    activePresetId: presetId,
    services: JSON.parse(JSON.stringify(targetPreset.initialServices)),
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
