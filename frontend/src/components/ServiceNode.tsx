// frontend/src/components/ServiceNode.jsx - Custom React Flow Node with 4 Status States
import React from 'react';
import { Handle, Position } from '@xyflow/react';
import { Database, Shield, Server, Globe, Cpu, AlertTriangle, CheckCircle2, RotateCw, Flame } from 'lucide-react';

const TIER_ICONS = {
  data: Database,
  backend: Server,
  edge: Shield,
  frontend: Globe
};

export default function ServiceNode({ data, selected }) {
  const { id, label, tier, status, metrics } = data;
  const Icon = TIER_ICONS[tier] || Server;

  const memMb = metrics?.mem_mb ?? 0;
  const memLimit = metrics?.mem_limit_mb ?? 64;
  const memPercent = Math.min(Math.round((memMb / memLimit) * 100), 100);
  const cpuPct = metrics?.cpu_pct ?? 0;
  const restarts = metrics?.restarts ?? 0;

  // Status-specific classes & glowing themes
  const statusStyles = {
    healthy: {
      border: 'border-emerald-500/50 hover:border-emerald-400',
      glow: 'shadow-[0_0_15px_rgba(16,185,129,0.15)]',
      badgeBg: 'bg-emerald-950/80 text-emerald-400 border-emerald-800',
      badgeText: 'HEALTHY',
      barColor: 'bg-emerald-500',
      iconColor: 'text-emerald-400'
    },
    root_cause: {
      border: 'border-red-500 animate-pulse-glow',
      glow: 'shadow-[0_0_30px_rgba(239,68,68,0.5)]',
      badgeBg: 'bg-red-950/90 text-red-300 border-red-700 animate-pulse',
      badgeText: 'ROOT CAUSE',
      barColor: 'bg-red-500',
      iconColor: 'text-red-400'
    },
    impacted: {
      border: 'border-amber-500/80',
      glow: 'shadow-[0_0_20px_rgba(245,158,11,0.25)]',
      badgeBg: 'bg-amber-950/80 text-amber-300 border-amber-700',
      badgeText: 'IMPACTED',
      barColor: 'bg-amber-500',
      iconColor: 'text-amber-400'
    },
    recovering: {
      border: 'border-cyan-500 animate-pulse',
      glow: 'shadow-[0_0_25px_rgba(6,182,212,0.35)]',
      badgeBg: 'bg-cyan-950/80 text-cyan-300 border-cyan-700',
      badgeText: 'RECOVERING',
      barColor: 'bg-cyan-400',
      iconColor: 'text-cyan-400'
    }
  }[status] || {
    border: 'border-zinc-700',
    glow: '',
    badgeBg: 'bg-zinc-800 text-zinc-400 border-zinc-700',
    badgeText: status.toUpperCase(),
    barColor: 'bg-zinc-500',
    iconColor: 'text-zinc-400'
  };

  return (
    <div
      className={`relative min-w-[210px] rounded-xl bg-zinc-900/95 backdrop-blur-md border ${statusStyles.border} ${statusStyles.glow} p-3.5 transition-all duration-300 ${
        selected ? 'ring-2 ring-indigo-400 scale-[1.02]' : ''
      }`}
    >
      {/* React Flow Handles */}
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-zinc-600 !border-2 !border-zinc-900 hover:!bg-indigo-400 !-left-1.5 transition-colors"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!w-3 !h-3 !bg-zinc-600 !border-2 !border-zinc-900 hover:!bg-indigo-400 !-right-1.5 transition-colors"
      />

      {/* Header: Tier + Status Chip */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-1.5">
          <div className={`p-1.5 rounded-lg bg-zinc-800/80 ${statusStyles.iconColor}`}>
            <Icon size={15} />
          </div>
          <span className="text-[10px] font-mono tracking-wider uppercase text-zinc-400">
            {tier}
          </span>
        </div>

        <span
          className={`text-[9px] font-semibold tracking-wider px-2 py-0.5 rounded-full border ${statusStyles.badgeBg} flex items-center gap-1`}
        >
          {status === 'root_cause' && <Flame size={10} className="animate-bounce" />}
          {status === 'impacted' && <AlertTriangle size={10} />}
          {status === 'recovering' && <RotateCw size={10} className="animate-spin" />}
          {status === 'healthy' && <CheckCircle2 size={10} />}
          {statusStyles.badgeText}
        </span>
      </div>

      {/* Service Name */}
      <div className="mb-2.5">
        <h4 className="text-sm font-bold text-zinc-100 tracking-tight flex items-center justify-between">
          {label}
          {restarts > 0 && (
            <span className="text-[10px] font-mono font-normal text-rose-400 bg-rose-950/60 px-1.5 py-0.2 rounded border border-rose-800">
              {restarts} restarts
            </span>
          )}
        </h4>
        <span className="text-[10px] font-mono text-zinc-500">{id}</span>
      </div>

      {/* Telemetry Metrics Bar */}
      <div className="space-y-1.5 bg-zinc-950/70 p-2 rounded-lg border border-zinc-800/80">
        {/* Memory Bar */}
        <div>
          <div className="flex justify-between text-[10px] font-mono mb-1">
            <span className="text-zinc-400">MEM</span>
            <span className={memPercent >= 90 ? 'text-rose-400 font-bold' : 'text-zinc-300'}>
              {memMb} / {memLimit} MB ({memPercent}%)
            </span>
          </div>
          <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-500 rounded-full ${
                memPercent >= 95
                  ? 'bg-red-500 animate-pulse'
                  : memPercent >= 75
                  ? 'bg-amber-500'
                  : statusStyles.barColor
              }`}
              style={{ width: `${memPercent}%` }}
            />
          </div>
        </div>

        {/* CPU & Sub-metrics */}
        <div className="flex items-center justify-between text-[10px] font-mono pt-0.5 text-zinc-400">
          <div className="flex items-center gap-1">
            <Cpu size={11} className="text-zinc-500" />
            <span>CPU</span>
          </div>
          <span className={cpuPct >= 80 ? 'text-rose-400 font-bold' : 'text-zinc-300'}>
            {cpuPct}%
          </span>
        </div>
      </div>
    </div>
  );
}
