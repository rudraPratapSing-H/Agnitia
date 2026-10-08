// D:\CoffeeOverflow\Agnitia\frontend\src\components\ChaosPanel.tsx - Chaos Triggers + Autonomy Slider
import React from 'react';
import { RotateCcw, Flame, AlertOctagon, Cpu, TrendingUp, Sliders, Shield } from 'lucide-react';
import { playScenario } from '../ws';
import { resetStore, setAutonomyLevel } from '../store';
import { playClickTone } from '../lib/sounds';

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
  autonomyLevel?: number;
}

export default function ChaosPanel({
  activeScenario,
  isSimulating,
  wsConnected,
  autonomyLevel = 2
}: ChaosPanelProps) {
  const handleTrigger = (scenarioId: string) => {
    playClickTone();
    playScenario(scenarioId);
  };

  const handleReset = () => {
    playClickTone();
    resetStore();
  };

  const handleAutonomyChange = (lvl: number) => {
    playClickTone();
    setAutonomyLevel(lvl);
  };

  return (
    <div className="bg-white border border-stone-200 rounded-xl p-3 shadow-xs flex flex-wrap items-center justify-between gap-3 font-mono">
      {/* Left: Section Title */}
      <div className="flex items-center gap-2.5">
        <div className="p-1.5 rounded-lg bg-stone-100 text-stone-700 border border-stone-200">
          <Flame size={15} />
        </div>
        <div>
          <span className="text-[11px] font-extrabold text-stone-900 tracking-wider uppercase block">
            CHAOS ORCHESTRATION ENGINE
          </span>
          <span className="text-[9px] text-stone-400 font-sans block">
            Fault injection vectors & autonomous reliability policies
          </span>
        </div>
      </div>

      {/* Middle: Scenario Trigger Buttons */}
      <div className="flex items-center gap-2 flex-wrap">
        {SCENARIOS.map((sc) => {
          const Icon = sc.icon;
          const isActive = activeScenario === sc.id;

          return (
            <button
              key={sc.id}
              onClick={() => handleTrigger(sc.id)}
              disabled={isSimulating && !isActive}
              className={`p-2 rounded-lg border text-left transition-all ${sc.color} ${
                isActive
                  ? 'bg-rose-50 border-rose-400 ring-2 ring-rose-300'
                  : 'bg-white border-stone-200 hover:shadow-xs'
              } disabled:opacity-50`}
            >
              <div className="flex items-center gap-1.5">
                <Icon size={13} className={isActive ? 'animate-bounce' : ''} />
                <span className="text-[11px] font-bold text-stone-800">{sc.title}</span>
                <span className="text-[8px] px-1 rounded bg-stone-100 text-stone-600 font-bold border border-stone-200">
                  {sc.badge}
                </span>
              </div>
              <span className="text-[9px] text-stone-400 block font-sans truncate max-w-[140px]">
                {sc.desc}
              </span>
            </button>
          );
        })}
      </div>

      {/* Right: Autonomy Selector & Reset Button */}
      <div className="flex items-center gap-3">
        {/* Phase 3 Autonomy Selector */}
        <div className="bg-stone-50 border border-stone-200 rounded-lg p-1 flex items-center gap-1">
          <span className="text-[9px] font-bold text-stone-500 uppercase px-1.5 flex items-center gap-1">
            <Sliders size={11} />
            AUTONOMY:
          </span>
          {[
            { lvl: 1, label: 'L1 STRICT', tip: 'Human approves all steps' },
            { lvl: 2, label: 'L2 BALANCED', tip: 'Default: Approvals on high risk' },
            { lvl: 3, label: 'L3 FULL', tip: 'Self-healing auto-pilot' }
          ].map((item) => (
            <button
              key={item.lvl}
              onClick={() => handleAutonomyChange(item.lvl)}
              title={item.tip}
              className={`px-2 py-0.5 rounded text-[9px] font-bold transition-colors ${
                autonomyLevel === item.lvl
                  ? 'bg-stone-900 text-white shadow-2xs'
                  : 'text-stone-600 hover:bg-stone-200/70'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {/* Reset Button */}
        <button
          onClick={handleReset}
          className="bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-2 rounded-lg text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 shadow-xs transition-all active:scale-[0.98]"
        >
          <RotateCcw size={13} />
          <span>RESET TO GREEN</span>
        </button>
      </div>
    </div>
  );
}
