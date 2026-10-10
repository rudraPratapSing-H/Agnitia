// frontend/src/components/PredictionGauge.tsx - Per-node failure probability gauge
import React from 'react';

interface PredictionGaugeProps {
  probability: number;
  threshold: number;
  secondsToLimit: number | null;
}

export default function PredictionGauge({ probability, threshold, secondsToLimit }: PredictionGaugeProps) {
  if (probability < 0.2) return null;

  const pct = Math.round(Math.min(1, probability) * 100);
  const thresholdPct = Math.round(Math.min(1, threshold) * 100);

  const barColor =
    probability >= threshold ? 'bg-rose-500' : probability >= 0.5 ? 'bg-amber-500' : 'bg-emerald-500';
  const textColor =
    probability >= threshold ? 'text-rose-300' : probability >= 0.5 ? 'text-amber-300' : 'text-emerald-300';

  return (
    <div className="mt-1.5 pt-1.5 border-t border-ink-700/80 font-mono">
      <div className="flex items-center justify-between text-[8.5px] mb-0.5">
        <span className="text-ink-500 font-bold uppercase tracking-wider">Failure risk</span>
        <span className={`font-bold ${textColor}`}>
          p = {probability.toFixed(2)}
          {secondsToLimit !== null && <span className="text-ink-400 font-semibold"> · fails in ~{Math.round(secondsToLimit)}s</span>}
        </span>
      </div>
      <div className="relative h-1.5 w-full bg-ink-700 rounded-full overflow-hidden border border-ink-600">
        <div className={`h-full transition-all duration-300 ${barColor}`} style={{ width: `${pct}%` }} />
        <div
          className="absolute top-0 h-full w-px bg-ink-200/70"
          style={{ left: `${thresholdPct}%` }}
          title={`Auto-heal threshold: ${thresholdPct}%`}
        />
      </div>
    </div>
  );
}
