// Web Audio API sound synthesizer for Agnitia (Task 3.10)
// No external asset files required; synthesizes warning siren and recovery chimes dynamically.

let audioCtx: AudioContext | null = null;
let isAudioMuted = false;

// Check localStorage for mute preference if available
if (typeof window !== 'undefined') {
  try {
    const saved = localStorage.getItem('agnitia_sound_muted');
    if (saved !== null) {
      isAudioMuted = saved === 'true';
    }
  } catch {
    // Ignore storage errors
  }
}

function getAudioContext(): AudioContext | null {
  if (typeof window === 'undefined') return null;
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (AudioContextClass) {
      audioCtx = new AudioContextClass();
    }
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume().catch(() => {});
  }
  return audioCtx;
}

export function isMuted(): boolean {
  return isAudioMuted;
}

export function setMuted(muted: boolean): void {
  isAudioMuted = muted;
  if (typeof window !== 'undefined') {
    try {
      localStorage.setItem('agnitia_sound_muted', String(muted));
      window.dispatchEvent(new CustomEvent('agnitia_mute_change', { detail: { muted } }));
    } catch {
      // Ignore
    }
  }
}

export function toggleMute(): boolean {
  setMuted(!isAudioMuted);
  return isAudioMuted;
}

/**
 * Plays a two-tone emergency siren when a chaos incident is injected.
 */
export function playSiren(durationMs = 1800): void {
  if (isAudioMuted) return;
  const ctx = getAudioContext();
  if (!ctx) return;

  try {
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'sawtooth';
    gain.gain.setValueAtTime(0.12, now);

    // Modulate pitch up and down (440Hz -> 880Hz)
    const cycles = Math.max(1, Math.floor(durationMs / 450));
    for (let i = 0; i < cycles; i++) {
      const t0 = now + i * 0.45;
      osc.frequency.setValueAtTime(460, t0);
      osc.frequency.linearRampToValueAtTime(840, t0 + 0.22);
      osc.frequency.linearRampToValueAtTime(460, t0 + 0.45);
    }

    gain.gain.setValueAtTime(0.12, now + durationMs / 1000 - 0.1);
    gain.gain.linearRampToValueAtTime(0.001, now + durationMs / 1000);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + durationMs / 1000);
  } catch (err) {
    console.debug('Audio playback error (siren):', err);
  }
}

/**
 * Plays an ascending harmonic chime when an incident is fully resolved.
 */
export function playSuccessChime(): void {
  if (isAudioMuted) return;
  const ctx = getAudioContext();
  if (!ctx) return;

  try {
    const notes = [523.25, 659.25, 783.99, 1046.5]; // C5, E5, G5, C6
    const now = ctx.currentTime;

    notes.forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.value = freq;

      const startTime = now + idx * 0.12;
      const noteDuration = 0.6;

      gain.gain.setValueAtTime(0.001, startTime);
      gain.gain.linearRampToValueAtTime(0.15, startTime + 0.04);
      gain.gain.exponentialRampToValueAtTime(0.001, startTime + noteDuration);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(startTime);
      osc.stop(startTime + noteDuration);
    });
  } catch (err) {
    console.debug('Audio playback error (chime):', err);
  }
}

/**
 * Plays a short, crisp notification beep for alert arrivals.
 */
export function playAlertPing(): void {
  if (isAudioMuted) return;
  const ctx = getAudioContext();
  if (!ctx) return;

  try {
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, now);
    osc.frequency.exponentialRampToValueAtTime(440, now + 0.1);

    gain.gain.setValueAtTime(0.08, now);
    gain.gain.linearRampToValueAtTime(0.001, now + 0.1);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.1);
  } catch (err) {
    console.debug('Audio playback error (ping):', err);
  }
}
