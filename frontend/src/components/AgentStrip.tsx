// D:\CoffeeOverflow\Agnitia\frontend\src\components\AgentStrip.tsx
import React from 'react';
import { Search, Stethoscope, Wrench, Play, CheckCheck, Loader2 } from 'lucide-react';
import { AgentStep, Incident } from '../types';

const AGENT_STAGES = [
  { id: 'triage', label: 'TRIAGE', desc: 'Alert Filtering', icon: Search },
  { id: 'diagnose', label: 'DIAGNOSE', desc: 'RCA & Evidence', icon: Stethoscope },
  { id: 'plan', label: 'PLAN', desc: 'Topological Sort', icon: Wrench },
  { id: 'execute', label: 'EXECUTE', desc: 'Remediation', icon: Play },
  { id: 'verify', label: 'VERIFY', desc: 'Health Probes', icon: CheckCheck }
];

interface AgentStripProps {
  agentSteps: AgentStep[];
  incident: Incident | null;
}

export default function AgentStrip({ agentSteps, incident }: AgentStripProps) {
  const getStageState = (stageId: string) => {
    const stepsForStage = agentSteps.filter(s => s.agent === stageId);
    if (stepsForStage.length === 0) {
      if (stageId === 'triage' && incident) return 'done';
      return 'idle';
    }
    const latest = stepsForStage[stepsForStage.length - 1];
    return latest.status || 'running';
  };

  return (
    <div className="bg-white rounded-xl border border-stone-200 p-2 shadow-xs">
      <div className="flex items-center justify-between gap-1 overflow-x-auto pb-0.5">
        {AGENT_STAGES.map((stage, idx) => {
          const state = getStageState(stage.id);
          const Icon = stage.icon;

          let badgeStyles = 'border-stone-200 bg-stone-50/80 text-stone-400';
          let iconColor = 'text-stone-400';

          if (state === 'running') {
            badgeStyles = 'border-amber-300 bg-amber-50 text-amber-800';
            iconColor = 'text-amber-600';
          } else if (state === 'done') {
            badgeStyles = 'border-emerald-200 bg-emerald-50 text-emerald-800';
            iconColor = 'text-emerald-600';
          }

          return (
            <React.Fragment key={stage.id}>
              <div
                className={`flex-1 min-w-[85px] py-1.5 px-2 rounded-lg border ${badgeStyles} flex items-center gap-2 transition-all duration-200 font-mono`}
              >
                <div>
                  {state === 'running' ? (
                    <Loader2 size={13} className="animate-spin text-amber-600" />
                  ) : (
                    <Icon size={13} className={iconColor} />
                  )}
                </div>

                <div className="overflow-hidden">
                  <div className="text-[10px] font-bold tracking-wider leading-none flex items-center gap-1">
                    {stage.label}
                    {state === 'done' && <span className="text-[8px] text-emerald-600 font-bold">✓</span>}
                  </div>
                  <div className="text-[8px] text-stone-500 truncate mt-0.5">
                    {stage.desc}
                  </div>
                </div>
              </div>

              {idx < AGENT_STAGES.length - 1 && (
                <div className="text-stone-300 text-xs px-0.5 select-none">→</div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
