// D:\CoffeeOverflow\Agnitia\frontend\src\lib\voice.ts - Voice Briefing (Google/Gemini TTS)
let isVoiceMuted = false; // Matches sounds.ts's default (store.ts: soundMuted: false) -- one mute button controls both

let currentAudio: HTMLAudioElement | null = null;

export function setVoiceMuted(muted: boolean) {
  isVoiceMuted = muted;
  if (muted) {
    currentAudio?.pause();
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
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
 * Reads `text` aloud using Gemini's text-to-speech (POST /api/tts). Falls back
 * to the browser's built-in speechSynthesis if that call fails or is slow --
 * the briefing should never just go silent on stage. Silent when muted.
 */
export function speakBriefing(text: string): void {
  if (isVoiceMuted) return;

  currentAudio?.pause();

  const controller = new AbortController();
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
      if (isVoiceMuted) return; // muted while the request was in flight
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      currentAudio = audio;
      audio.addEventListener('ended', () => URL.revokeObjectURL(url));
      audio.play().catch(() => speakWithBrowserFallback(text));
    })
    .catch(() => {
      if (!isVoiceMuted) speakWithBrowserFallback(text);
    })
    .finally(() => clearTimeout(timeout));
}
