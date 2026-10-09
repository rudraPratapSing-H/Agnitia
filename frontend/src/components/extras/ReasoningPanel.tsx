// D:\CoffeeOverflow\Agnitia\frontend\src\components\extras\ReasoningPanel.tsx - SRE Execution Trace
import React, { useEffect, useRef } from 'react';
import { Terminal, Activity, FileText } from 'lucide-react';
import { AgentStep } from '../../types';

interface ReasoningPanelProps {
  steps: AgentStep[];
  isSimulating: boolean;
}

export default function ReasoningPanel({ steps, isSimulating }: ReasoningPanelProps) {
  const terminalEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [steps]);

  return (
    <div className="bg-white rounded-xl border border-stone-200 shadow-2xs flex flex-col h-[200px] font-mono overflow-hidden">
      <div className="bg-stone-100/90 px-3 py-1.5 border-b border-stone-200 flex items-center justify-between text-xs select-none">
        <div className="flex items-center gap-1.5 text-stone-800 font-bold text-[11px]">
          <Terminal size={13} className="text-stone-600" />
          <span>ORCHESTRATOR EXECUTION TRACE</span>
        </div>

        <div className="flex items-center gap-2 text-[10px] text-stone-500">
          {isSimulating ? (
            <span className="flex items-center gap-1 text-emerald-700 font-semibold">
              <Activity size={11} className="animate-pulse" />
              TRACE ACTIVE
            </span>
          ) : (
            <span className="text-stone-500 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
              READY
            </span>
          )}
        </div>
      </div>

      <div className="flex-1 p-2.5 overflow-y-auto space-y-1.5 text-[11px] leading-relaxed custom-scrollbar bg-stone-50/50">
        {steps.length === 0 ? (
          <div className="text-stone-400 italic py-6 text-center flex flex-col items-center justify-center gap-1.5">
            <FileText size={15} className="text-stone-300" />
            <span>Telemetry listeners active. Press [1..4] to inject a scenario...</span>
          </div>
        ) : (
          steps.map((st, idx) => {
            const agentTag = (st.agent || 'SYSTEM').toUpperCase();

            let tagColor = 'text-stone-700 border-stone-300 bg-stone-100';
            if (st.agent === 'triage') tagColor = 'text-amber-800 border-amber-300 bg-amber-50';
            if (st.agent === 'diagnose') tagColor = 'text-sky-800 border-sky-300 bg-sky-50';
            if (st.agent === 'plan') tagColor = 'text-purple-800 border-purple-300 bg-purple-50';
            if (st.agent === 'execute') tagColor = 'text-rose-800 border-rose-300 bg-rose-50';
            if (st.agent === 'verify') tagColor = 'text-emerald-800 border-emerald-300 bg-emerald-50';

            return (
              <div key={st.id || idx} className="flex items-start gap-1.5 animate-fadeIn">
                <span className="text-stone-400 select-none text-[10px] pt-0.5">
                  &gt;
                </span>
                <span
                  className={`text-[9px] px-1.5 py-0.2 rounded border font-bold uppercase shrink-0 ${tagColor}`}
                >
                  {agentTag}
                </span>
                <span className="text-stone-800 font-mono text-[11px] leading-tight break-words">
                  {st.text || (st as any).action}
                </span>
              </div>
            );
          })
        )}
        <div ref={terminalEndRef} />
      </div>
    </div>
  );
}
