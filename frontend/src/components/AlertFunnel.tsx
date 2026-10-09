// D:\CoffeeOverflow\Agnitia\frontend\src\components\AlertFunnel.tsx
import React, { useState } from 'react';
import { ShieldAlert, Zap, ChevronDown, ChevronUp, Bell, CheckCircle } from 'lucide-react';
import { Alert, Incident } from '../types';

interface AlertFunnelProps {
  alerts: Alert[];
  incident: Incident | null;
}

export default function AlertFunnel({ alerts, incident }: AlertFunnelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const alertCount = alerts.length;
  const isCollapsed = Boolean(incident);

  const noiseReductionPct = alertCount > 1
    ? Math.round(((alertCount - 1) / alertCount) * 100)
    : 0;

  return (
    <div className="bg-ink-900 rounded-xl border border-ink-700 p-3.5 transition-all shrink-0 min-h-[90px]">
      <div className="flex items-center justify-between mb-2.5">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-rose-500/12 text-rose-400 border border-rose-500/25">
            <ShieldAlert size={15} />
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-ink-50 font-mono flex items-center gap-1.5">
              Alert Stream
              {alertCount > 0 && (
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping" />
              )}
            </h3>
            <p className="text-[10px] text-ink-500 font-mono">
              Topological Correlation
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="text-right font-mono">
            <div className="text-sm font-bold text-rose-400 leading-none">
              {alertCount}
            </div>
            <div className="text-[8px] text-ink-500 uppercase">RAW ALERTS</div>
          </div>

          {isCollapsed && (
            <div className="bg-emerald-500/12 border border-emerald-500/30 px-2 py-0.5 rounded text-right font-mono">
              <div className="text-xs font-bold text-emerald-300 leading-none flex items-center gap-1">
                <CheckCircle size={10} className="text-emerald-400" />
                {noiseReductionPct}%
              </div>
              <div className="text-[8px] text-emerald-400 uppercase">NOISE CUT</div>
            </div>
          )}
        </div>
      </div>

      {isCollapsed ? (
        <div className="mb-2.5 bg-emerald-500/8 border border-emerald-500/25 rounded-lg p-2.5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded-full bg-emerald-500 text-ink-950 flex items-center justify-center font-bold text-[10px]">
              1
            </div>
            <div>
              <div className="text-xs font-bold text-emerald-200 font-mono">
                {alertCount} Alerts Correlated to 1 Root Incident
              </div>
              <div className="text-[10px] text-ink-400 font-mono">
                {incident?.id} · Root Origin: <span className="font-semibold text-rose-300">{incident?.root_service}</span>
              </div>
            </div>
          </div>

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-[10px] font-mono text-ink-300 hover:text-ink-50 bg-ink-850 hover:bg-ink-700 border border-ink-600 px-2 py-1 rounded flex items-center gap-1 transition-colors"
          >
            {isExpanded ? 'Hide' : 'View'} ({alertCount})
            {isExpanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
          </button>
        </div>
      ) : alertCount > 0 ? (
        <div className="mb-2.5 bg-amber-500/10 border border-amber-500/30 rounded-lg p-2 flex items-center justify-between text-xs font-mono text-amber-200">
          <span className="flex items-center gap-1.5">
            <Zap size={12} className="text-amber-400 animate-bounce" />
            Ingesting alerts... Clustering active.
          </span>
          <span className="font-bold">{alertCount} / 56</span>
        </div>
      ) : (
        <div className="mb-1 py-2 text-center rounded-lg border border-dashed border-ink-700 text-[11px] text-ink-500 font-mono">
          Cluster telemetry calm. 0 active alerts.
        </div>
      )}

      {(isExpanded || (!isCollapsed && alertCount > 0)) && (
        <div className="max-h-40 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
          {alerts.map((alt, idx) => (
            <div
              key={alt.id || idx}
              className="p-1.5 rounded bg-ink-850 border border-ink-700 text-[11px] font-mono hover:border-ink-500 transition-colors"
            >
              <div className="flex items-center justify-between gap-1 mb-0.5">
                <span className="font-semibold text-rose-300 flex items-center gap-1">
                  <Bell size={10} />
                  {alt.service}
                </span>
                <span className="text-[9px] text-ink-500">{alt.ts || '03:14:08'}</span>
              </div>
              <p className="text-ink-300 text-[10px] leading-tight truncate">
                {alt.message}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
