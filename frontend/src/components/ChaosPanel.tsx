// frontend/src/components/ChaosPanel.tsx
import React from 'react';
import { RotateCcw, Flame, AlertOctagon, Cpu, TrendingUp, Activity } from 'lucide-react';
import { playScenario, resetBackend } from '../ws';

const SCENARIOS = [
  {
    id: 'db_oom',
    title: 'DB Out of Memory',
    badge: '56 ALERTS',
    desc: 'OOMKilled ExitCode 137',
    icon: Flame,
    color: 'hover:border-rose-300 hover:bg-rose-50 text-rose-700'
  },
  {
    id: 'bad_config',
    title: 'Bad Config Rollout',
    badge: 'CRASH LOOP',
    desc: 'Missing STRIPE_API_SECRET',
    icon: AlertOctagon,
    color: 'hover:border-amber-300 hover:bg-amber-50 text-amber-700'
  },
  {
    id: 'cpu_spike',
    title: 'CPU Saturation',
    badge: 'AUTOSCALE',
    desc: '100% Throttle spike',
    icon: Cpu,
    color: 'hover:border-purple-300 hover:bg-purple-50 text-purple-700'
  },
  {
    id: 'slow_leak',
    title: 'Slow Memory Leak',
    badge: 'PREDICTIVE',
    desc: 'Exhaustion in 2m 22s',
    icon: TrendingUp,
    color: 'hover:border-sky-300 hover:bg-sky-50 text-sky-700'
  }
];

interface ChaosPanelProps {
  activeScenario: string | null;
  isSimulating: boolean;
  wsConnected: boolean;
}

export default function ChaosPanel({ activeScenario, isSimulating, wsConnected }: ChaosPanelProps) {
  const handleTrigger = (scenarioId: string) => {
    playScenario(scenarioId);
  };

  const handleReset = () => {
    // resetBackend() calls POST /api/reset when live, then resets local store.
    // This clears the adapter's _scenario guard so Inject works again.
    void resetBackend();
  };

  return (
    <div className="bg-white border border-stone-200 rounded-xl p-3 shadow-xs flex flex-wrap items-center justify-between gap-3 font-mono">
      <div className="flex items-center gap-2.5">
        <div className="p-1.5 rounded-lg bg-stone-100 text-stone-700 border border-stone-200">
          <Activity size={15} />
        </div>
        <div>
          <div className="text-xs font-bold text-stone-800 tracking-wider uppercase">
            Chaos Injection
          </div>
          <div className="text-[10px] text-stone-500 flex items-center gap-1.5">
            <span>Demo Fault Scenarios</span>
            <span className="text-stone-300">·</span>
            <span className={wsConnected ? 'text-emerald-700 font-semibold' : 'text-stone-600'}>
              {wsConnected ? 'Live Cluster' : 'Deterministic Mode'}
            </span>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {SCENARIOS.map((sc) => {
          const Icon = sc.icon;
          const isActive = activeScenario === sc.id;

          return (
            <button
              key={sc.id}
              onClick={() => handleTrigger(sc.id)}
              disabled={isSimulating}
              className={`px-3 py-1.5 rounded-lg border text-left transition-all duration-150 flex items-center gap-2 text-xs font-medium cursor-pointer active:scale-98 ${
                isActive
                  ? 'border-rose-500 bg-rose-50 text-rose-900 shadow-xs'
                  : `border-stone-200 bg-white text-stone-700 ${sc.color}`
              } ${isSimulating ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <Icon size={14} className="shrink-0" />
              <div>
                <div className="font-bold flex items-center gap-1.5 leading-none text-stone-900">
                  <span>{sc.title}</span>
                  <span className="text-[8px] px-1 py-0.2 rounded bg-stone-100 border border-stone-200 text-stone-600 font-normal">
                    {sc.badge}
                  </span>
                </div>
                <div className="text-[9px] text-stone-500 mt-0.5">
                  {sc.desc}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <div>
        <button
          onClick={handleReset}
          className="px-3.5 py-1.5 rounded-lg bg-stone-100 hover:bg-stone-200 border border-stone-200 text-stone-800 font-bold text-xs uppercase tracking-wider transition-all flex items-center gap-1.5 shadow-2xs active:scale-98 cursor-pointer"
          title="Return cluster to nominal healthy state in 2 seconds"
        >
          <RotateCcw size={13} className="text-emerald-700" />
          <span>RESET TO GREEN</span>
        </button>
      </div>
    </div>
  );
}
