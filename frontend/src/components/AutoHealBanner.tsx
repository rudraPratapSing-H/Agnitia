// frontend/src/components/AutoHealBanner.tsx - Autonomous predictive-heal status banner
import React from 'react';
import { Loader2, CheckCircle2, AlertTriangle, ShieldOff } from 'lucide-react';

interface AutoHeal {
  id: string;
  service: string;
  action: string;
  params: Record<string, any>;
  phase: 'applied' | 'verified' | 'rolled_back';
  probability: number;
  reason?: string;
}

interface Blocked {
  service: string;
  probability: number;
  reasons: string[];
}

interface AutoHealBannerProps {
  autoHeal: AutoHeal | null;
  blocked: Blocked | null;
}

function describeAction(action: string, params: Record<string, any>): string {
  if (action === 'patch_memory_limit') return `memory ${params.from_mb}Mi → ${params.to_mb}Mi`;
  if (action === 'patch_cpu_limit') return `CPU limit ${params.from_m}m → ${params.to_m}m`;
  if (action === 'scale_replicas') return `replicas ${params.from} → ${params.to}`;
  return action;
}

export default function AutoHealBanner({ autoHeal, blocked }: AutoHealBannerProps) {
  if (autoHeal) {
    const detail = describeAction(autoHeal.action, autoHeal.params);

    if (autoHeal.phase === 'applied') {
      return (
        <div className="bg-copper-500/10 border border-copper-500/35 rounded-xl p-3 px-4 font-mono text-xs text-copper-200 animate-fadeIn flex items-center gap-3">
          <Loader2 size={16} className="animate-spin text-copper-400 shrink-0" />
          <span className="font-semibold">
            Auto-healing <span className="font-bold">{autoHeal.service}</span>: {detail} (predicted p = {autoHeal.probability.toFixed(2)})
          </span>
        </div>
      );
    }

    if (autoHeal.phase === 'verified') {
      return (
        <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-3 px-4 font-mono text-xs text-emerald-200 animate-fadeIn flex items-center gap-3">
          <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
          <span className="font-semibold">
            Healthy. Pre-emptively mitigated on <span className="font-bold">{autoHeal.service}</span> ({detail}) — root cause remains, flagged for follow-up.
          </span>
        </div>
      );
    }

    return (
      <div className="bg-rose-500/10 border border-rose-500/35 rounded-xl p-3 px-4 font-mono text-xs text-rose-200 animate-fadeIn flex items-center gap-3">
        <AlertTriangle size={16} className="text-rose-400 shrink-0" />
        <span className="font-semibold">
          Auto-heal on <span className="font-bold">{autoHeal.service}</span> did not verify{autoHeal.reason ? `: ${autoHeal.reason}` : ''}. A human has been alerted.
        </span>
      </div>
    );
  }

  if (blocked) {
    return (
      <div className="bg-ink-850 border border-ink-600 rounded-xl p-3 px-4 font-mono text-xs text-ink-300 animate-fadeIn flex items-center gap-3">
        <ShieldOff size={16} className="text-ink-400 shrink-0" />
        <span className="font-semibold">
          Policy blocked an automatic fix on <span className="font-bold text-ink-100">{blocked.service}</span>: {blocked.reasons.join('; ')}
        </span>
      </div>
    );
  }

  return null;
}
