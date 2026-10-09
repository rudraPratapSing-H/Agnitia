// D:\CoffeeOverflow\Agnitia\frontend\src\components\extras\CostTicker.tsx
import React, { useState, useEffect } from 'react';
import { DollarSign, ShieldCheck } from 'lucide-react';

interface CostTickerProps {
  isActive: boolean;
  resolvedAt?: string | null;
  costPerMinute?: number; // default $4200/min ($70/s)
}

export default function CostTicker({
  isActive,
  resolvedAt,
  costPerMinute = 4200
}: CostTickerProps) {
  const [cost, setCost] = useState(0);

  useEffect(() => {
    if (!isActive && !resolvedAt) {
      setCost(0);
      return;
    }

    if (resolvedAt) {
      // Freezes at $2,660 (38s * $70/s)
      setCost(2660);
      return;
    }

    const ratePerSec = costPerMinute / 60;
    const startMs = Date.now();

    const interval = setInterval(() => {
      const elapsedSec = (Date.now() - startMs) / 1000;
      setCost(Math.round(elapsedSec * ratePerSec));
    }, 500);

    return () => clearInterval(interval);
  }, [isActive, resolvedAt, costPerMinute]);

  const formatted = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0
  }).format(cost);

  return (
    <div
      className={`px-2.5 py-1 rounded-lg border flex items-center gap-1.5 font-mono text-xs transition-colors ${
        resolvedAt
          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
          : isActive
          ? 'bg-rose-500/10 border-rose-500/35 text-rose-300'
          : 'bg-ink-850 border-ink-700 text-ink-400'
      }`}
    >
      {resolvedAt ? (
        <ShieldCheck size={13} className="text-emerald-400" />
      ) : (
        <DollarSign size={13} className={isActive ? 'text-rose-400' : 'text-ink-500'} />
      )}

      <span className="text-[10px] text-ink-500 uppercase">
        {resolvedAt ? 'SAVED:' : 'IMPACT:'}
      </span>
      <span className="font-bold tracking-tight">
        {resolvedAt ? `${formatted} CAPPED` : `${formatted}`}
      </span>
    </div>
  );
}
