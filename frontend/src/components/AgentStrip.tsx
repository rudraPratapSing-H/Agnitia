// frontend/src/components/AgentStrip.jsx - 5-Stage Agent Pipeline Status Strip
import React from 'react';
import { Search, Stethoscope, Wrench, Play, CheckCheck, Loader2 } from 'lucide-react';

const AGENT_STAGES = [
  { id: 'triage', label: 'TRIAGE', desc: 'Alert Filtering', icon: Search },
  { id: 'diagnose', label: 'DIAGNOSE', desc: 'RCA & Evidence', icon: Stethoscope },
  { id: 'plan', label: 'PLAN', desc: 'Topological Sort', icon: Wrench },
  { id: 'execute', label: 'EXECUTE', desc: 'Remediation', icon: Play },
  { id: 'verify', label: 'VERIFY', desc: 'Health Probes', icon: CheckCheck }
];

export default function AgentStrip({ agentSteps, incident }) {
  // Determine the status of each stage from agentSteps and incident status
  const getStageState = (stageId) => {
    const stepsForStage = agentSteps.filter(s => s.agent === stageId);
    if (stepsForStage.length === 0) {
      if (stageId === 'triage' && incident) return 'done';
      return 'idle';
    }
    const latest = stepsForStage[stepsForStage.length - 1];
    return latest.status || 'running';
  };

  return (
    <div className="bg-zinc-900/90 rounded-xl border border-zinc-800 p-2.5 backdrop-blur-md shadow-lg">
      <div className="flex items-center justify-between gap-1 overflow-x-auto pb-0.5">
        {AGENT_STAGES.map((stage, idx) => {
          const state = getStageState(stage.id);
          const Icon = stage.icon;

          let badgeStyles = 'border-zinc-800 bg-zinc-950/60 text-zinc-500';
          let iconColor = 'text-zinc-600';

          if (state === 'running') {
            badgeStyles = 'border-amber-500/80 bg-amber-950/50 text-amber-300 shadow-[0_0_12px_rgba(245,158,11,0.25)]';
            iconColor = 'text-amber-400';
          } else if (state === 'done') {
            badgeStyles = 'border-emerald-600/60 bg-emerald-950/40 text-emerald-300';
            iconColor = 'text-emerald-400';
          }

          return (
            <React.Fragment key={stage.id}>
              <div
                className={`flex-1 min-w-[90px] py-1.5 px-2 rounded-lg border ${badgeStyles} flex items-center gap-2 transition-all duration-300 font-mono`}
              >
                <div className="relative">
                  {state === 'running' ? (
                    <Loader2 size={13} className="animate-spin text-amber-400" />
                  ) : (
                    <Icon size={13} className={iconColor} />
                  )}
                </div>

                <div className="overflow-hidden">
                  <div className="text-[10px] font-bold tracking-wider leading-none flex items-center gap-1">
                    {stage.label}
                    {state === 'done' && <span className="text-[8px] text-emerald-400">✓</span>}
                  </div>
                  <div className="text-[8px] text-zinc-500 truncate mt-0.5">
                    {stage.desc}
                  </div>
                </div>
              </div>

              {idx < AGENT_STAGES.length - 1 && (
                <div className="text-zinc-700 text-xs px-0.5">→</div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
