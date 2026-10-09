// D:\CoffeeOverflow\Agnitia\frontend\src\components\ServiceNode.tsx - Production K8s Pod Service Node
import React from 'react';
import { Handle, Position } from '@xyflow/react';
import { Database, Shield, Server, Globe, Cpu, AlertTriangle, CheckCircle2, RotateCw, Flame } from 'lucide-react';
import { ServiceNode as ServiceNodeType } from '../types';

const TIER_ICONS: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  data: Database,
  backend: Server,
  edge: Shield,
  frontend: Globe
};

interface ServiceNodeProps {
  data: ServiceNodeType & {
    _whatIfOrigin?: boolean;
    _whatIfImpacted?: boolean;
    _isDimmed?: boolean;
  };
  selected?: boolean;
}

export default function ServiceNode({ data, selected }: ServiceNodeProps) {
  const { id, label, tier, status, metrics, _whatIfOrigin, _whatIfImpacted } = data;
  const Icon = TIER_ICONS[tier] || Server;

  const memMb = metrics?.mem_mb ?? 0;
  const memLimit = metrics?.mem_limit_mb ?? 64;
  const memPercent = Math.min(Math.round((memMb / memLimit) * 100), 100);
  const cpuPct = metrics?.cpu_pct ?? 0;
  const restarts = metrics?.restarts ?? 0;

  const statusStyles = {
    healthy: {
      border: 'border-ink-600 hover:border-ink-400',
      badgeBg: 'bg-emerald-500/12 text-emerald-300 border-emerald-500/30',
      badgeText: 'NOMINAL',
      barColor: 'bg-emerald-500',
      iconBg: 'bg-ink-700 text-ink-300',
      accent: 'bg-ink-850'
    },
    root_cause: {
      border: 'border-rose-500 ring-4 ring-rose-500/40 shadow-2xl shadow-rose-950/60',
      badgeBg: 'bg-rose-500/18 text-rose-300 border-rose-500/50 font-bold',
      badgeText: 'ROOT FAILURE',
      barColor: 'bg-rose-500',
      iconBg: 'bg-rose-500 text-ink-950',
      accent: 'bg-rose-950/40'
    },
    impacted: {
      border: 'border-amber-500 ring-2 ring-amber-500/35 shadow-lg shadow-amber-950/40',
      badgeBg: 'bg-amber-500/15 text-amber-300 border-amber-500/40 font-semibold',
      badgeText: 'DEGRADED',
      barColor: 'bg-amber-500',
      iconBg: 'bg-amber-500/20 text-amber-300',
      accent: 'bg-amber-950/25'
    },
    recovering: {
      border: 'border-sky-500 ring-2 ring-sky-500/25',
      badgeBg: 'bg-sky-500/12 text-sky-300 border-sky-500/35',
      badgeText: 'RECOVERING',
      barColor: 'bg-sky-500',
      iconBg: 'bg-sky-500/18 text-sky-300',
      accent: 'bg-sky-950/20'
    }
  }[status] || {
    border: 'border-ink-600',
    badgeBg: 'bg-ink-700 text-ink-300 border-ink-600',
    badgeText: status.toUpperCase(),
    barColor: 'bg-ink-500',
    iconBg: 'bg-ink-700 text-ink-300',
    accent: 'bg-ink-850'
  };

  // What-If highlights
  let whatIfRing = '';
  if (_whatIfOrigin) {
    whatIfRing = 'ring-3 ring-sky-500 border-sky-500 shadow-md';
  } else if (_whatIfImpacted) {
    whatIfRing = 'ring-2 ring-amber-500 border-amber-500 shadow-xs';
  }

  const pulseClass = status === 'root_cause' ? 'animate-grow-red' : status === 'impacted' ? 'animate-pulse-impacted' : '';
  const effectiveMemPercent = status === 'root_cause' ? 100 : memPercent;

  const handleColor = status === 'root_cause'
    ? '!bg-rose-500 !border-ink-900'
    : status === 'impacted'
    ? '!bg-amber-500 !border-ink-900'
    : status === 'recovering'
    ? '!bg-sky-500 !border-ink-900'
    : '!bg-ink-400 !border-ink-900';

  return (
    <div
      className={`relative w-[240px] rounded-xl border ${statusStyles.border} ${statusStyles.accent} ${whatIfRing} ${pulseClass} shadow-lg shadow-black/30 hover:shadow-xl p-3.5 transition-all duration-300 cursor-pointer ${
        selected ? 'ring-2 ring-copper-400 scale-[1.01]' : ''
      }`}
    >
      {/* Root Cause High-Alert Ping Beacon */}
      {status === 'root_cause' && (
        <span className="absolute -top-2.5 -right-2.5 flex h-6 w-6 z-30 pointer-events-none">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-500 opacity-80" />
          <span className="relative inline-flex rounded-full h-6 w-6 bg-rose-500 text-ink-950 text-[10px] font-black items-center justify-center shadow-lg border-2 border-ink-950 font-mono">
            !
          </span>
        </span>
      )}

      {/* Top Handle (Incoming dependencies) */}
      <Handle
        type="target"
        position={Position.Top}
        className={`!w-3 !h-3 !-top-1.5 ${handleColor} !border-2 hover:!scale-125 transition-all shadow-xs`}
      />
      {/* Bottom Handle (Outgoing dependencies) */}
      <Handle
        type="source"
        position={Position.Bottom}
        className={`!w-3 !h-3 !-bottom-1.5 ${handleColor} !border-2 hover:!scale-125 transition-all shadow-xs`}
      />

      {/* Header: Tier + K8s Tag */}
      <div className="flex items-center justify-between gap-1.5 mb-1.5">
        <div className="flex items-center gap-1.5">
          <div className={`p-1 rounded-md ${statusStyles.iconBg}`}>
            <Icon size={13} />
          </div>
          <span className="text-[9.5px] font-mono font-bold uppercase tracking-wider text-ink-400">
            {tier}
          </span>
        </div>

        <span
          className={`text-[8.5px] font-bold tracking-wider px-1.5 py-0.5 rounded border ${statusStyles.badgeBg} flex items-center gap-1 font-mono`}
        >
          {status === 'root_cause' && <Flame size={9} className="text-rose-300 animate-pulse" />}
          {status === 'impacted' && <AlertTriangle size={9} className="text-amber-400" />}
          {status === 'recovering' && <RotateCw size={9} className="text-sky-400 animate-spin" />}
          {status === 'healthy' && <CheckCircle2 size={9} className="text-emerald-400" />}
          {_whatIfOrigin ? 'SIMULATED ROOT' : _whatIfImpacted ? 'DOWNSTREAM VICTIM' : statusStyles.badgeText}
        </span>
      </div>

      {/* Service Name & Pod Identifier */}
      <div className="mb-2">
        <div className="font-mono font-black text-[12.5px] text-ink-50 tracking-tight truncate">
          {label || id}
        </div>
        <div className="text-[9.5px] text-ink-500 font-mono truncate">
          pod/{id}-0 • ns:prod
        </div>
      </div>

      {/* Telemetry Metric Bars */}
      <div className="space-y-1.5 font-mono text-[9.5px]">
        {/* Memory Bar */}
        <div>
          <div className="flex justify-between text-ink-400 mb-0.5 text-[9px]">
            <span className="font-semibold">MEM: {status === 'root_cause' ? memLimit : memMb}MiB / {memLimit}MiB</span>
            <span className={effectiveMemPercent >= 90 ? 'text-rose-400 font-bold' : 'font-bold text-ink-300'}>
              {effectiveMemPercent}%
            </span>
          </div>
          <div className="h-2 w-full bg-ink-700 rounded-full overflow-hidden border border-ink-600">
            <div
              className={`h-full transition-all duration-300 ${status === 'root_cause' ? 'bg-rose-500 animate-pulse' : statusStyles.barColor}`}
              style={{ width: `${effectiveMemPercent}%` }}
            />
          </div>
        </div>

        {/* CPU & K8s State Indicator */}
        <div className="flex items-center justify-between text-[9px] text-ink-400 pt-1 border-t border-ink-700 font-medium">
          <span className="flex items-center gap-1">
            <Cpu size={11} className="text-ink-500" />
            <span>CPU: {cpuPct}%</span>
          </span>
          {status === 'root_cause' ? (
            <span className="text-rose-300 font-bold bg-rose-500/15 px-1.5 py-0.5 rounded border border-rose-500/40 animate-pulse">
              exitCode: 137
            </span>
          ) : restarts > 0 ? (
            <span className="text-rose-300 font-bold bg-rose-500/12 px-1 rounded border border-rose-500/30">
              restarts: {restarts}
            </span>
          ) : (
            <span className="text-emerald-300 font-bold bg-emerald-500/12 px-1 rounded border border-emerald-500/30">
              ready: 1/1
            </span>
          )}
        </div>

        {/* Explicit Dependency Connectivity Footer */}
        {data.depends_on && data.depends_on.length > 0 ? (
          <div className="flex items-center gap-1.5 text-[8.5px] font-mono text-ink-300 pt-1.5 border-t border-ink-700/80 flex-wrap">
            <span className="text-ink-500 font-bold uppercase tracking-wider shrink-0 text-[8px]">Depends on:</span>
            <div className="flex flex-wrap gap-1">
              {data.depends_on.map((dep: string) => (
                <span
                  key={dep}
                  className="bg-ink-700 text-ink-200 font-bold px-1.5 py-0.5 rounded border border-ink-600 text-[8px]"
                >
                  {dep}
                </span>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-[8.5px] font-mono text-ink-500 pt-1.5 border-t border-ink-700/80">
            <span className="text-emerald-300 font-bold uppercase tracking-wider bg-emerald-500/12 px-1.5 py-0.5 rounded border border-emerald-500/30 shrink-0 text-[8px]">
              Root Source
            </span>
            <span className="text-ink-400 text-[8px] font-medium">Data Tier • 0 Upstream</span>
          </div>
        )}
      </div>
    </div>
  );
}
