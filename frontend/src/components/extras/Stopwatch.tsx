import React from 'react';
import { useIncidentTimer } from './useIncidentTimer';

export interface StopwatchProps {
  startedAt?: string | null;
  resolvedAt?: string | null;
}

export const Stopwatch: React.FC<StopwatchProps> = ({ startedAt, resolvedAt }) => {
  const { elapsedMs, status } = useIncidentTimer(startedAt, resolvedAt);

  // Format to big monospace MM:SS.t
  const formatTime = (ms: number): string => {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    const tenths = Math.floor((ms % 1000) / 100);

    const mm = String(minutes).padStart(2, '0');
    const ss = String(seconds).padStart(2, '0');
    return `${mm}:${ss}.${tenths}`;
  };

  const elapsedSeconds = Math.round(elapsedMs / 1000);

  return (
    <div className="flex flex-col items-center justify-center p-3 rounded-xl bg-stone-900 border border-stone-800 text-stone-100 font-mono shadow-sm select-none">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-stone-400 mb-0.5">
        Incident Stopwatch
      </div>

      {/* Big monospace MM:SS.t display */}
      <div
        className={`text-3xl md:text-4xl font-black tracking-widest tabular-nums transition-colors duration-200 ${
          status === 'idle'
            ? 'text-stone-600'
            : status === 'running'
            ? 'text-red-500 animate-pulse'
            : 'text-emerald-400'
        }`}
      >
        {status === 'idle' ? '00:00.0' : formatTime(elapsedMs)}
      </div>

      {/* Status description */}
      <div className="text-xs font-medium mt-1">
        {status === 'idle' && (
          <span className="text-stone-500 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500/50" />
            All systems normal
          </span>
        )}

        {status === 'running' && (
          <span className="text-red-400 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
            Downtime active
          </span>
        )}

        {status === 'resolved' && (
          <span className="text-emerald-400 font-bold flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            Recovered in {elapsedSeconds}s
          </span>
        )}
      </div>
    </div>
  );
};

export default Stopwatch;
