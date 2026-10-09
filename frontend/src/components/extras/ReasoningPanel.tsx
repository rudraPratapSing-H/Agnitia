// frontend/src/components/extras/ReasoningPanel.tsx - Clean CMD Pod Terminal Log Stream
import React, { useEffect, useRef, useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { AgentStep } from '../../types';

interface ReasoningPanelProps {
  steps: AgentStep[];
  isSimulating: boolean;
}

function derivePodName(step: AgentStep): string {
  const text = (step.text || (step as any).action || '').toLowerCase();
  const agent = (step.agent || '').toLowerCase();

  // Target Pods
  if (text.includes('postgres')) return 'pod/postgres-0';
  if (text.includes('aurora') || text.includes('aurora-orders-db')) return 'pod/aurora-orders-db';
  if (text.includes('payment')) return 'pod/payment-service';
  if (text.includes('auth') || text.includes('cognito')) return 'pod/auth-service';
  if (text.includes('api-gateway') || text.includes('gateway')) return 'pod/api-gateway';
  if (text.includes('redis')) return 'pod/redis-cache';
  if (text.includes('dynamo')) return 'pod/dynamodb';
  if (text.includes('kafka')) return 'pod/kafka-broker';
  if (text.includes('shipping') || text.includes('logistics')) return 'pod/shipping-logistics';
  if (text.includes('inventory')) return 'pod/inventory-manager';
  if (text.includes('order')) return 'pod/order-orchestrator';

  // Orchestrator Agents
  if (agent === 'triage') return 'pod/triage-agent';
  if (agent === 'diagnose') return 'pod/diagnose-agent';
  if (agent === 'plan') return 'pod/planner-agent';
  if (agent === 'execute') return 'pod/remediator';
  if (agent === 'verify') return 'pod/prober';

  return 'pod/system';
}

const DEFAULT_BASELINE_LOGS: AgentStep[] = [
  {
    agent: 'verify',
    text: 'Synthetic healthz probe 200 OK across pods',
    status: 'done',
    ts: '15:32:00'
  },
  {
    agent: 'triage',
    text: 'cgroup memory & CPU limits within nominal range (<45%)',
    status: 'done',
    ts: '15:32:01'
  },
  {
    agent: 'diagnose',
    text: 'Zero packet drops, mesh latency median 1.2ms',
    status: 'done',
    ts: '15:32:02'
  },
  {
    agent: 'plan',
    text: 'Cluster telemetry active. Ready for scenario injection [1..4]',
    status: 'pending',
    ts: '15:32:04'
  }
];

export default function ReasoningPanel({ steps, isSimulating }: ReasoningPanelProps) {
  const terminalEndRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);

  const logsToDisplay = steps.length > 0 ? steps : DEFAULT_BASELINE_LOGS;

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [steps]);

  const lastLog = logsToDisplay[logsToDisplay.length - 1];
  const activePromptPod = lastLog ? derivePodName(lastLog) : 'pod/system';

  const handleCopyLogs = () => {
    const text = logsToDisplay
      .map((st, i) => {
        const pod = derivePodName(st);
        const ts = st.ts || `15:32:${String(i * 2 + 10).padStart(2, '0')}`;
        return `${pod}> [${ts}] ${st.text || (st as any).action}`;
      })
      .join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="rounded-xl overflow-hidden border border-stone-800 shadow-md font-mono bg-[#0a0a0a] flex flex-col h-[240px] min-h-[220px] shrink-0">
      {/* Simple CMD Header Bar */}
      <div className="bg-[#141414] px-3 py-1.5 border-b border-[#252525] flex items-center justify-between select-none">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-bold text-stone-300 flex items-center gap-1.5">
            <span className="text-emerald-400 font-black">&gt;_</span>
            POD LOGS (CMD)
          </span>
          {isSimulating ? (
            <span className="flex items-center gap-1 text-[9.5px] text-emerald-400 font-bold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              STREAMING
            </span>
          ) : (
            <span className="text-[9.5px] text-stone-500">• LIVE</span>
          )}
        </div>

        {/* Copy Button */}
        <button
          onClick={handleCopyLogs}
          className="text-stone-400 hover:text-white px-2 py-0.5 rounded text-[10.5px] hover:bg-stone-800 transition-colors flex items-center gap-1 cursor-pointer border border-stone-700/60"
          title="Copy log lines"
        >
          {copied ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
          <span>{copied ? 'COPIED' : 'COPY'}</span>
        </button>
      </div>

      {/* Terminal Body: Black Background, Increased Font Size, Pod-Only Paths */}
      <div className="flex-1 p-3 overflow-y-auto space-y-1.5 text-[12px] leading-relaxed custom-scrollbar bg-[#0a0a0a] text-stone-200">
        {logsToDisplay.map((st, idx) => {
          const pod = derivePodName(st);
          const timestamp = st.ts || `15:32:${String(idx * 2 + 10).padStart(2, '0')}`;
          const text = st.text || (st as any).action || '';

          const isError = /exitcode|oomkilled|crashloop|fatal|panic/i.test(text);
          const isWarn = /patch|rollout|rollback|scale|throttl|gradient/i.test(text);
          const isSuccess = /200 ok|healthy|restored|validated/i.test(text);

          let messageClass = 'text-stone-200';
          if (isError) messageClass = 'text-rose-400 font-semibold';
          else if (isWarn) messageClass = 'text-amber-300';
          else if (isSuccess) messageClass = 'text-emerald-400 font-semibold';

          return (
            <div key={st.id || idx} className="leading-normal animate-fadeIn font-mono break-words">
              {/* Pod Prompt Prefix */}
              <span className="text-emerald-400 font-bold select-none">{pod}&gt; </span>
              {/* Timestamp */}
              <span className="text-stone-500 select-none text-[11px]">[{timestamp}] </span>
              {/* Log Message */}
              <span className={messageClass}>{text}</span>
            </div>
          );
        })}

        {/* Terminal Blinking Prompt */}
        <div className="pt-1 font-mono text-[12px] flex items-center select-none">
          <span className="text-emerald-400 font-bold">{activePromptPod}&gt;</span>
          <span className="inline-block w-2 h-4 bg-stone-200 ml-1.5 animate-pulse" />
        </div>

        <div ref={terminalEndRef} />
      </div>
    </div>
  );
}
