// D:\CoffeeOverflow\Agnitia\frontend\src\components\ServiceNode.tsx - Fixed Width, Spacious Node
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
  data: ServiceNodeType;
  selected?: boolean;
}

export default function ServiceNode({ data, selected }: ServiceNodeProps) {
  const { id, label, tier, status, metrics } = data;
  const Icon = TIER_ICONS[tier] || Server;

  const memMb = metrics?.mem_mb ?? 0;
  const memLimit = metrics?.mem_limit_mb ?? 64;
  const memPercent = Math.min(Math.round((memMb / memLimit) * 100), 100);
  const cpuPct = metrics?.cpu_pct ?? 0;
  const restarts = metrics?.restarts ?? 0;

  const statusStyles = {
    healthy: {
      border: 'border-stone-200/90 hover:border-stone-300',
      badgeBg: 'bg-emerald-50 text-emerald-800 border-emerald-200',
      badgeText: 'HEALTHY',
      barColor: 'bg-emerald-600',
      iconBg: 'bg-stone-100 text-stone-600',
      accent: 'bg-white'
    },
    root_cause: {
      border: 'border-rose-500 animate-pulse-root',
      badgeBg: 'bg-rose-50 text-rose-800 border-rose-300 font-bold',
      badgeText: 'ROOT CAUSE',
      barColor: 'bg-rose-600',
      iconBg: 'bg-rose-100 text-rose-700',
      accent: 'bg-rose-50/40'
    },
    impacted: {
      border: 'border-amber-400',
      badgeBg: 'bg-amber-50 text-amber-800 border-amber-300',
      badgeText: 'IMPACTED',
      barColor: 'bg-amber-500',
      iconBg: 'bg-amber-100 text-amber-700',
      accent: 'bg-amber-50/20'
    },
    recovering: {
      border: 'border-sky-400',
      badgeBg: 'bg-sky-50 text-sky-800 border-sky-300',
      badgeText: 'RECOVERING',
      barColor: 'bg-sky-500',
      iconBg: 'bg-sky-100 text-sky-700',
      accent: 'bg-sky-50/20'
    }
  }[status] || {
    border: 'border-stone-200',
    badgeBg: 'bg-stone-100 text-stone-700 border-stone-200',
    badgeText: status.toUpperCase(),
    barColor: 'bg-stone-400',
    iconBg: 'bg-stone-100 text-stone-600',
    accent: 'bg-white'
  };

  return (
    <div
      className={`relative w-[220px] rounded-xl border ${statusStyles.border} ${statusStyles.accent} shadow-sm hover:shadow-md p-3.5 transition-all duration-200 ${
        selected ? 'ring-2 ring-stone-800 scale-[1.01]' : ''
      }`}
    >
      {/* Top Handle (Incoming dependencies) */}
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !-top-1.5 !bg-stone-400 !border-2 !border-white hover:!bg-stone-800"
      />
      {/* Bottom Handle (Outgoing dependencies) */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !-bottom-1.5 !bg-stone-400 !border-2 !border-white hover:!bg-stone-800"
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
          {statusStyles.badgeText}
        </span>
      </div>

      {/* Service Name & Restart Badge */}
      <div className="mb-2">
        <h4 className="text-xs font-bold text-stone-900 tracking-tight flex items-center justify-between">
          <span className="truncate">{label}</span>
          {restarts > 0 && (
            <span className="text-[9px] font-mono font-normal text-rose-700 bg-rose-50 px-1 py-0.2 rounded border border-rose-200 shrink-0">
              {restarts}r
            </span>
          )}
        </h4>
        <span className="text-[10px] font-mono text-stone-400 block truncate">{id}</span>
      </div>

      {/* Telemetry Metrics Bar */}
      <div className="space-y-1.5 bg-stone-50/90 p-2 rounded-lg border border-stone-200/60">
        <div>
          <div className="flex justify-between text-[10px] font-mono mb-1">
            <span className="text-stone-500">Memory</span>
            <span className={memPercent >= 90 ? 'text-rose-700 font-bold' : 'text-stone-700 font-medium'}>
              {memMb}/{memLimit}MB ({memPercent}%)
            </span>
          </div>
          <div className="w-full h-1.5 bg-stone-200 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-300 rounded-full ${
                memPercent >= 95
                  ? 'bg-rose-600'
                  : memPercent >= 75
                  ? 'bg-amber-500'
                  : statusStyles.barColor
              }`}
              style={{ width: `${memPercent}%` }}
            />
          </div>
        </div>

        <div className="flex items-center justify-between text-[10px] font-mono pt-0.5 text-stone-500">
          <div className="flex items-center gap-1">
            <Cpu size={11} className="text-stone-400" />
            <span>CPU</span>
          </div>
          <span className={cpuPct >= 80 ? 'text-rose-700 font-bold' : 'text-stone-700 font-medium'}>
            {cpuPct}%
          </span>
        </div>
      </div>
    </div>
  );
}
