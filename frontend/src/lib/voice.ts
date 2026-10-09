// frontend/src/lib/voice.ts (Member 4, task 3.10)
// Hands-free audio briefing via the browser's built-in speech synthesis.

import { isMuted } from './sounds';

/** Reads `text` aloud. Silent when sounds.setMuted(true) is in effect. */
export function speak(text: string): void {
  if (isMuted()) return;
  if (typeof window === 'undefined' || !window.speechSynthesis) return;

  window.speechSynthesis.cancel(); // don't stack briefings
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.05;
  utterance.pitch = 1.0;
  window.speechSynthesis.speak(utterance);
}
