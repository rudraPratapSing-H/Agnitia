import React, { useState, useRef } from 'react';
import Stopwatch from '../Stopwatch';
import CostTicker from '../CostTicker';

export const isTimerDemoMode = (): boolean => {
  if (typeof window === 'undefined') return false;
  const params = new URLSearchParams(window.location.search);
  return params.get('demo') === 'timer';
};

export const TimerDemo: React.FC = () => {
  const [startedAt, setStartedAt] = useState<string | null>(null);
  const [resolvedAt, setResolvedAt] = useState<string | null>(null);
  const [stressTestStatus, setStressTestStatus] = useState<string>('Ready');
  const [testErrors, setTestErrors] = useState<string[]>([]);

  const handleStart = () => {
    setStartedAt(new Date().toISOString());
    setResolvedAt(null);
  };

  const handleStartSimulatedPast = () => {
    // >1 hour in the past to trigger time-source guard
    const twoHoursAgo = new Date(Date.now() - 2 * 3600 * 1000).toISOString();
    setStartedAt(twoHoursAgo);
    setResolvedAt(null);
  };

  const handleResolve = () => {
    if (!startedAt) return;
    setResolvedAt(new Date().toISOString());
  };

  const handleReset = () => {
    setStartedAt(null);
    setResolvedAt(null);
  };

  // Automated 20 quick Start/Reset clicks stress test
  const runStressTest = async () => {
    setStressTestStatus('Running 20 rapid cycles...');
    setTestErrors([]);
    const errors: string[] = [];

    // Spy on console.error
    const originalError = console.error;
    console.error = (...args: any[]) => {
      errors.push(args.join(' '));
      originalError(...args);
    };

    try {
      for (let i = 1; i <= 20; i++) {
        // Toggle Start
        setStartedAt(new Date().toISOString());
        setResolvedAt(null);
        await new Promise((r) => setTimeout(r, 40));

        // Toggle Reset
        setStartedAt(null);
        setResolvedAt(null);
        await new Promise((r) => setTimeout(r, 40));
      }

      console.error = originalError;

      if (errors.length === 0) {
        setStressTestStatus('PASSED: 20 rapid Start/Reset cycles completed with 0 errors');
      } else {
        setStressTestStatus(`FAILED: ${errors.length} errors captured`);
        setTestErrors(errors);
      }
    } catch (e: any) {
      console.error = originalError;
      setStressTestStatus(`EXCEPTION: ${e.message}`);
    }
  };

  return (
    <div className="min-h-screen bg-[#06090e] text-zinc-100 flex flex-col items-center justify-center p-6 font-mono select-none">
      <div className="w-full max-w-xl bg-stone-950 border border-stone-800 rounded-2xl p-6 shadow-2xl flex flex-col gap-6">
        {/* Header */}
        <div className="border-b border-stone-800 pb-4">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold text-emerald-400 flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
              Stopwatch & CostTicker Dev Demo
            </h1>
            <span className="text-xs bg-stone-800 text-stone-300 px-2 py-0.5 rounded border border-stone-700">
              Task 2.13
            </span>
          </div>
          <p className="text-xs text-stone-400 mt-1">
            Endpoint: <code className="text-emerald-300">/?demo=timer</code>
          </p>
        </div>

        {/* Live Mounted Components */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Stopwatch isActive={!!startedAt && !resolvedAt} resolvedAt={resolvedAt} />
          <CostTicker
            isActive={!!startedAt && !resolvedAt}
            resolvedAt={resolvedAt}
            costPerMinute={Number(import.meta.env.VITE_COST_PER_MINUTE) || 4200}
          />
        </div>

        {/* Invalid costPerMinute Edge Case Test Component */}
        <div className="p-3 bg-stone-900/60 border border-stone-800 rounded-xl flex items-center justify-between">
          <div className="text-xs text-stone-400">
            Fallback Test (NaN costPerMinute):
          </div>
          <div className="scale-90 origin-right">
            <CostTicker
              isActive={!!startedAt && !resolvedAt}
              resolvedAt={resolvedAt}
              costPerMinute={NaN}
            />
          </div>
        </div>

        {/* Control Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleStart}
            className="flex-1 bg-red-600 hover:bg-red-500 active:bg-red-700 text-white font-bold py-2.5 px-4 rounded-xl text-xs transition-all shadow-md cursor-pointer"
          >
            Start (Current Time)
          </button>

          <button
            onClick={handleStartSimulatedPast}
            className="flex-1 bg-amber-600 hover:bg-amber-500 active:bg-amber-700 text-white font-bold py-2.5 px-4 rounded-xl text-xs transition-all shadow-md cursor-pointer"
          >
            Start (&gt;1h Past Guard)
          </button>

          <button
            onClick={handleResolve}
            disabled={!startedAt || !!resolvedAt}
            className={`flex-1 font-bold py-2.5 px-4 rounded-xl text-xs transition-all shadow-md cursor-pointer ${
              !startedAt || !!resolvedAt
                ? 'bg-stone-800 text-stone-600 cursor-not-allowed'
                : 'bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white'
            }`}
          >
            Resolve
          </button>

          <button
            onClick={handleReset}
            className="flex-1 bg-stone-800 hover:bg-stone-700 active:bg-stone-900 text-stone-200 font-bold py-2.5 px-4 rounded-xl text-xs transition-all border border-stone-700 cursor-pointer"
          >
            Reset
          </button>
        </div>

        {/* 20 Quick Clicks Stress Test Section */}
        <div className="p-4 bg-stone-900 border border-stone-800 rounded-xl flex flex-col gap-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-stone-300">
              Stress Test: 20 Quick Start/Reset Clicks
            </span>
            <button
              onClick={runStressTest}
              className="bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white text-xs font-bold px-3 py-1.5 rounded-lg cursor-pointer transition-all"
            >
              Run Stress Test
            </button>
          </div>
          <div className="text-xs text-stone-400 bg-stone-950 p-2.5 rounded-lg border border-stone-800/80">
            Status: <span className="text-emerald-400 font-bold">{stressTestStatus}</span>
          </div>
          {testErrors.length > 0 && (
            <div className="text-xs text-red-400 bg-red-950/40 p-2 rounded border border-red-800">
              {testErrors.map((err, i) => (
                <div key={i}>{err}</div>
              ))}
            </div>
          )}
        </div>

        {/* State Telemetry Inspector */}
        <div className="text-[11px] text-stone-500 flex flex-col gap-1 border-t border-stone-800 pt-3">
          <div>started_at: <span className="text-stone-300">{startedAt || 'undefined'}</span></div>
          <div>resolved_at: <span className="text-stone-300">{resolvedAt || 'undefined'}</span></div>
        </div>
      </div>
    </div>
  );
};

export default TimerDemo;
