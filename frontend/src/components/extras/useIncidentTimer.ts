import { useState, useEffect, useRef } from 'react';

const ONE_HOUR_MS = 60 * 60 * 1000;

export interface IncidentTimerState {
  elapsedMs: number;
  status: 'idle' | 'running' | 'resolved';
}

/**
 * Custom hook providing a synchronized, leak-safe timer for incident telemetry.
 * Implements a time-source guard: if startedAt is >1 hour away from current time
 * (typical in simulator replays with fixed synthetic timestamps), it measures elapsed
 * time from the moment the component first witnessed the event.
 */
export function useIncidentTimer(
  startedAt?: string | null,
  resolvedAt?: string | null
): IncidentTimerState {
  const [elapsedMs, setElapsedMs] = useState<number>(0);
  const [status, setStatus] = useState<'idle' | 'running' | 'resolved'>('idle');

  const firstSeenStartRef = useRef<number | null>(null);
  const firstSeenResolveRef = useRef<number | null>(null);
  const useFirstSeenRef = useRef<boolean>(false);
  const intervalRef = useRef<number | null>(null);

  // Helper to safely clear any active polling interval
  const clearActiveInterval = () => {
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  useEffect(() => {
    // 1. Reset / Idle condition: startedAt is null or undefined
    if (!startedAt) {
      clearActiveInterval();
      firstSeenStartRef.current = null;
      firstSeenResolveRef.current = null;
      useFirstSeenRef.current = false;
      setElapsedMs(0);
      setStatus('idle');
      return;
    }

    // 2. Incident Started: determine timing baseline
    if (firstSeenStartRef.current === null) {
      firstSeenStartRef.current = Date.now();
      const parsedStart = new Date(startedAt).getTime();
      // Time-source guard: if more than 1 hour away from current time, use component arrival time
      if (isNaN(parsedStart) || Math.abs(Date.now() - parsedStart) > ONE_HOUR_MS) {
        useFirstSeenRef.current = true;
      } else {
        useFirstSeenRef.current = false;
      }
    }

    // 3. Resolved condition: resolvedAt is provided
    if (resolvedAt) {
      clearActiveInterval();
      if (firstSeenResolveRef.current === null) {
        firstSeenResolveRef.current = Date.now();
      }

      let finalElapsed = 0;
      if (useFirstSeenRef.current) {
        finalElapsed = Math.max(0, firstSeenResolveRef.current - (firstSeenStartRef.current || firstSeenResolveRef.current));
      } else {
        const parsedStart = new Date(startedAt).getTime();
        const parsedResolve = new Date(resolvedAt).getTime();
        finalElapsed = Math.max(0, parsedResolve - parsedStart);
      }

      setElapsedMs(finalElapsed);
      setStatus('resolved');
      return;
    }

    // 4. Running condition: calculate live elapsed time every 100ms
    setStatus('running');
    firstSeenResolveRef.current = null;

    const tick = () => {
      let currentElapsed = 0;
      if (useFirstSeenRef.current) {
        currentElapsed = Math.max(0, Date.now() - (firstSeenStartRef.current || Date.now()));
      } else {
        const parsedStart = new Date(startedAt).getTime();
        currentElapsed = Math.max(0, Date.now() - parsedStart);
      }
      setElapsedMs(currentElapsed);
    };

    tick();
    clearActiveInterval();
    intervalRef.current = window.setInterval(tick, 100);

    return () => {
      clearActiveInterval();
    };
  }, [startedAt, resolvedAt]);

  // Clean up on component unmount
  useEffect(() => {
    return () => {
      clearActiveInterval();
    };
  }, []);

  return { elapsedMs, status };
}
