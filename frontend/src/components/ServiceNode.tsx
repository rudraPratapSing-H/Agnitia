// D:\CoffeeOverflow\Agnitia\frontend\src\components\ServiceNode.tsx - Clean, Spacious Architecture Node
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
      badgeText: 'HEALTHY',
      barColor: 'bg-emerald-600',
      iconBg: 'bg-stone-100 text-stone-600',
      accent: 'bg-white'
    },
    root_cause: {
      border: 'border-rose-500 ring-2 ring-rose-200 animate-pulse-root',
      badgeBg: 'bg-rose-50 text-rose-800 border-rose-300 font-bold',
      badgeText: 'ROOT CAUSE',
      barColor: 'bg-rose-600',
      iconBg: 'bg-rose-100 text-rose-700',
      accent: 'bg-rose-50/50'
    },
    impacted: {
      border: 'border-amber-400 ring-1 ring-amber-200',
      badgeBg: 'bg-amber-50 text-amber-800 border-amber-300',
      badgeText: 'IMPACTED',
      barColor: 'bg-amber-500',
      iconBg: 'bg-amber-100 text-amber-700',
      accent: 'bg-amber-50/30'
    },
    recovering: {
      border: 'border-sky-400 ring-1 ring-sky-200',
      badgeBg: 'bg-sky-50 text-sky-800 border-sky-300',
      badgeText: 'RECOVERING',
      barColor: 'bg-sky-500',
      iconBg: 'bg-sky-100 text-sky-700',
      accent: 'bg-sky-50/30'
    }
  }[status] || {
    border: 'border-stone-200',
    badgeBg: 'bg-stone-100 text-stone-700 border-stone-200',
    badgeText: status.toUpperCase(),
    barColor: 'bg-stone-400',
    iconBg: 'bg-stone-100 text-stone-600',
    accent: 'bg-white'
  };

  // What-If dynamic highlights
  let whatIfRing = '';
  if (_whatIfOrigin) {
    whatIfRing = 'ring-3 ring-sky-500 border-sky-500 shadow-md';
  } else if (_whatIfImpacted) {
    whatIfRing = 'ring-2 ring-amber-500 border-amber-500 shadow-xs';
  }

  return (
    <div
      className={`relative w-[230px] rounded-xl border ${statusStyles.border} ${statusStyles.accent} ${whatIfRing} shadow-sm hover:shadow-md p-3.5 transition-all duration-200 cursor-pointer ${
        selected ? 'ring-2 ring-stone-900 scale-[1.01]' : ''
      }`}
    >
      {/* Top Handle (Incoming dependencies) - dead center */}
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !-top-1.5 !bg-stone-400 !border-2 !border-white hover:!bg-stone-900 transition-colors"
      />
      {/* Bottom Handle (Outgoing dependencies) - dead center */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !-bottom-1.5 !bg-stone-400 !border-2 !border-white hover:!bg-stone-900 transition-colors"
      />

      {/* Header: Tier + Status */}
      <div className="flex items-center justify-between gap-1.5 mb-2">
        <div className="flex items-center gap-1.5">
          <div className={`p-1 rounded-md ${statusStyles.iconBg}`}>
            <Icon size={14} />
          </div>
          <span className="text-[10px] font-mono font-medium uppercase tracking-wider text-stone-500">
            {tier}
          </span>
        </div>

        <span
          className={`text-[9px] font-semibold tracking-wider px-1.5 py-0.5 rounded border ${statusStyles.badgeBg} flex items-center gap-1 font-mono`}
        >
          {status === 'root_cause' && <Flame size={10} className="text-rose-600" />}
          {status === 'impacted' && <AlertTriangle size={10} className="text-amber-600" />}
          {status === 'recovering' && <RotateCw size={10} className="text-sky-600 animate-spin" />}
          {status === 'healthy' && <CheckCircle2 size={10} className="text-emerald-600" />}
          {_whatIfOrigin ? 'SIMULATED ROOT' : _whatIfImpacted ? 'VICTIM' : statusStyles.badgeText}
        </span>
      </div>

      {/* Service Name */}
      <div className="font-mono font-bold text-xs text-stone-900 truncate mb-2.5">
        {label || id}
      </div>

      {/* Real-time Telemetry: Memory bar + CPU & Restarts */}
      <div className="space-y-1.5 font-mono text-[10px]">
        {/* Memory Bar */}
        <div>
          <div className="flex justify-between text-stone-500 mb-0.5 text-[9px]">
            <span>MEM: {memMb}MiB / {memLimit}MiB</span>
            <span className={memPercent > 90 ? 'text-rose-600 font-bold' : ''}>
              {memPercent}%
            </span>
          </div>
          <div className="h-1.5 w-full bg-stone-100 rounded-full overflow-hidden border border-stone-200">
            <div
              className={`h-full transition-all duration-300 ${statusStyles.barColor}`}
              style={{ width: `${memPercent}%` }}
            />
          </div>
        </div>

        {/* CPU & Restarts */}
        <div className="flex items-center justify-between text-[9px] text-stone-400 pt-0.5 border-t border-stone-100">
          <span className="flex items-center gap-1">
            <Cpu size={10} />
            <span>CPU: {cpuPct}%</span>
          </span>
          <span className={restarts > 0 ? 'text-rose-600 font-bold' : ''}>
            restarts: {restarts}
          </span>
        </div>
      </div>
    </div>
  );
}
