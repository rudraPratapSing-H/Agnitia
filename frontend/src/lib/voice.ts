// D:\CoffeeOverflow\Agnitia\frontend\src\lib\voice.ts - Voice Briefing (Google/Gemini TTS)
let isVoiceMuted = false; // Matches sounds.ts's default (store.ts: soundMuted: false) -- one mute button controls both

let currentAudio: HTMLAudioElement | null = null;
let activeController: AbortController | null = null;
let requestSeq = 0; // monotonic id -- lets a stale in-flight request recognize it's been superseded

export function setVoiceMuted(muted: boolean) {
  isVoiceMuted = muted;
  if (muted) stopCurrent();
}

/** Cancels any in-flight TTS fetch and stops whatever's currently audible. */
function stopCurrent() {
  requestSeq++; // invalidate any in-flight request's eventual .then()/.catch()
  activeController?.abort();
  activeController = null;
  currentAudio?.pause();
  currentAudio = null;
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
}

function getApiBase(): string {
  const wsUrl: string = (import.meta as any).env?.VITE_WS_URL || 'ws://localhost:8000/ws';
  try {
    const u = new URL(wsUrl);
    u.protocol = u.protocol === 'wss:' ? 'https:' : 'http:';
    return `${u.protocol}//${u.host}`;
  } catch {
    return 'http://localhost:8000';
  }
}

/** Last-resort fallback: the browser's own speech synthesis, no network needed. */
function speakWithBrowserFallback(text: string) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.05;
  utterance.pitch = 1.0;
  window.speechSynthesis.speak(utterance);
}

/**
 * Reads `text` aloud using Google TTS (POST /api/tts). Falls back to the browser's
 * built-in speechSynthesis if that call fails or is slow -- the briefing should never
 * just go silent on stage. Silent when muted.
 *
 * Single-flight: calling this again cancels any still-in-flight request and stops
 * whatever's currently playing first, so two briefings can never overlap.
 */
export function speakBriefing(text: string): void {
  if (isVoiceMuted) return;

  stopCurrent();
  const mySeq = requestSeq; // stopCurrent() already bumped it; capture this call's id
  const controller = new AbortController();
  activeController = controller;
  const timeout = setTimeout(() => controller.abort(), 16000);

  fetch(`${getApiBase()}/api/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(`TTS request failed: ${res.status}`);
      const blob = await res.blob();
      if (mySeq !== requestSeq || isVoiceMuted) return; // superseded or muted while in flight
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      currentAudio = audio;
      audio.addEventListener('ended', () => URL.revokeObjectURL(url));
      audio.play().catch(() => {
        if (mySeq === requestSeq) speakWithBrowserFallback(text);
      });
    })
    .catch((err: any) => {
      if (err?.name === 'AbortError') return; // intentionally cancelled by a newer call
      if (mySeq === requestSeq && !isVoiceMuted) speakWithBrowserFallback(text);
    })
    .finally(() => clearTimeout(timeout));
}
