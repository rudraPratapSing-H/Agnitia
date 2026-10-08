import React, { useState, useEffect, useRef } from 'react';

export type AgentType = 'triage' | 'diagnose' | 'plan' | 'execute' | 'verify';
export type StepStatus = 'running' | 'done' | 'failed';

export interface AgentStep {
  agent: AgentType;
  text: string;
  status: StepStatus;
  ts?: string;
}

export interface ReasoningPanelProps {
  steps: AgentStep[];
  className?: string;
}

const AGENT_COLORS: Record<AgentType, { tag: string; border: string; bg: string; text: string }> = {
  triage: {
    tag: '[TRIAGE]',
    border: 'border-purple-600/50',
    bg: 'bg-purple-950/40',
    text: 'text-purple-400',
  },
  diagnose: {
    tag: '[DIAGNOSE]',
    border: 'border-amber-600/50',
    bg: 'bg-amber-950/40',
    text: 'text-amber-400',
  },
  plan: {
    tag: '[PLAN]',
    border: 'border-cyan-600/50',
    bg: 'bg-cyan-950/40',
    text: 'text-cyan-400',
  },
  execute: {
    tag: '[EXECUTE]',
    border: 'border-indigo-600/50',
    bg: 'bg-indigo-950/40',
    text: 'text-indigo-400',
  },
  verify: {
    tag: '[VERIFY]',
    border: 'border-emerald-600/50',
    bg: 'bg-emerald-950/40',
    text: 'text-emerald-400',
  },
};

const formatTimestamp = (ts?: string): string => {
  if (!ts) {
    const now = new Date();
    return now.toTimeString().split(' ')[0];
  }
  try {
    const d = new Date(ts);
    if (!isNaN(d.getTime())) {
      return d.toTimeString().split(' ')[0];
    }
  } catch {
    // fallback
  }
  return ts.length > 8 ? ts.slice(11, 19) : ts;
};

