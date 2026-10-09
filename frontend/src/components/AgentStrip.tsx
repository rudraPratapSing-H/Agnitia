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
    <div className="bg-white rounded-xl border border-stone-200 p-3 shadow-2xs font-mono shrink-0">
      {/* Header: Synchronized Process Title & State */}
      <div className="flex items-center justify-between pb-2 mb-2 border-b border-stone-200 select-none">
        <div className="flex items-center gap-2">
          <div className="p-1 rounded-md bg-stone-100 text-stone-700 border border-stone-200">
            <GitFork size={13} />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] font-black tracking-wider text-stone-900 uppercase">
                AUTONOMOUS SRE PIPELINE
              </span>
              <span className="text-[8px] bg-stone-100 text-stone-600 px-1 py-0.2 rounded border border-stone-200 font-bold">
                5 STAGES
              </span>
            </div>
            <span className="text-[9px] text-stone-500 font-sans block">
              Topological resolution & verification lifecycle
            </span>
          </div>
        </div>

        {/* Live Process Pill */}
        <div>
          {isPipelineActive ? (
            <span className="bg-amber-50 text-amber-900 border border-amber-300 px-2 py-0.5 rounded text-[8.5px] font-bold flex items-center gap-1.5 shadow-2xs">
              <Loader2 size={10} className="animate-spin text-amber-600" />
              <span>STAGE {activeStage?.num || '01'} ACTIVE</span>
            </span>
          ) : isResolved ? (
            <span className="bg-emerald-50 text-emerald-800 border border-emerald-300 px-2 py-0.5 rounded text-[8.5px] font-bold flex items-center gap-1 shadow-2xs">
              <CheckCircle2 size={10} className="text-emerald-600" />
              <span>PIPELINE VERIFIED</span>
            </span>
          ) : (
            <span className="bg-stone-50 text-stone-600 border border-stone-200 px-2 py-0.5 rounded text-[8.5px] font-bold flex items-center gap-1">
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

          let rowBg = 'bg-stone-50/60 border-stone-200/80 text-stone-500';
          let iconBoxBg = 'bg-stone-100 text-stone-400 border-stone-200';
          let titleColor = 'text-stone-700';

          if (state === 'running') {
            rowBg = 'bg-amber-50/80 border-amber-300 ring-1 ring-amber-200 shadow-2xs';
            iconBoxBg = 'bg-amber-100 text-amber-800 border-amber-300';
            titleColor = 'text-amber-950 font-black';
          } else if (state === 'done') {
            rowBg = 'bg-emerald-50/40 border-emerald-200/90';
            iconBoxBg = 'bg-emerald-100 text-emerald-800 border-emerald-300';
            titleColor = 'text-emerald-950 font-bold';
          }

          return (
            <React.Fragment key={stage.id}>
              <div
                onClick={stage.onClick}
                className={`p-2 rounded-lg border transition-all duration-200 ${rowBg} ${
                  stage.onClick ? 'cursor-pointer hover:border-stone-400' : ''
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
                        <Loader2 size={12} className="animate-spin text-amber-600" />
                      ) : state === 'done' ? (
                        <Check size={12} className="text-emerald-700" />
                      ) : (
                        <Icon size={12} />
                      )}
                    </div>

                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 leading-none">
                        <span className={`text-[10px] font-mono tracking-tight ${titleColor}`}>
                          {stage.num} {stage.title}
                        </span>
                        <span className="text-[8px] text-stone-400 font-sans hidden sm:inline">
                          • {stage.subtitle}
                        </span>
                      </div>
                      <div className="text-[9px] text-stone-600 font-sans truncate mt-0.5">
                        {desc}
                      </div>
                    </div>
                  </div>

                  {/* Right: State Pill Badge */}
                  <div className="shrink-0">
                    {state === 'done' ? (
                      <span className="bg-emerald-100 text-emerald-800 text-[8px] font-bold font-mono px-1.5 py-0.5 rounded border border-emerald-300 flex items-center gap-0.5">
                        <Check size={8} className="text-emerald-700" />
                        DONE
                      </span>
                    ) : state === 'running' ? (
                      <span className="bg-amber-100 text-amber-900 text-[8px] font-bold font-mono px-1.5 py-0.5 rounded border border-amber-300 flex items-center gap-0.5 animate-pulse">
                        ACTIVE
                      </span>
                    ) : (
                      <span className="bg-stone-100 text-stone-400 text-[8px] font-bold font-mono px-1.5 py-0.5 rounded border border-stone-200">
                        IDLE
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Connecting Vertical Process Arrow */}
              {idx < STAGES.length - 1 && (
                <div className="flex items-center justify-center -my-0.5 text-stone-300 select-none">
                  <div className={`w-0.5 h-1.5 ${state === 'done' ? 'bg-emerald-300' : 'bg-stone-200'}`} />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
