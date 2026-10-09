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
      border: 'border-stone-200/90 hover:border-stone-400',
      badgeBg: 'bg-emerald-50 text-emerald-800 border-emerald-200',
      badgeText: 'NOMINAL',
      barColor: 'bg-emerald-600',
      iconBg: 'bg-stone-100 text-stone-600',
      accent: 'bg-white'
    },
    root_cause: {
      border: 'border-rose-600 ring-4 ring-rose-400/80 shadow-2xl',
      badgeBg: 'bg-rose-100 text-rose-900 border-rose-400 font-bold',
      badgeText: 'ROOT FAILURE',
      barColor: 'bg-rose-600',
      iconBg: 'bg-rose-600 text-white',
      accent: 'bg-rose-50/95'
    },
    impacted: {
      border: 'border-amber-500 ring-2 ring-amber-300/80 shadow-md',
      badgeBg: 'bg-amber-100 text-amber-900 border-amber-300 font-semibold',
      badgeText: 'DEGRADED',
      barColor: 'bg-amber-500',
      iconBg: 'bg-amber-100 text-amber-800',
      accent: 'bg-amber-50/50'
    },
    recovering: {
      border: 'border-sky-400 ring-2 ring-sky-200 shadow-sm',
      badgeBg: 'bg-sky-50 text-sky-800 border-sky-300',
      badgeText: 'RECOVERING',
      barColor: 'bg-sky-500',
      iconBg: 'bg-sky-100 text-sky-700',
      accent: 'bg-sky-50/40'
    }
  }[status] || {
    border: 'border-stone-200',
    badgeBg: 'bg-stone-100 text-stone-700 border-stone-200',
    badgeText: status.toUpperCase(),
    barColor: 'bg-stone-400',
    iconBg: 'bg-stone-100 text-stone-600',
    accent: 'bg-white'
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
    ? '!bg-rose-500 !border-rose-100' 
    : status === 'impacted' 
    ? '!bg-amber-500 !border-amber-100' 
    : status === 'recovering' 
    ? '!bg-sky-500 !border-sky-100' 
    : '!bg-slate-400 !border-white';

  return (
    <div
      className={`relative w-[230px] rounded-xl border ${statusStyles.border} ${statusStyles.accent} ${whatIfRing} ${pulseClass} shadow-2xs hover:shadow-md p-3 transition-all duration-300 cursor-pointer ${
        selected ? 'ring-2 ring-stone-900 scale-[1.01]' : ''
      }`}
    >
      {/* Root Cause High-Alert Ping Beacon */}
      {status === 'root_cause' && (
        <span className="absolute -top-2.5 -right-2.5 flex h-6 w-6 z-30 pointer-events-none">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-500 opacity-80" />
          <span className="relative inline-flex rounded-full h-6 w-6 bg-rose-600 text-white text-[10px] font-black items-center justify-center shadow-lg border-2 border-white font-mono">
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
          <span className="text-[9px] font-mono font-bold uppercase tracking-wider text-stone-500">
            {tier}
          </span>
        </div>

        <span
          className={`text-[8px] font-bold tracking-wider px-1.5 py-0.5 rounded border ${statusStyles.badgeBg} flex items-center gap-1 font-mono`}
        >
          {status === 'root_cause' && <Flame size={9} className="text-white animate-pulse" />}
          {status === 'impacted' && <AlertTriangle size={9} className="text-amber-600" />}
          {status === 'recovering' && <RotateCw size={9} className="text-sky-600 animate-spin" />}
          {status === 'healthy' && <CheckCircle2 size={9} className="text-emerald-600" />}
          {_whatIfOrigin ? 'SIMULATED ROOT' : _whatIfImpacted ? 'DOWNSTREAM VICTIM' : statusStyles.badgeText}
        </span>
      </div>

      {/* Service Name & Pod Identifier */}
      <div className="mb-2">
        <div className="font-mono font-black text-xs text-stone-900 truncate">
          {label || id}
        </div>
        <div className="text-[9px] text-stone-400 font-mono truncate">
          pod/{id}-0 • ns:prod
        </div>
      </div>

      {/* Telemetry Metric Bars */}
      <div className="space-y-1.5 font-mono text-[9px]">
        {/* Memory Bar */}
        <div>
          <div className="flex justify-between text-stone-500 mb-0.5 text-[8.5px]">
            <span>MEM: {status === 'root_cause' ? memLimit : memMb}MiB / {memLimit}MiB</span>
            <span className={effectiveMemPercent >= 90 ? 'text-rose-600 font-bold' : ''}>
              {effectiveMemPercent}%
            </span>
          </div>
          <div className="h-1.5 w-full bg-stone-100 rounded-full overflow-hidden border border-stone-200">
            <div
              className={`h-full transition-all duration-300 ${status === 'root_cause' ? 'bg-rose-600 animate-pulse' : statusStyles.barColor}`}
              style={{ width: `${effectiveMemPercent}%` }}
            />
          </div>
        </div>

        {/* CPU & K8s State Indicator */}
        <div className="flex items-center justify-between text-[8.5px] text-stone-500 pt-1 border-t border-stone-100">
          <span className="flex items-center gap-1">
            <Cpu size={10} className="text-stone-400" />
            <span>CPU: {cpuPct}%</span>
          </span>
          {status === 'root_cause' ? (
            <span className="text-rose-700 font-bold bg-rose-50 px-1 rounded border border-rose-200 animate-pulse">
              exitCode: 137
            </span>
          ) : restarts > 0 ? (
            <span className="text-rose-600 font-bold">
              restarts: {restarts}
            </span>
          ) : (
            <span className="text-stone-400">
              ready: 1/1
            </span>
          )}
        </div>

        {/* Explicit Dependency Connectivity Footer */}
        {data.depends_on && data.depends_on.length > 0 ? (
          <div className="flex items-center gap-1.5 text-[8px] font-mono text-stone-600 pt-1.5 border-t border-stone-200/80 flex-wrap">
            <span className="text-stone-400 font-bold uppercase tracking-wider shrink-0 text-[7.5px]">Depends on:</span>
            <div className="flex flex-wrap gap-1">
              {data.depends_on.map((dep: string) => (
                <span
                  key={dep}
                  className="bg-stone-100 text-stone-800 font-semibold px-1.5 py-0.2 rounded border border-stone-300/90 text-[7.5px]"
                >
                  {dep}
                </span>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-[8px] font-mono text-stone-400 pt-1.5 border-t border-stone-200/80">
            <span className="text-emerald-700 font-bold uppercase tracking-wider bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-300 shrink-0 text-[7.5px]">
              Root Source
            </span>
            <span className="text-stone-500 text-[7.5px]">Data Tier • 0 Upstream</span>
          </div>
        )}
      </div>
    </div>
  );
}
