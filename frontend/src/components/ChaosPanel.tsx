// frontend/src/components/ChaosPanel.tsx - SRE Chaos Engine + Hotkey Badges
import React from 'react';
import { RotateCcw, Flame, AlertOctagon, Cpu, TrendingUp, Sliders } from 'lucide-react';
import { playScenario, resetAll, setAutonomyBackend } from '../ws';
import { setAutonomyLevel, useAgnitiaStore } from '../store';
import { playClickTone } from '../lib/sounds';

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
  const { activePresetId } = useAgnitiaStore();
  const isAmazon = activePresetId === 'amazon-scale';

  const scenarios = [
    {
      id: 'db_oom',
      key: '1',
      title: 'DB Out of Memory',
      badge: isAmazon ? '84 ALERTS' : '56 ALERTS',
      desc: isAmazon ? 'Aurora OOMKilled 137' : 'OOMKilled exitCode 137',
      icon: Flame,
      color: 'hover:border-rose-300 hover:bg-rose-50 text-rose-700'
    },
    {
      id: 'bad_config',
      key: '2',
      title: 'Bad Config Rollout',
      badge: 'CRASH LOOP',
      desc: isAmazon ? 'Missing Stripe & Pay keys' : 'Missing STRIPE_API_SECRET',
      icon: AlertOctagon,
      color: 'hover:border-amber-300 hover:bg-amber-50 text-amber-700'
    },
    {
      id: 'cpu_spike',
      key: '3',
      title: 'CPU Saturation',
      badge: 'AUTOSCALE',
      desc: isAmazon ? 'Cognito 100% throttle' : '100% Throttle spike',
      icon: Cpu,
      color: 'hover:border-purple-300 hover:bg-purple-50 text-purple-700'
    },
    {
      id: 'slow_leak',
      key: '4',
      title: 'Slow Memory Leak',
      badge: 'PREDICTIVE',
      desc: isAmazon ? 'Exhaustion in 2m 58s' : 'Exhaustion in 2m 22s',
      icon: TrendingUp,
      color: 'hover:border-sky-300 hover:bg-sky-50 text-sky-700'
    }
  ];

  const handleTrigger = (scenarioId: string) => {
    playClickTone();
    playScenario(scenarioId);
  };

  const handleReset = () => {
    playClickTone();
    resetAll();
  };

  const handleAutonomyChange = (lvl: number) => {
    playClickTone();
    setAutonomyLevel(lvl);
    setAutonomyBackend(lvl);
  };

  return (
    <div className="bg-white border border-stone-200 rounded-xl p-2.5 shadow-2xs flex flex-wrap items-center justify-between gap-3 font-mono">
      {/* Left: Section Title & Hotkey hint */}
      <div className="flex items-center gap-2.5">
        <div className="p-1.5 rounded-lg bg-stone-100 text-stone-700 border border-stone-200">
          <Flame size={15} />
        </div>
        <div>
          <span className="text-[11px] font-black text-stone-900 tracking-wider uppercase block">
            CHAOS INJECTION VECTORS
          </span>
          <span className="text-[9px] text-stone-500 font-sans block">
            Press <kbd className="px-1 py-0.2 bg-stone-100 border border-stone-300 rounded text-stone-700 font-mono font-bold">1</kbd>–<kbd className="px-1 py-0.2 bg-stone-100 border border-stone-300 rounded text-stone-700 font-mono font-bold">4</kbd> to inject • <kbd className="px-1 py-0.2 bg-stone-100 border border-stone-300 rounded text-stone-700 font-mono font-bold">R</kbd> to reset
          </span>
        </div>
      </div>

      {/* Middle: Scenario Trigger Buttons */}
      <div className="flex items-center gap-2 flex-wrap">
        {scenarios.map((sc) => {
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
                <kbd className="px-1 py-0.2 text-[9px] font-bold font-mono bg-stone-100 border border-stone-300 rounded text-stone-700 shadow-2xs">
                  {sc.key}
                </kbd>
                <Icon size={13} className={isActive ? 'animate-bounce' : ''} />
                <span className="text-[11px] font-bold text-stone-800">{sc.title}</span>
                <span className="text-[8px] px-1 rounded bg-stone-100 text-stone-600 font-bold border border-stone-200">
                  {sc.badge}
                </span>
              </div>
              <span className="text-[9px] text-stone-500 block font-sans truncate max-w-[145px] ml-5">
                {sc.desc}
              </span>
            </button>
          );
        })}
      </div>

      {/* Right: Autonomy Selector & Reset Button */}
      <div className="flex items-center gap-2.5">
        {/* Autonomy Selector */}
        <div className="bg-stone-50 border border-stone-200 rounded-lg p-1 flex items-center gap-1">
          <span className="text-[9px] font-bold text-stone-500 uppercase px-1.5 flex items-center gap-1">
            <Sliders size={11} />
            GUARD:
          </span>
          {[
            { lvl: 1, label: 'L1 MANUAL', tip: 'Operator approves all steps' },
            { lvl: 2, label: 'L2 GUARDED', tip: 'Default: Approvals on high risk' },
            { lvl: 3, label: 'L3 AUTO', tip: 'Self-healing auto-pilot' }
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
          className="bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-2 rounded-lg text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 shadow-2xs transition-all active:scale-[0.98]"
        >
          <kbd className="px-1 py-0.2 text-[9px] font-bold font-mono bg-emerald-800/80 border border-emerald-500 rounded text-emerald-100">
            R
          </kbd>
          <RotateCcw size={13} />
          <span>RESET</span>
        </button>
      </div>
    </div>
  );
}
