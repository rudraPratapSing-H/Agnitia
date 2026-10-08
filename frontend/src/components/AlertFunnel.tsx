// frontend/src/components/AlertFunnel.jsx - Alert Storm Funnel & Noise Reduction Stream
import React, { useState } from 'react';
import { ShieldAlert, Zap, Filter, ChevronDown, ChevronUp, Bell, CheckCircle } from 'lucide-react';

export default function AlertFunnel({ alerts, incident }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const alertCount = alerts.length;
  const isCollapsed = Boolean(incident);

  // Noise reduction percentage: 56 alerts -> 1 incident = 98.2%
  const noiseReductionPct = alertCount > 1 
    ? Math.round(((alertCount - 1) / alertCount) * 100) 
    : 0;

  return (
    <div className="bg-zinc-900/90 rounded-xl border border-zinc-800 p-3.5 backdrop-blur-md shadow-xl transition-all duration-300">
      {/* Funnel Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-rose-950/80 text-rose-400 border border-rose-800">
            <ShieldAlert size={16} />
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono flex items-center gap-2">
              ALERT STORM FUNNEL
              {alertCount > 0 && (
                <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
              )}
            </h3>
            <p className="text-[10px] text-zinc-400 font-mono">
              Topological Correlation Pipeline
            </p>
          </div>
        </div>

        {/* Live Counters & Stats */}
        <div className="flex items-center gap-2">
          <div className="text-right font-mono">
            <div className="text-sm font-extrabold text-rose-400 leading-none">
              {alertCount}
            </div>
            <div className="text-[9px] text-zinc-500 uppercase">RAW ALERTS</div>
          </div>

          {isCollapsed && (
            <div className="bg-emerald-950/80 border border-emerald-800 px-2 py-0.5 rounded text-right font-mono">
              <div className="text-xs font-bold text-emerald-400 leading-none flex items-center gap-1">
                <CheckCircle size={10} />
                {noiseReductionPct}%
              </div>
              <div className="text-[8px] text-emerald-300 uppercase">NOISE CUT</div>
            </div>
          )}
        </div>
      </div>

      {/* Funnel Status Banner */}
      {isCollapsed ? (
        <div className="mb-3 bg-gradient-to-r from-emerald-950/60 to-zinc-950/80 border border-emerald-800/80 rounded-lg p-2.5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-xs border border-emerald-500/40">
              1
            </div>
            <div>
              <div className="text-xs font-bold text-emerald-300 font-mono">
                {alertCount} ALERTS → 1 INCIDENT
              </div>
              <div className="text-[10px] text-zinc-400 font-mono">
                {incident.id} ({incident.scenario?.toUpperCase()}) · Root: {incident.root_service}
              </div>
            </div>
          </div>

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-[10px] font-mono text-zinc-400 hover:text-zinc-200 bg-zinc-800/60 hover:bg-zinc-800 px-2 py-1 rounded flex items-center gap-1 transition-colors"
          >
            {isExpanded ? 'Hide' : 'Inspect'} {alertCount}
            {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
        </div>
      ) : alertCount > 0 ? (
        <div className="mb-3 bg-amber-950/40 border border-amber-800/60 rounded-lg p-2 flex items-center justify-between text-xs font-mono text-amber-300">
          <span className="flex items-center gap-1.5">
            <Zap size={13} className="text-amber-400 animate-bounce" />
            Ingesting alert flood... Clustering active.
          </span>
          <span className="font-bold">{alertCount} / 56</span>
        </div>
      ) : (
        <div className="mb-2 py-3 text-center rounded-lg border border-dashed border-zinc-800 text-[11px] text-zinc-500 font-mono">
          Cluster telemetry calm. 0 active alerts.
        </div>
      )}

      {/* Collapsible / Live Alert Stream List */}
      {(isExpanded || (!isCollapsed && alertCount > 0)) && (
        <div className="max-h-48 overflow-y-auto space-y-1.5 pr-1 custom-scrollbar">
          {alerts.map((alt, idx) => (
            <div
              key={alt.id || idx}
              className="p-2 rounded bg-zinc-950/90 border border-zinc-800/80 text-[11px] font-mono hover:border-zinc-700 transition-colors"
            >
              <div className="flex items-center justify-between gap-1 mb-0.5">
                <span className="font-semibold text-rose-400 flex items-center gap-1">
                  <Bell size={10} />
                  {alt.service}
                </span>
                <span className="text-[9px] text-zinc-500">{alt.ts || '03:14:08'}</span>
              </div>
              <p className="text-zinc-300 text-[10px] leading-tight truncate">
                {alt.message}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
