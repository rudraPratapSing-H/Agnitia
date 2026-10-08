// frontend/src/components/ChaosPanel.jsx - Chaos Engineering Trigger Bar & Instant Reset
import React from 'react';
import { Play, RotateCcw, Flame, AlertOctagon, Cpu, TrendingUp, Radio } from 'lucide-react';
import { playScenario } from '../ws';
import { resetStore } from '../store';

const SCENARIOS = [
  {
    id: 'db_oom',
    title: 'DB Out of Memory',
    badge: '56 ALERTS',
    desc: 'OOMKilled ExitCode 137',
    icon: Flame,
    color: 'hover:border-red-500 hover:bg-red-950/40 text-red-400'
  },
  {
    id: 'bad_config',
    title: 'Bad Config Rollout',
    badge: 'CRASH LOOP',
    desc: 'Missing STRIPE_API_SECRET',
    icon: AlertOctagon,
    color: 'hover:border-amber-500 hover:bg-amber-950/40 text-amber-400'
  },
  {
    id: 'cpu_spike',
    title: 'CPU Saturation',
    badge: 'AUTOSCALE',
    desc: '100% Throttle spike',
    icon: Cpu,
    color: 'hover:border-purple-500 hover:bg-purple-950/40 text-purple-400'
  },
  {
    id: 'slow_leak',
    title: 'Slow Memory Leak',
    badge: 'PREDICTIVE',
    desc: 'Exhaustion warning in 2m',
    icon: TrendingUp,
    color: 'hover:border-cyan-500 hover:bg-cyan-950/40 text-cyan-400'
  }
];

export default function ChaosPanel({ activeScenario, isSimulating, wsConnected }) {
  const handleTrigger = (scenarioId) => {
    playScenario(scenarioId);
  };

  const handleReset = () => {
    resetStore();
  };

  return (
    <div className="bg-zinc-900/95 border border-zinc-800 rounded-xl p-3 backdrop-blur-md shadow-2xl flex flex-wrap items-center justify-between gap-3 font-mono">
      {/* Left: Section Label & Connection Indicator */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-indigo-950/80 text-indigo-400 border border-indigo-800">
            <Radio size={15} />
          </div>
          <div>
            <div className="text-xs font-bold text-zinc-200 tracking-wider uppercase">
              CHAOS INJECTOR
            </div>
            <div className="text-[10px] text-zinc-500 flex items-center gap-1.5">
              <span>DEMO TRIGGER PANEL</span>
              <span className="text-zinc-600">·</span>
              <span className={wsConnected ? 'text-emerald-400' : 'text-zinc-400'}>
                {wsConnected ? 'LIVE WS' : 'MOCK REPLAY (SAFE)'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Middle: Scenario Trigger Buttons */}
      <div className="flex flex-wrap items-center gap-2">
        {SCENARIOS.map((sc) => {
          const Icon = sc.icon;
          const isActive = activeScenario === sc.id;

          return (
            <button
              key={sc.id}
              onClick={() => handleTrigger(sc.id)}
              disabled={isSimulating}
              className={`px-3 py-1.5 rounded-lg border text-left transition-all duration-200 flex items-center gap-2 text-xs font-medium group active:scale-95 ${
                isActive
                  ? 'border-red-500 bg-red-950/70 text-red-300 shadow-[0_0_15px_rgba(239,68,68,0.4)]'
                  : `border-zinc-800 bg-zinc-950/70 text-zinc-300 ${sc.color}`
              } ${isSimulating ? 'opacity-60 cursor-not-allowed' : ''}`}
            >
              <Icon size={14} className="shrink-0" />
              <div>
                <div className="font-bold flex items-center gap-1.5 leading-none">
                  <span>{sc.title}</span>
                  <span className="text-[8px] px-1 py-0.2 rounded bg-zinc-900 border border-zinc-700 text-zinc-400 font-normal">
                    {sc.badge}
                  </span>
                </div>
                <div className="text-[9px] text-zinc-500 mt-0.5">
                  {sc.desc}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Right: Instant Reset Button */}
      <div>
        <button
          onClick={handleReset}
          className="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-200 font-bold text-xs uppercase tracking-wider transition-all flex items-center gap-1.5 shadow-md active:scale-95 hover:border-zinc-500"
          title="Return cluster to nominal healthy state in 2 seconds"
        >
          <RotateCcw size={14} className="text-emerald-400" />
          <span>RESET TO GREEN</span>
        </button>
      </div>
    </div>
  );
}