export const ReasoningPanel: React.FC<ReasoningPanelProps> = ({ steps = [], className = '' }) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [userScrolledUp, setUserScrolledUp] = useState<boolean>(false);
  const [typedCharCount, setTypedCharCount] = useState<number>(0);
  const [typingStepIndex, setTypingStepIndex] = useState<number>(-1);

  // Store timestamps persistently per step index so they don't change on re-render
  const timestampsRef = useRef<string[]>([]);

  // Reset logic when steps shrinks to []
  useEffect(() => {
    if (steps.length === 0) {
      setTypedCharCount(0);
      setTypingStepIndex(-1);
      setUserScrolledUp(false);
      timestampsRef.current = [];
    }
  }, [steps.length]);

  // Keep timestamp cache aligned with steps
  useEffect(() => {
    if (steps.length > timestampsRef.current.length) {
      for (let i = timestampsRef.current.length; i < steps.length; i++) {
        timestampsRef.current.push(formatTimestamp(steps[i].ts));
      }
    }
  }, [steps]);

  // Typing effect on the newest step only (approx 25ms per char)
  useEffect(() => {
    if (steps.length === 0) return;

    const newestIndex = steps.length - 1;
    const targetText = steps[newestIndex].text;

    // If new step added, start typing from 0
    if (typingStepIndex !== newestIndex) {
      setTypingStepIndex(newestIndex);
      setTypedCharCount(0);
      return;
    }

    // Continue typing current newest step if characters remain
    if (typedCharCount < targetText.length) {
      const timer = setTimeout(() => {
        setTypedCharCount((prev) => Math.min(prev + 1, targetText.length));
      }, 25);
      return () => clearTimeout(timer);
    }
  }, [steps, typingStepIndex, typedCharCount]);

  // Auto-scroll to bottom when new steps arrive or characters type out (unless user scrolled up)
  useEffect(() => {
    if (!userScrolledUp && scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
  }, [steps, typedCharCount, userScrolledUp]);

  // Detect user manual scroll up
  const handleScroll = () => {
    if (!scrollContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    // 35px threshold
    const isAtBottom = distanceFromBottom <= 35;
    setUserScrolledUp(!isAtBottom);
  };

  const handleJumpToLatest = () => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTo({
        top: scrollContainerRef.current.scrollHeight,
        behavior: 'smooth',
      });
      setUserScrolledUp(false);
    }
  };

  const isAnyRunning = steps.some((s) => s.status === 'running');

  return (
    <div
      className={`relative flex flex-col w-full h-[360px] min-h-[360px] max-w-[640px] bg-[#080c14] border border-zinc-800 rounded-xl overflow-hidden shadow-2xl font-mono select-text ${className}`}
    >
      {/* Terminal Header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-[#0e1422] border-b border-zinc-850 select-none">
        <div className="flex items-center gap-2">
          <span className="w-3.5 h-3.5 rounded-full bg-rose-500/80 inline-block" />
          <span className="w-3.5 h-3.5 rounded-full bg-amber-500/80 inline-block" />
          <span className="w-3.5 h-3.5 rounded-full bg-emerald-500/80 inline-block" />
          <span className="ml-2 text-zinc-300 text-base font-semibold tracking-wide">
            terminal://agnitia/reasoning-engine
          </span>
        </div>
        <div className="flex items-center gap-2">
          {isAnyRunning ? (
            <span className="flex items-center gap-1.5 px-2.5 py-0.5 text-base text-amber-400 bg-amber-950/60 border border-amber-800/60 rounded-full font-medium animate-pulse">
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
              RUNNING
            </span>
          ) : steps.length > 0 ? (
            <span className="px-2.5 py-0.5 text-base text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 rounded-full font-medium">
              IDLE
            </span>
          ) : (
            <span className="px-2.5 py-0.5 text-base text-zinc-400 bg-zinc-900 border border-zinc-800 rounded-full">
              STANDBY
            </span>
          )}
        </div>
      </div>

      {/* Terminal Body */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 p-4 overflow-y-auto space-y-3.5 scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-transparent"
      >
        {steps.length === 0 ? (
          <div className="flex items-center gap-2.5 text-zinc-500 text-base py-3">
            <span className="text-emerald-400 font-bold select-none text-base">❯</span>
            <span className="italic text-base">Waiting for incident...</span>
            <span className="w-2 h-5 bg-emerald-400/80 animate-pulse ml-1 inline-block" />
          </div>
        ) : (
          steps.map((step, index) => {
            const agentCfg = AGENT_COLORS[step.agent] || AGENT_COLORS.diagnose;
            const tsStr = timestampsRef.current[index] || formatTimestamp(step.ts);
            const isNewest = index === steps.length - 1;

            // Typing effect: only newest step types; earlier steps render in full
            const displayText =
              isNewest && typingStepIndex === index
                ? step.text.slice(0, typedCharCount)
                : step.text;

            const isCurrentlyTyping = isNewest && typedCharCount < step.text.length;

            return (
              <div
                key={`${step.agent}-${index}`}
                className="flex items-start text-base leading-relaxed tracking-normal group"
              >
                {/* Prompt Glyph */}
                <span className="text-emerald-400 font-bold mr-2 select-none text-base shrink-0">
                  ❯
                </span>

                {/* Timestamp */}
                <span className="text-zinc-500 mr-2.5 select-none text-base shrink-0 font-mono">
                  [{tsStr}]
                </span>

                {/* Agent Tag */}
                <span
                  className={`px-1.5 py-0.5 rounded border text-base font-bold mr-2.5 select-none shrink-0 ${agentCfg.bg} ${agentCfg.border} ${agentCfg.text}`}
                >
                  {agentCfg.tag}
                </span>

                {/* Step Text & Status Cursor / Badges */}
                <span className="text-zinc-100 text-base break-words font-mono flex-1">
                  {displayText}

                  {/* Running state or typing state: blinking cursor */}
                  {(step.status === 'running' || isCurrentlyTyping) && (
                    <span className="inline-block w-2.5 h-5 ml-1 bg-emerald-400 text-emerald-400 animate-pulse align-middle font-bold">
                      ▋
                    </span>
                  )}

                  {/* Done badge */}
                  {step.status === 'done' && !isCurrentlyTyping && (
                    <span className="inline-flex items-center justify-center ml-2 text-emerald-400 font-bold text-base select-none">
                      ✓
                    </span>
                  )}

                  {/* Failed badge */}
                  {step.status === 'failed' && (
                    <span className="inline-flex items-center justify-center ml-2 text-rose-500 font-bold text-base select-none">
                      ✗
                    </span>
                  )}
                </span>
              </div>
            );
          })
        )}
      </div>

      {/* Floating 'Jump to latest' button */}
      {userScrolledUp && steps.length > 0 && (
        <button
          type="button"
          onClick={handleJumpToLatest}
          className="absolute bottom-4 right-4 px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white text-base font-mono font-medium rounded-lg shadow-xl flex items-center gap-2 border border-emerald-400/40 cursor-pointer transition-all animate-bounce z-20"
        >
          <span>Jump to latest</span>
          <span className="text-lg">↓</span>
        </button>
      )}
    </div>
  );
};

export default ReasoningPanel;
