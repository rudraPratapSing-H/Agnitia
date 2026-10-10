// frontend/src/components/KillSwitch.tsx - Instant halt for the predictive auto-heal layer
import React from 'react';
import { ShieldOff, ShieldCheck } from 'lucide-react';

interface KillSwitchProps {
  active: boolean;
  onToggle: () => void;
}

export default function KillSwitch({ active, onToggle }: KillSwitchProps) {
  return (
    <button
      onClick={onToggle}
      className={`p-1.5 rounded-lg border transition-colors flex items-center gap-1 ${
        active
          ? 'bg-rose-500/12 text-rose-300 border-rose-500/35'
          : 'bg-ink-800 text-ink-400 border-ink-600'
      }`}
      title={active ? 'Predictive auto-heal is OFF — click to re-enable' : 'Predictive auto-heal is ON — click to kill'}
    >
      {active ? <ShieldOff size={14} /> : <ShieldCheck size={14} />}
      <span className="text-[11px] font-semibold">{active ? 'AUTO-HEAL OFF' : 'AUTO-HEAL ON'}</span>
    </button>
  );
}
