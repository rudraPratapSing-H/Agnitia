import React from 'react';
import { useIncidentTimer } from './useIncidentTimer';

export interface CostTickerProps {
  startedAt?: string | null;
  resolvedAt?: string | null;
  perMinute?: number;
  currency?: string;
}

export const CostTicker: React.FC<CostTickerProps> = ({
  startedAt,
  resolvedAt,
  // Configure per-minute downtime impact figure via VITE_COST_PER_MINUTE in .env
  perMinute = Number(import.meta.env.VITE_COST_PER_MINUTE),
  currency = '₹',
}) => {
  const { elapsedMs, status } = useIncidentTimer(startedAt, resolvedAt);

  // If perMinute is NaN or 0 or negative, display a dash instead of a calculated number
  const isCostValid = !isNaN(perMinute) && perMinute > 0;

  // Calculate accumulated financial cost (pro-rated by milliseconds)
  const currentCost = isCostValid ? Math.floor((elapsedMs / 60000) * perMinute) : 0;

  // Formatted with Indian digit grouping (e.g., ₹ 1,20,000)
  const formattedCost = isCostValid ? currentCost.toLocaleString('en-IN') : '-';

  return (
    <div className="flex flex-col items-center justify-center p-3 rounded-xl bg-stone-900 border border-stone-800 text-stone-100 font-mono shadow-sm select-none">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-stone-400 mb-0.5">
        Downtime Cost
      </div>

      {/* Financial cost display formatted in rupees */}
      <div
        className={`text-3xl md:text-4xl font-black tracking-tight tabular-nums transition-colors duration-200 ${
          status === 'idle'
            ? 'text-stone-600'
            : status === 'running'
            ? 'text-amber-400'
            : 'text-stone-300'
        }`}
      >
        {isCostValid ? (
          <span>
            <span className="text-2xl mr-1 text-stone-400 font-bold">{currency}</span>
            {formattedCost}
          </span>
        ) : (
          <span className="text-stone-600">-</span>
        )}
      </div>

      {/* Subtitle / rate tag */}
      <div className="text-xs font-medium mt-1 text-stone-500">
        {status === 'idle' && (
          <span>
            Rate: {isCostValid ? `${currency}${perMinute.toLocaleString('en-IN')}/min` : 'Unconfigured'}
          </span>
        )}

        {status === 'running' && (
          <span className="text-amber-400/90 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
            Accruing live
          </span>
        )}

        {status === 'resolved' && (
          <span className="text-stone-400 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            Total cost frozen
          </span>
        )}
      </div>
    </div>
  );
};

export default CostTicker;
