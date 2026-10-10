// frontend/src/components/extras/ReasoningPanel.tsx - Minimalist Terminal Log Viewer
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
  if (text.includes('postgres')) return 'postgres-0';
  if (text.includes('aurora') || text.includes('aurora-orders-db')) return 'aurora-orders-db';
  if (text.includes('payment')) return 'payment-service';
  if (text.includes('auth') || text.includes('cognito')) return 'auth-service';
  if (text.includes('api-gateway') || text.includes('gateway')) return 'api-gateway';
  if (text.includes('redis')) return 'redis-cache';
  if (text.includes('dynamo')) return 'dynamodb';
  if (text.includes('kafka')) return 'kafka-broker';
  if (text.includes('shipping') || text.includes('logistics')) return 'shipping-logistics';
  if (text.includes('inventory')) return 'inventory-manager';
  if (text.includes('order')) return 'order-orchestrator';

  // Orchestrator Agents
  if (agent === 'triage') return 'triage';
  if (agent === 'diagnose') return 'diagnose';
  if (agent === 'plan') return 'planner';
  if (agent === 'execute') return 'remediator';
  if (agent === 'verify') return 'prober';

  return 'system';
}

const DEFAULT_BASELINE_LOGS: AgentStep[] = [
  {
    agent: 'verify',
    text: 'Synthetic healthz probe 200 OK across cluster mesh',
    status: 'done',
    ts: '15:32:00'
  },
  {
    agent: 'triage',
    text: 'cgroup memory & CPU limits nominal (<45% allocation)',
    status: 'done',
    ts: '15:32:01'
  },
  {
    agent: 'diagnose',
    text: 'Zero packet drops, ingress mesh latency median 1.2ms',
    status: 'done',
    ts: '15:32:02'
  },
  {
    agent: 'plan',
    text: 'Cluster telemetry active. Ready for scenario injection',
    status: 'pending',
    ts: '15:32:04'
  }
];

export default function ReasoningPanel({ steps, isSimulating }: ReasoningPanelProps) {
  const logBodyRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);

  const logsToDisplay = steps.length > 0 ? steps : DEFAULT_BASELINE_LOGS;

  useEffect(() => {
    const el = logBodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [steps]);

  const lastLog = logsToDisplay[logsToDisplay.length - 1];
  const activePod = lastLog ? derivePodName(lastLog) : 'mesh';

  const handleCopyLogs = () => {
    const text = logsToDisplay
      .map((st, i) => {
        const pod = derivePodName(st);
        const ts = st.ts || `15:32:${String(i * 2 + 10).padStart(2, '0')}`;
        return `[${ts}] ${pod} > ${st.text || (st as any).action}`;
      })
      .join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="rounded-xl overflow-hidden border border-[#30363d] font-mono bg-[#0d1117] flex flex-col h-[240px] min-h-[220px] shadow-lg shrink-0">
      {/* Minimalist Terminal Window Header */}
      <div className="bg-[#161b22] px-3.5 py-2 border-b border-[#30363d] flex items-center justify-between select-none">
        {/* Left: 3 macOS dots + terminal title */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#ff5f56]" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#ffbd2e]" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#27c93f]" />
          </div>
          <span className="text-[11px] font-mono font-medium text-[#8b949e] tracking-tight">
            terminal <span className="text-[#30363d]">—</span> <span className="text-[#c9d1d9]">pod logs</span>
          </span>
        </div>

        {/* Right: Live indicator + Copy */}
        <div className="flex items-center gap-2">
          {isSimulating ? (
            <span className="flex items-center gap-1.5 text-[10px] text-[#3fb950] font-mono font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-[#3fb950] animate-pulse" />
              STREAMING
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-[10px] text-[#8b949e] font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-[#3fb950]" />
              LIVE
            </span>
          )}

          <button
            onClick={handleCopyLogs}
            className="text-[#8b949e] hover:text-[#e6edf3] px-2 py-0.5 rounded text-[10px] bg-[#21262d] hover:bg-[#30363d] transition-colors flex items-center gap-1 border border-[#30363d] cursor-pointer"
            title="Copy logs"
          >
            {copied ? <Check size={10} className="text-[#3fb950]" /> : <Copy size={10} />}
            <span>{copied ? 'COPIED' : 'COPY'}</span>
          </button>
        </div>
      </div>

      {/* Terminal Body */}
      <div
        ref={logBodyRef}
        className="flex-1 p-3 overflow-y-auto space-y-1 text-[11.5px] leading-relaxed custom-scrollbar bg-[#0d1117] text-[#c9d1d9]"
      >
        {logsToDisplay.map((st, idx) => {
          const pod = derivePodName(st);
          const timestamp = st.ts || `15:32:${String(idx * 2 + 10).padStart(2, '0')}`;
          const text = st.text || (st as any).action || '';

          const isError = /exitcode|oomkilled|crashloop|fatal|panic|error|fail|killed/i.test(text);
          const isWarn = /patch|rollout|rollback|scale|throttl|gradient/i.test(text);
          const isSuccess = /200 ok|healthy|restored|validated|nominal/i.test(text);

          let textClass = 'text-[#e6edf3]';
          if (isError) textClass = 'text-[#ff7b72] font-semibold';
          else if (isWarn) textClass = 'text-[#f2cc60]';
          else if (isSuccess) textClass = 'text-[#7ee787]';

          return (
            <div key={st.id || idx} className="flex items-start gap-1.5 font-mono">
              {/* Timestamp */}
              <span className="text-[#6e7681] text-[10px] select-none shrink-0 pt-0.5">
                [{timestamp}]
              </span>

              {/* Pod Prompt */}
              <span className="text-[#34d399] font-semibold select-none shrink-0">
                {pod}&gt;
              </span>

              {/* Log Message */}
              <span className={`break-words ${textClass}`}>
                {text}
              </span>
            </div>
          );
        })}

        {/* Minimal Terminal Prompt with Blinking Cursor */}
        <div className="pt-1 flex items-center font-mono text-[11.5px] select-none text-[#8b949e]">
          <span className="text-[#34d399] font-semibold">{activePod}&gt;</span>
          <span className="inline-block w-2 h-3.5 bg-[#3fb950] ml-1.5 animate-pulse" />
        </div>
      </div>
    </div>
  );
}
