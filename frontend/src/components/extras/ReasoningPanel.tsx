// frontend/src/components/extras/ReasoningPanel.jsx - Terminal Auto-Scroll Investigation Feed
import React, { useEffect, useRef } from 'react';
import { Terminal, ShieldCheck, Sparkles, Activity } from 'lucide-react';

export default function ReasoningPanel({ steps, isSimulating }) {
  const terminalEndRef = useRef(null);

  // Auto-scroll to bottom whenever new reasoning steps arrive
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [steps]);

  return (
    <div className="bg-zinc-950 rounded-xl border border-zinc-800 shadow-2xl flex flex-col h-[230px] font-mono overflow-hidden">
      {/* Terminal Bar */}
      <div className="bg-zinc-900/90 px-3 py-1.5 border-b border-zinc-800 flex items-center justify-between text-xs select-none">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500/80 inline-block" />
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80 inline-block" />
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80 inline-block" />
          </div>
          <div className="flex items-center gap-1.5 text-zinc-400 font-bold ml-1 text-[11px]">
            <Terminal size={13} className="text-indigo-400" />
            <span>AI INVESTIGATION LOG</span>
          </div>
        </div>

        <div className="flex items-center gap-2 text-[10px] text-zinc-500">
          {isSimulating ? (
            <span className="flex items-center gap-1 text-emerald-400 animate-pulse font-semibold">
              <Activity size={12} />
              REASONING ACTIVE
            </span>
          ) : (
            <span className="text-zinc-600">IDLE · READY</span>
          )}
        </div>
      </div>

      {/* Terminal Output Stream */}
      <div className="flex-1 p-3 overflow-y-auto space-y-2 text-[11px] leading-relaxed custom-scrollbar bg-black/60">
        {steps.length === 0 ? (
          <div className="text-zinc-600 italic py-8 text-center flex flex-col items-center justify-center gap-2">
            <Sparkles size={16} className="text-zinc-700" />
            <span>Telemetry listeners active. Inject a fault below to initiate AI SRE investigation...</span>
          </div>
        ) : (
          steps.map((st, idx) => {
            const agentTag = (st.agent || 'SYSTEM').toUpperCase();
            
            let tagColor = 'text-indigo-400 border-indigo-800/80 bg-indigo-950/40';
            if (st.agent === 'triage') tagColor = 'text-amber-400 border-amber-800/80 bg-amber-950/40';
            if (st.agent === 'diagnose') tagColor = 'text-cyan-400 border-cyan-800/80 bg-cyan-950/40';
            if (st.agent === 'plan') tagColor = 'text-purple-400 border-purple-800/80 bg-purple-950/40';
            if (st.agent === 'execute') tagColor = 'text-rose-400 border-rose-800/80 bg-rose-950/40';
            if (st.agent === 'verify') tagColor = 'text-emerald-400 border-emerald-800/80 bg-emerald-950/40';

            return (
              <div key={st.id || idx} className="flex items-start gap-2 animate-fadeIn">
                <span className="text-zinc-600 select-none text-[10px] pt-0.5">
                  &gt;
                </span>
                <span
                  className={`text-[9px] uppercase px-1.5 py-0.2 rounded border font-semibold tracking-wider shrink-0 ${tagColor}`}
                >
                  [{agentTag}]
                </span>
                <span className="text-zinc-200">
                  {st.text}
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
