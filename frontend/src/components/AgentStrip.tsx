// D:\CoffeeOverflow\Agnitia\frontend\src\components\AgentStrip.tsx - Dynamic SRE Pipeline Strip
import React from 'react';
import { Filter, GitFork, ShieldCheck, Play, CheckCircle2, Loader2, ChevronRight } from 'lucide-react';
import { AgentStep, Incident, Alert } from '../types';

interface AgentStripProps {
  agentSteps: AgentStep[];
  incident: Incident | null;
  alerts?: Alert[];
}

export default function AgentStrip({ agentSteps, incident, alerts = [] }: AgentStripProps) {
  const getStageState = (stageId: string) => {
    const stepsForStage = agentSteps.filter((s) => s.agent === stageId);
    if (stepsForStage.length === 0) {
      if (stageId === 'triage' && (incident || alerts.length > 0)) return 'done';
      return 'idle';
    }
    const latest = stepsForStage[stepsForStage.length - 1];
    return latest.status || 'running';
  };

  const getStageDesc = (stageId: string, state: string) => {
    const alertCount = incident?.raw_alert_count || alerts.length;

    switch (stageId) {
      case 'triage':
        if (incident) return `${alertCount || 1} alerts correlated -> 1 root`;
        if (alertCount > 0) return `${alertCount} firing alerts incoming`;
        if (state === 'running') return 'Correlating alerts...';
        return 'Monitoring alert streams (0 firing)';

      case 'diagnose':
        if (incident?.rca) {
          const root = incident.root_service;
          const conf = Math.round((incident.rca.confidence || 0.95) * 100);
          return `Root: ${root} (${conf}% conf)`;
        }
        if (state === 'running') return 'Traversing dependency DAG...';
        return 'Topological invariant checks';

      case 'plan':
        if (incident?.playbook?.steps?.length) {
          return `${incident.playbook.steps.length} sequential recovery steps`;
        }
        if (state === 'running') return 'Calculating dependency order...';
        return 'Dependency-ordered planner';

      case 'execute':
        if (incident?.status === 'resolved') return 'Remediation applied & verified';
        if (incident?.status === 'awaiting_approval') return 'Awaiting operator sign-off';
        if (state === 'running') return 'Applying declarative patch...';
        return 'Guarded execution engine';

      case 'verify':
        if (incident?.status === 'resolved') return 'All services nominal • 0 loss';
        if (state === 'running') return 'Probing endpoint readiness...';
        return 'Health & readiness probes';

      default:
        return '';
    }
  };

  const STAGES = [
    { id: 'triage', label: '1. INGEST & DEDUP', icon: Filter },
    { id: 'diagnose', label: '2. TOPOLOGICAL RCA', icon: GitFork },
    { id: 'plan', label: '3. DAG PLANNER', icon: ShieldCheck },
    { id: 'execute', label: '4. GUARDED APPLY', icon: Play },
    { id: 'verify', label: '5. PROBE VERIFY', icon: CheckCircle2 }
  ];

  return (
    <div className="bg-white rounded-xl border border-stone-200 p-2 shadow-2xs font-mono">
      <div className="flex items-center justify-between gap-1 overflow-x-auto pb-0.5">
        {STAGES.map((stage, idx) => {
          const state = getStageState(stage.id);
          const Icon = stage.icon;
          const desc = getStageDesc(stage.id, state);

          let badgeStyles = 'border-stone-200 bg-stone-50/70 text-stone-400';
          let iconColor = 'text-stone-400';

          if (state === 'running') {
            badgeStyles = 'border-amber-400 bg-amber-50 text-amber-900 shadow-2xs';
            iconColor = 'text-amber-600';
          } else if (state === 'done') {
            badgeStyles = 'border-emerald-300 bg-emerald-50/80 text-emerald-900';
            iconColor = 'text-emerald-700';
          }

          return (
            <React.Fragment key={stage.id}>
              <div
                className={`flex-1 min-w-[130px] py-1.5 px-2.5 rounded-lg border ${badgeStyles} flex items-center gap-2 transition-all duration-200`}
              >
                <div className="shrink-0">
                  {state === 'running' ? (
                    <Loader2 size={13} className="animate-spin text-amber-600" />
                  ) : (
                    <Icon size={13} className={iconColor} />
                  )}
                </div>

                <div className="overflow-hidden flex-1">
                  <div className="text-[10px] font-extrabold tracking-wider leading-none flex items-center justify-between">
                    <span>{stage.label}</span>
                    {state === 'done' && (
                      <span className="text-[8px] text-emerald-700 font-bold bg-emerald-100/60 px-1 rounded">
                        DONE
                      </span>
                    )}
                    {state === 'running' && (
                      <span className="text-[8px] text-amber-700 font-bold bg-amber-100 px-1 rounded animate-pulse">
                        RUN
                      </span>
                    )}
                  </div>
                  <div className="text-[8px] text-stone-500 truncate mt-0.5 font-sans">
                    {desc}
                  </div>
                </div>
              </div>

              {idx < STAGES.length - 1 && (
                <div className="text-stone-300 shrink-0 px-0.5 select-none">
                  <ChevronRight size={13} />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
