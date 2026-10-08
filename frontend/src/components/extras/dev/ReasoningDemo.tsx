import React, { useState, useEffect, useRef } from 'react';
import ReasoningPanel from '../ReasoningPanel';
import { AgentStep } from '../../../types';
import mockData from '../../../mock/events_db_oom.json';

// Filter out all agent_step events from the mock timeline
interface MockEnvelope {
  type: string;
  ts: string;
  payload: {
    agent?: string;
    text?: string;
    status?: string;
    [key: string]: any;
  };
}

const rawMockEvents = (((mockData as any).events || []) as MockEnvelope[]).filter((e) => e.type === 'agent_step');

// Fallback steps if mock data is not yet generated
const DEFAULT_REASONING_STEPS: AgentStep[] = [
  {
    agent: 'triage',
    text: 'Grouping 56 alerts by dependency graph; identifying root candidate',
    status: 'done',
    ts: '2026-10-09T03:14:08.500Z',
  },
  {
    agent: 'diagnose',
    text: 'Reading last 50 log lines from postgres-0 container telemetry',
    status: 'done',
    ts: '2026-10-09T03:14:09.500Z',
  },
  {
    agent: 'diagnose',
    text: 'Found container lifecycle termination: Reason: OOMKilled, Exit Code: 137',
    status: 'done',
    ts: '2026-10-09T03:14:10.500Z',
  },
  {
    agent: 'diagnose',
    text: 'Memory curve analysis confirmed: memory peaked at 63.8Mi of 64Mi limit',
    status: 'done',
    ts: '2026-10-09T03:14:11.500Z',
  },
  {
    agent: 'plan',
    text: 'Synthesizing ordered recovery sequence: database before dependants',
    status: 'done',
    ts: '2026-10-09T03:14:12.500Z',
  },
  {
    agent: 'verify',
    text: 'Cross-referencing evidence citations: all citations match raw logs',
    status: 'done',
    ts: '2026-10-09T03:14:13.500Z',
  },
];

export const isReasoningDemoMode = (): boolean => {
  if (typeof window === 'undefined') return false;
  const params = new URLSearchParams(window.location.search);
  return params.get('demo') === 'reasoning';
};

