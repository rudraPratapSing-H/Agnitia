// frontend/src/lib/sounds.ts (Member 4, task 3.10)
// Synthesized Web Audio tones -- no external audio files to ship or load.

let audioCtx: AudioContext | null = null;
let muted = false;

export function setMuted(muted_: boolean): void {
  muted = muted_;
}

export function isMuted(): boolean {
  return muted;
}

function getAudioContext(): AudioContext | null {
  if (typeof window === 'undefined') return null;
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioContextClass) return null;
    audioCtx = new AudioContextClass();
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

function tone(freq: number, startOffset: number, durationS: number, type: OscillatorType, peakGain: number): void {
  const ctx = getAudioContext();
  if (!ctx) return;

  const start = ctx.currentTime + startOffset;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();

  osc.type = type;
  osc.frequency.setValueAtTime(freq, start);

  gain.gain.setValueAtTime(peakGain, start);
  gain.gain.exponentialRampToValueAtTime(0.001, start + durationS);

  osc.connect(gain);
  gain.connect(ctx.destination);

  osc.start(start);
  osc.stop(start + durationS);
}

/** Urgent two-tone alarm sweep, played once on chaos injection. */
export function playSiren(): void {
  if (muted) return;
  const ctx = getAudioContext();
  if (!ctx) return;

  const now = ctx.currentTime;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();

  osc.type = 'sawtooth';
  osc.frequency.setValueAtTime(440, now);
  osc.frequency.exponentialRampToValueAtTime(880, now + 0.2);
  osc.frequency.exponentialRampToValueAtTime(440, now + 0.4);

  gain.gain.setValueAtTime(0.08, now);
  gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);

  osc.connect(gain);
  gain.connect(ctx.destination);

  osc.start(now);
  osc.stop(now + 0.45);
}

/** Pleasant ascending chime, played once on incident resolution. */
export function playChime(): void {
  if (muted) return;
  const notes = [523.25, 659.25, 783.99]; // C5, E5, G5
  notes.forEach((freq, idx) => tone(freq, idx * 0.1, 0.35, 'sine', 0.1));
}
