// frontend/src/components/AgentStrip.tsx - Vertical SRE Process Pipeline Stepper
import React from 'react';
import {
  Filter,
  GitFork,
  ShieldCheck,
  Play,
  CheckCircle2,
  Loader2,
  Check,
  Activity,
  ArrowDown
} from 'lucide-react';
import { AgentStep, Incident, Alert } from '../types';

interface AgentStripProps {
  agentSteps: AgentStep[];
  incident: Incident | null;
  alerts?: Alert[];
  onOpenEvidence?: () => void;
  onOpenApproval?: () => void;
  onOpenPostmortem?: () => void;
}

export default function AgentStrip({
  agentSteps,
  incident,
  alerts = [],
  onOpenEvidence,
  onOpenApproval,
  onOpenPostmortem
}: AgentStripProps) {
  const isResolved = incident?.status === 'resolved';

  const getStageState = (stageId: string): 'idle' | 'running' | 'done' => {
    if (isResolved) return 'done';

    const stepsForStage = agentSteps.filter((s) => s.agent === stageId);
    if (stepsForStage.length > 0) {
      const latest = stepsForStage[stepsForStage.length - 1];
      if (latest.status === 'done') return 'done';
      if (latest.status === 'running') return 'running';
    }

    if (stageId === 'triage') {
      if (incident) return 'done';
      if (alerts.length > 0) return 'running';
      return 'idle';
    }

    if (stageId === 'diagnose') {
      if (incident?.rca) return 'done';
      if (incident?.status === 'analyzing') return 'running';
      return 'idle';
    }

    if (stageId === 'plan') {
      if (incident?.playbook?.steps?.length) return 'done';
      if (incident?.rca) return 'running';
      return 'idle';
    }

    if (stageId === 'execute') {
      if (incident?.status === 'healing' || incident?.status === 'awaiting_approval') return 'running';
      return 'idle';
    }

    if (stageId === 'verify') {
      if (incident?.status === 'healing') return 'running';
      return 'idle';
    }

    return 'idle';
  };

  const getStageDesc = (stageId: string, state: string) => {
    const alertCount = incident?.raw_alert_count || alerts.length;
    const root = incident?.root_service || 'root';

    switch (stageId) {
      case 'triage':
        if (incident) return `${alertCount || 1} alerts collapsed -> 1 incident (${root})`;
        if (alertCount > 0) return `Correlating ${alertCount} raw alert signals...`;
        if (state === 'running') return 'Correlating alerts...';
        return 'Telemetry stream active (0 firing)';

      case 'diagnose':
        if (incident?.rca) {
          const conf = Math.round((incident.rca.confidence || 0.95) * 100);
          return `Confirmed root: ${root} (${conf}% conf) • ${incident.rca.evidence?.length || 3} citations`;
        }
        if (state === 'running') return 'Traversing topological dependency DAG...';
        return 'Topological invariant checks';

      case 'plan':
        if (incident?.playbook?.steps?.length) {
          return `${incident.playbook.steps.length} sequential recovery steps synthesized`;
        }
        if (state === 'running') return 'Calculating dependency order...';
        return 'Dependency-ordered planner';

      case 'execute':
        if (incident?.status === 'resolved') return 'Remediation patch executed & verified';
        if (incident?.status === 'healing') return 'Applying declarative patch to cluster...';
        if (incident?.status === 'awaiting_approval') return 'Awaiting operator authorization (APEX-04)';
        return 'Guarded execution engine';

      case 'verify':
        if (incident?.status === 'resolved') return 'All services 200 OK • Zero downtime';
        if (state === 'running') return 'Probing endpoint readiness & latencies...';
        return 'Continuous healthz probes';

      default:
        return '';
    }
  };

  const STAGES = [
    {
      id: 'triage',
      num: '01',
      title: 'INGEST & DEDUP',
      subtitle: 'Alert Clustering',
      icon: Filter
    },
    {
      id: 'diagnose',
      num: '02',
      title: 'TOPOLOGICAL RCA',
      subtitle: 'Causal Inference',
      icon: GitFork,
      onClick: onOpenEvidence
    },
    {
      id: 'plan',
      num: '03',
      title: 'DAG PLANNER',
      subtitle: 'Recovery Playbook',
      icon: ShieldCheck
    },
    {
      id: 'execute',
      num: '04',
      title: 'GUARDED APPLY',
      subtitle: 'Operator Gate',
      icon: Play,
      onClick: onOpenApproval
    },
    {
      id: 'verify',
      num: '05',
      title: 'PROBE VERIFY',
      subtitle: 'Readiness Validation',
      icon: CheckCircle2,
      onClick: onOpenPostmortem
    }
  ];

  const activeStage = STAGES.find((s) => getStageState(s.id) === 'running');
  const isPipelineActive = Boolean(activeStage || (alerts.length > 0 && !isResolved));

  return (
    <div className="bg-ink-900 rounded-xl border border-ink-700 p-3 font-mono shrink-0">
      {/* Header: Synchronized Process Title & State */}
      <div className="flex items-center justify-between pb-2 mb-2 border-b border-ink-700 select-none">
        <div className="flex items-center gap-2">
          <div className="p-1 rounded-md bg-copper-500/12 text-copper-400 border border-copper-500/25">
            <GitFork size={13} />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] font-bold tracking-wider text-ink-50 uppercase">
                Autonomous SRE Pipeline
              </span>
              <span className="text-[8px] bg-ink-700 text-ink-300 px-1 py-0.2 rounded border border-ink-600 font-bold">
                5 STAGES
              </span>
            </div>
            <span className="text-[9px] text-ink-500 font-sans block">
              Topological resolution & verification lifecycle
            </span>
          </div>
        </div>

        {/* Live Process Pill */}
        <div>
          {isPipelineActive ? (
            <span className="bg-amber-500/12 text-amber-300 border border-amber-500/35 px-2 py-0.5 rounded text-[8.5px] font-bold flex items-center gap-1.5">
              <Loader2 size={10} className="animate-spin text-amber-400" />
              <span>STAGE {activeStage?.num || '01'} ACTIVE</span>
            </span>
          ) : isResolved ? (
            <span className="bg-emerald-500/12 text-emerald-300 border border-emerald-500/35 px-2 py-0.5 rounded text-[8.5px] font-bold flex items-center gap-1">
              <CheckCircle2 size={10} className="text-emerald-400" />
              <span>PIPELINE VERIFIED</span>
            </span>
          ) : (
            <span className="bg-ink-800 text-ink-400 border border-ink-600 px-2 py-0.5 rounded text-[8.5px] font-bold flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <span>STANDBY</span>
            </span>
          )}
        </div>
      </div>

      {/* Vertical Stepper: 5 Stages Stacked with Process Flow Connector Lines */}
      <div className="space-y-1">
        {STAGES.map((stage, idx) => {
          const state = getStageState(stage.id);
          const Icon = stage.icon;
          const desc = getStageDesc(stage.id, state);

          let rowBg = 'bg-ink-850 border-ink-700 text-ink-500';
          let iconBoxBg = 'bg-ink-700 text-ink-500 border-ink-600';
          let titleColor = 'text-ink-300';

          if (state === 'running') {
            rowBg = 'bg-amber-500/8 border-amber-500/35 ring-1 ring-amber-500/20';
            iconBoxBg = 'bg-amber-500/15 text-amber-300 border-amber-500/40';
            titleColor = 'text-amber-200 font-black';
          } else if (state === 'done') {
            rowBg = 'bg-emerald-500/6 border-emerald-500/25';
            iconBoxBg = 'bg-emerald-500/15 text-emerald-300 border-emerald-500/35';
            titleColor = 'text-emerald-200 font-bold';
          }

          return (
            <React.Fragment key={stage.id}>
              <div
                onClick={stage.onClick}
                className={`p-2 rounded-lg border transition-all duration-200 ${rowBg} ${
                  stage.onClick ? 'cursor-pointer hover:border-ink-400' : ''
                }`}
                title={stage.onClick ? `Click to inspect ${stage.title}` : undefined}
              >
                <div className="flex items-center justify-between gap-2">
                  {/* Left: Stage Icon + Title + Real-time Descr */}
                  <div className="flex items-center gap-2 min-w-0">
                    <div
                      className={`w-6 h-6 rounded-md flex items-center justify-center shrink-0 border ${iconBoxBg}`}
                    >
                      {state === 'running' ? (
                        <Loader2 size={12} className="animate-spin text-amber-400" />
                      ) : state === 'done' ? (
                        <Check size={12} className="text-emerald-300" />
                      ) : (
                        <Icon size={12} />
                      )}
                    </div>

                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 leading-none">
                        <span className={`text-[10px] font-mono tracking-tight ${titleColor}`}>
                          {stage.num} {stage.title}
                        </span>
                        <span className="text-[8px] text-ink-500 font-sans hidden sm:inline">
                          • {stage.subtitle}
                        </span>
                      </div>
                      <div className="text-[9px] text-ink-400 font-sans truncate mt-0.5">
                        {desc}
                      </div>
                    </div>
                  </div>

                  {/* Right: State Pill Badge */}
                  <div className="shrink-0">
                    {state === 'done' ? (
                      <span className="bg-emerald-500/15 text-emerald-300 text-[8px] font-bold font-mono px-1.5 py-0.5 rounded border border-emerald-500/35 flex items-center gap-0.5">
                        <Check size={8} className="text-emerald-300" />
                        DONE
                      </span>
                    ) : state === 'running' ? (
                      <span className="bg-amber-500/15 text-amber-300 text-[8px] font-bold font-mono px-1.5 py-0.5 rounded border border-amber-500/40 flex items-center gap-0.5 animate-pulse">
                        ACTIVE
                      </span>
                    ) : (
                      <span className="bg-ink-700 text-ink-500 text-[8px] font-bold font-mono px-1.5 py-0.5 rounded border border-ink-600">
                        IDLE
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Connecting Vertical Process Arrow */}
              {idx < STAGES.length - 1 && (
                <div className="flex items-center justify-center -my-0.5 text-ink-600 select-none">
                  <div className={`w-0.5 h-1.5 ${state === 'done' ? 'bg-emerald-500/40' : 'bg-ink-700'}`} />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