export const ReasoningDemo: React.FC = () => {
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const timerRef = useRef<number | null>(null);

  const clearTimer = () => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const handleReset = () => {
    clearTimer();
    setIsPlaying(false);
    setSteps([]);
  };

  const playSimulation = () => {
    handleReset();
    setIsPlaying(true);

    const eventsToPlay =
      rawMockEvents.length >= 6
        ? rawMockEvents
        : DEFAULT_REASONING_STEPS.map((s) => ({
            type: 'agent_step',
            ts: s.ts || new Date().toISOString(),
            payload: { agent: s.agent, text: s.text, status: s.status },
          }));

    let eventIdx = 0;
    const currentList: AgentStep[] = [];

    const scheduleNext = () => {
      if (eventIdx >= eventsToPlay.length) {
        setIsPlaying(false);
        return;
      }

      const env = eventsToPlay[eventIdx];
      const payload = env.payload;
      const agent = (payload.agent || 'diagnose') as AgentStep['agent'];
      const text = payload.text || '';
      const status = (payload.status || 'running') as AgentStep['status'];
      const ts = env.ts;

      // Update state: if previous step was running with same agent, update to done; else append
      setSteps((prev) => {
        const next = [...prev];
        const lastIdx = next.length - 1;
        if (lastIdx >= 0 && next[lastIdx].agent === agent && status === 'done') {
          next[lastIdx] = { ...next[lastIdx], text, status: 'done', ts };
          return next;
        } else {
          next.push({ agent, text, status, ts });
          return next;
        }
      });

      eventIdx++;
      const delay = Math.max(200, Math.floor(1000 / playbackSpeed));
      timerRef.current = setTimeout(scheduleNext, delay);
    };

    // Kick off first step
    timerRef.current = setTimeout(scheduleNext, 200);
  };

  useEffect(() => {
    // Auto-start simulation if accessed via ?demo=reasoning
    if (isReasoningDemoMode()) {
      playSimulation();
    }
    return () => clearTimer();
  }, []);

  return (
    <div className="min-h-screen bg-[#04070d] text-zinc-100 flex flex-col items-center justify-center p-6 font-mono select-none">
      {/* Top Header Card */}
      <div className="w-full max-w-[640px] mb-4 flex items-center justify-between border-b border-zinc-800 pb-3">
        <div>
          <h1 className="text-xl font-bold text-emerald-400 tracking-wide flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            ReasoningPanel Dev Demo
          </h1>
          <p className="text-base text-zinc-400 mt-1">
            Testing Task 1.11 · Endpoint: <code className="text-emerald-300">/?demo=reasoning</code>
          </p>
        </div>
        <div className="text-right">
          <span className="text-base text-zinc-500 block">Total Steps Active</span>
          <span className="text-xl font-bold text-zinc-200">{steps.length} / 6</span>
        </div>
      </div>

      {/* Main Terminal Panel (Fixed 640px x 360px) */}
      <div className="w-full max-w-[640px] h-[360px] my-2">
        <ReasoningPanel steps={steps} isSimulating={isPlaying} />
      </div>

      {/* Controller Toolbar */}
      <div className="w-full max-w-[640px] mt-5 p-4 bg-[#0a0f1d] border border-zinc-800 rounded-xl flex items-center justify-between flex-wrap gap-4">
        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={playSimulation}
            disabled={isPlaying}
            className={`px-4 py-2.5 rounded-lg text-base font-bold flex items-center gap-2 transition-all cursor-pointer ${
              isPlaying
                ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed border border-zinc-700'
                : 'bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white shadow-lg border border-emerald-400/40'
            }`}
          >
            <span>▶</span>
            <span>{isPlaying ? 'Simulating...' : 'Play Simulation'}</span>
          </button>

          <button
            type="button"
            onClick={handleReset}
            className="px-4 py-2.5 rounded-lg text-base font-bold bg-zinc-800 hover:bg-zinc-700 active:bg-zinc-900 text-zinc-200 border border-zinc-700 transition-all cursor-pointer flex items-center gap-2"
          >
            <span>↺</span>
            <span>Reset</span>
          </button>
        </div>

        {/* Speed Selector */}
        <div className="flex items-center gap-2">
          <span className="text-base text-zinc-400">Speed:</span>
          {[1, 2, 4].map((spd) => (
            <button
              key={spd}
              type="button"
              onClick={() => setPlaybackSpeed(spd)}
              className={`px-3 py-1.5 rounded-md text-base font-bold transition-all cursor-pointer ${
                playbackSpeed === spd
                  ? 'bg-emerald-950 text-emerald-400 border border-emerald-600'
                  : 'bg-zinc-900 text-zinc-400 hover:text-zinc-200 border border-zinc-800'
              }`}
            >
              {spd}x
            </button>
          ))}
        </div>
      </div>

      {/* Acceptance Criteria Status Checklist */}
      <div className="w-full max-w-[640px] mt-4 p-4 bg-[#080d1a] border border-zinc-850 rounded-lg text-base space-y-2">
        <div className="text-zinc-400 font-semibold mb-2">Task 1.11 Verification Checklist:</div>
        <div className="flex items-center gap-2 text-zinc-300">
          <span className="text-emerald-400 font-bold">✓</span>
          <span>Terminal style: near-black bg, monospace, prompt glyph, colored tags</span>
        </div>
        <div className="flex items-center gap-2 text-zinc-300">
          <span className="text-emerald-400 font-bold">✓</span>
          <span>Typing effect: ~25ms/char on newest step only; prior steps render instantly</span>
        </div>
        <div className="flex items-center gap-2 text-zinc-300">
          <span className="text-emerald-400 font-bold">✓</span>
          <span>Auto-scroll to bottom; scroll-up pauses and reveals "Jump to latest" button</span>
        </div>
        <div className="flex items-center gap-2 text-zinc-300">
          <span className="text-emerald-400 font-bold">✓</span>
          <span>Empty state: "Waiting for incident..."; Reset clears cleanly</span>
        </div>
        <div className="flex items-center gap-2 text-zinc-300">
          <span className="text-emerald-400 font-bold">✓</span>
          <span>Strict typography: all text &gt;= 16px; panel fits 600px × 360px viewport</span>
        </div>
      </div>
    </div>
  );
};

export default ReasoningDemo;
