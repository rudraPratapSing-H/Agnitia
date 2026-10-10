// frontend/src/components/extras/ReasoningPanel.tsx - Authentic Developer Terminal Emulator
import React, { useEffect, useRef, useState } from 'react';
import {
  Copy,
  Check,
  Terminal,
  Maximize2,
  Minimize2,
  Trash2,
  ArrowDown,
  Filter
} from 'lucide-react';
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
    text: 'Cluster telemetry active. Awaiting scenario injection [1..4]',
    status: 'pending',
    ts: '15:32:04'
  }
];

export default function ReasoningPanel({ steps, isSimulating }: ReasoningPanelProps) {
  const logBodyRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [activeFilter, setActiveFilter] = useState<'all' | 'errors' | 'cgroup'>('all');
  const [cleared, setCleared] = useState(false);

  const rawLogs = steps.length > 0 ? steps : DEFAULT_BASELINE_LOGS;

  useEffect(() => {
    if (cleared && steps.length > 0) {
      setCleared(false);
    }
  }, [steps, cleared]);

  const logsToDisplay = cleared
    ? []
    : rawLogs.filter((st) => {
        if (activeFilter === 'all') return true;
        const text = (st.text || (st as any).action || '').toLowerCase();
        if (activeFilter === 'errors') {
          return /exitcode|oomkilled|crashloop|fatal|panic|error|fail|kill/i.test(text);
        }
        if (activeFilter === 'cgroup') {
          return /cgroup|memory|limit|scale|patch|probe/i.test(text);
        }
        return true;
      });

  useEffect(() => {
    if (!autoScroll) return;
    const el = logBodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [steps, autoScroll, logsToDisplay]);

  const lastLog = rawLogs[rawLogs.length - 1];
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

  const handleClear = () => {
    setCleared(true);
  };

  const handleReset = () => {
    setCleared(false);
  };

  return (
    <div
      className={`rounded-xl overflow-hidden border border-[#30363d] font-mono bg-[#0d1117] flex flex-col shadow-2xl transition-all duration-200 shrink-0 ${
        isExpanded ? 'h-[440px] min-h-[400px]' : 'h-[250px] min-h-[230px]'
      }`}
    >
      {/* Top Terminal macOS / Linux Window Header */}
      <div className="bg-[#161b22] px-3 py-2 border-b border-[#30363d] flex items-center justify-between select-none">
        {/* Left: Window Traffic Light Dots + Title */}
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5">
            <span
              className="w-3 h-3 rounded-full bg-[#ff5f56] border border-[#e0443e]/60 hover:opacity-80 transition-opacity cursor-pointer inline-block"
              title="Close Session"
              onClick={handleClear}
            />
            <span
              className="w-3 h-3 rounded-full bg-[#ffbd2e] border border-[#dea123]/60 hover:opacity-80 transition-opacity cursor-pointer inline-block"
              title="Minimize View"
              onClick={() => setIsExpanded(false)}
            />
            <span
              className="w-3 h-3 rounded-full bg-[#27c93f] border border-[#1aab29]/60 hover:opacity-80 transition-opacity cursor-pointer inline-block"
              title="Expand View"
              onClick={() => setIsExpanded(!isExpanded)}
            />
          </div>

          <div className="flex items-center gap-1.5 pl-1.5 border-l border-[#30363d]">
            <Terminal size={13} className="text-[#38bdf8]" />
            <span className="text-[11px] font-semibold text-[#e6edf3] tracking-tight">
              sre@agnitia: <span className="text-[#8b949e]">~/logs/pods</span>
            </span>
            <span className="text-[9px] px-1.5 py-0.2 rounded bg-[#21262d] text-[#8b949e] border border-[#30363d] hidden sm:inline-block">
              bash (tty0)
            </span>
          </div>
        </div>

        {/* Right: Quick Terminal Actions */}
        <div className="flex items-center gap-1.5 text-[10px]">
          {/* Live Status Pill */}
          {isSimulating ? (
            <span className="flex items-center gap-1 text-[9.5px] text-[#3fb950] bg-[#238636]/15 border border-[#238636]/30 px-2 py-0.5 rounded font-bold">
              <span className="w-1.5 h-1.5 rounded-full bg-[#3fb950] animate-pulse" />
              STREAMING
            </span>
          ) : (
            <span className="flex items-center gap-1 text-[9.5px] text-[#8b949e] bg-[#21262d] border border-[#30363d] px-2 py-0.5 rounded">
              <span className="w-1.5 h-1.5 rounded-full bg-[#3fb950]" />
              LIVE
            </span>
          )}

          {/* Auto-Scroll Toggle */}
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`px-1.5 py-0.5 rounded border transition-colors flex items-center gap-1 cursor-pointer ${
              autoScroll
                ? 'bg-[#1f2937] text-[#38bdf8] border-[#38bdf8]/40'
                : 'bg-[#21262d] text-[#8b949e] border-[#30363d] hover:text-[#e6edf3]'
            }`}
            title={autoScroll ? 'Auto-scroll enabled' : 'Auto-scroll paused'}
          >
            <ArrowDown size={10} className={autoScroll ? 'animate-bounce' : ''} />
            <span className="text-[9px] font-bold">{autoScroll ? 'SCROLL' : 'PAUSED'}</span>
          </button>

          {/* Copy Buffer */}
          <button
            onClick={handleCopyLogs}
            className="text-[#8b949e] hover:text-[#e6edf3] px-2 py-0.5 rounded bg-[#21262d] hover:bg-[#30363d] transition-colors flex items-center gap-1 cursor-pointer border border-[#30363d]"
            title="Copy terminal buffer"
          >
            {copied ? <Check size={10} className="text-[#3fb950]" /> : <Copy size={10} />}
            <span>{copied ? 'COPIED' : 'COPY'}</span>
          </button>

          {/* Clear Buffer */}
          <button
            onClick={cleared ? handleReset : handleClear}
            className="text-[#8b949e] hover:text-[#e6edf3] p-1 rounded bg-[#21262d] hover:bg-[#30363d] transition-colors cursor-pointer border border-[#30363d]"
            title={cleared ? 'Restore terminal buffer' : 'Clear terminal buffer'}
          >
            <Trash2 size={11} className={cleared ? 'text-[#e3b341]' : ''} />
          </button>

          {/* Expand / Minimize Window */}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-[#8b949e] hover:text-[#e6edf3] p-1 rounded bg-[#21262d] hover:bg-[#30363d] transition-colors cursor-pointer border border-[#30363d] hidden sm:flex"
            title={isExpanded ? 'Collapse terminal' : 'Expand terminal'}
          >
            {isExpanded ? <Minimize2 size={11} /> : <Maximize2 size={11} />}
          </button>
        </div>
      </div>

      {/* Subheader: Filter Tabs Bar */}
      <div className="bg-[#0d1117] px-3 py-1 border-b border-[#21262d] flex items-center justify-between text-[10px]">
        <div className="flex items-center gap-1 text-[#8b949e]">
          <Filter size={10} className="text-[#8b949e]" />
          <span className="uppercase text-[9px] tracking-wider mr-1 text-[#8b949e]">FILTER:</span>
          {(['all', 'errors', 'cgroup'] as const).map((filter) => (
            <button
              key={filter}
              onClick={() => setActiveFilter(filter)}
              className={`px-2 py-0.2 rounded font-bold uppercase text-[9px] transition-colors cursor-pointer ${
                activeFilter === filter
                  ? 'bg-[#38bdf8]/15 text-[#38bdf8] border border-[#38bdf8]/40'
                  : 'text-[#8b949e] hover:text-[#e6edf3] hover:bg-[#161b22]'
              }`}
            >
              {filter}
            </button>
          ))}
        </div>

        <div className="text-[9px] text-[#8b949e] flex items-center gap-2">
          <span>LINES: <strong className="text-[#e6edf3]">{logsToDisplay.length}</strong></span>
          <span className="hidden sm:inline text-[#30363d]">|</span>
          <span className="hidden sm:inline">BUFFER: 64KB</span>
        </div>
      </div>

      {/* Terminal Screen / Output Body */}
      <div
        ref={logBodyRef}
        className="flex-1 p-2.5 overflow-y-auto space-y-1 text-[11.5px] leading-relaxed custom-scrollbar bg-[#0d1117] text-[#c9d1d9] selection:bg-[#38bdf8]/30 selection:text-[#ffffff]"
      >
        {logsToDisplay.length === 0 ? (
          <div className="py-6 text-center text-[#8b949e] text-[11px]">
            <span>Terminal buffer cleared. Press </span>
            <button
              onClick={handleReset}
              className="text-[#38bdf8] underline hover:text-[#7dd3fc] cursor-pointer font-bold"
            >
              Restore Buffer
            </button>
            <span> or wait for next telemetry event.</span>
          </div>
        ) : (
          logsToDisplay.map((st, idx) => {
            const pod = derivePodName(st);
            const timestamp = st.ts || `15:32:${String(idx * 2 + 10).padStart(2, '0')}`;
            const text = st.text || (st as any).action || '';

            const isError = /exitcode|oomkilled|crashloop|fatal|panic|error|fail|killed/i.test(text);
            const isWarn = /patch|rollout|rollback|scale|throttl|gradient|restart/i.test(text);
            const isSuccess = /200 ok|healthy|restored|validated|nominal/i.test(text);

            return (
              <div
                key={st.id || idx}
                className={`group flex items-start gap-2 py-0.5 px-1 rounded transition-colors ${
                  isError
                    ? 'bg-[#f85149]/10 border-l-2 border-[#f85149] text-[#ff7b72]'
                    : isWarn
                    ? 'bg-[#d29922]/10 border-l-2 border-[#d29922] text-[#e3b341]'
                    : isSuccess
                    ? 'hover:bg-[#161b22] border-l-2 border-[#238636]/40'
                    : 'hover:bg-[#161b22] border-l-2 border-transparent'
                }`}
              >
                {/* Gutter Line Number */}
                <span className="text-[#484f58] w-6 shrink-0 text-right select-none text-[10px] pt-0.5 font-mono">
                  {String(idx + 1).padStart(2, '0')}
                </span>

                {/* Log Line Content */}
                <div className="flex-1 break-words font-mono min-w-0">
                  {/* Prompt: user@pod:~$ */}
                  <span className="text-[#38bdf8] font-bold select-none text-[11px]">
                    sre@
                  </span>
                  <span className="text-[#34d399] font-bold select-none text-[11px]">
                    {pod.replace('pod/', '')}
                  </span>
                  <span className="text-[#8b949e] font-semibold select-none text-[11px]">
                    :~$&nbsp;
                  </span>

                  {/* Timestamp */}
                  <span className="text-[#6e7681] select-none text-[10px] mr-1.5">
                    [{timestamp}]
                  </span>

                  {/* Severity Badge */}
                  {isError && (
                    <span className="inline-block text-[9px] font-bold bg-[#f85149]/20 text-[#ff7b72] border border-[#f85149]/40 px-1 py-0 rounded mr-1.5 select-none align-middle">
                      FATAL
                    </span>
                  )}
                  {isWarn && (
                    <span className="inline-block text-[9px] font-bold bg-[#d29922]/20 text-[#e3b341] border border-[#d29922]/40 px-1 py-0 rounded mr-1.5 select-none align-middle">
                      WARN
                    </span>
                  )}
                  {isSuccess && (
                    <span className="inline-block text-[9px] font-bold bg-[#238636]/20 text-[#3fb950] border border-[#238636]/40 px-1 py-0 rounded mr-1.5 select-none align-middle">
                      OK
                    </span>
                  )}

                  {/* Message Body */}
                  <span
                    className={
                      isError
                        ? 'text-[#ff7b72] font-semibold'
                        : isWarn
                        ? 'text-[#f2cc60]'
                        : isSuccess
                        ? 'text-[#7ee787]'
                        : 'text-[#e6edf3]'
                    }
                  >
                    {text}
                  </span>
                </div>
              </div>
            );
          })
        )}

        {/* Live Blinking Shell Prompt at the bottom */}
        <div className="pt-1.5 flex items-center font-mono text-[11.5px] select-none px-1 text-[#8b949e]">
          <span className="text-[#38bdf8] font-bold">sre@</span>
          <span className="text-[#34d399] font-bold">{activePromptPod.replace('pod/', '')}</span>
          <span className="text-[#8b949e] font-semibold">:~$&nbsp;</span>
          <span className="text-[#79c0ff]">kubectl logs -f --tail=1</span>
          {/* Phosphor Green Terminal Cursor */}
          <span className="inline-block w-2 h-3.5 bg-[#3fb950] ml-1.5 animate-pulse shadow-[0_0_8px_rgba(63,185,80,0.8)] align-middle" />
        </div>
      </div>

      {/* Terminal Powerline / tmux Footer Status Bar */}
      <div className="bg-[#161b22] px-3 py-1 border-t border-[#30363d] flex items-center justify-between text-[9.5px] text-[#8b949e] font-mono select-none">
        <div className="flex items-center gap-2">
          <span className="bg-[#238636] text-[#ffffff] font-bold px-1.5 py-0.2 rounded text-[8.5px] uppercase">
            NORMAL
          </span>
          <span className="text-[#8b949e]">UTF-8</span>
          <span className="text-[#30363d]">|</span>
          <span className="text-[#e6edf3]">
            TARGET: <strong className="text-[#34d399]">{activePromptPod}</strong>
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[#8b949e]">zsh 5.9</span>
          <span className="text-[#30363d]">|</span>
          <span className="text-[#38bdf8] font-semibold">
            {isSimulating ? 'STREAM ACTIVE' : 'PIPE IDLE'}
          </span>
        </div>
      </div>
    </div>
  );
}
