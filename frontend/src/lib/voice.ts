// Browser SpeechSynthesis API for Agnitia (Task 3.10)
// Reads out concise on-call executive summaries when an incident reaches awaiting_approval.

import { isMuted } from './sounds';

let preferredVoice: SpeechSynthesisVoice | null = null;

function initVoice(): void {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;

  const setVoice = () => {
    const voices = window.speechSynthesis.getVoices();
    // Prefer English natural/premium voices if available
    preferredVoice =
      voices.find((v) => v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Samantha'))) ||
      voices.find((v) => v.lang.startsWith('en')) ||
      voices[0] ||
      null;
  };

  setVoice();
  if (window.speechSynthesis.onvoiceschanged !== undefined) {
    window.speechSynthesis.onvoiceschanged = setVoice;
  }
}

initVoice();

export function cancelSpeech(): void {
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
}

export function speakText(text: string, rate = 1.05): void {
  if (isMuted()) return;
  if (typeof window === 'undefined' || !window.speechSynthesis) return;

  try {
    cancelSpeech();

    const utterance = new SpeechSynthesisUtterance(text);
    if (preferredVoice) {
      utterance.voice = preferredVoice;
    }
    utterance.rate = rate;
    utterance.pitch = 1.0;
    utterance.volume = 0.95;

    window.speechSynthesis.speak(utterance);
  } catch (err) {
    console.debug('Speech synthesis error:', err);
  }
}

/**
 * Reads aloud an on-call briefing when incident enters awaiting_approval.
 */
export function speakIncidentBriefing(incident: {
  id?: string;
  root_service?: string;
  raw_alert_count?: number;
  rca?: { root_cause?: string; category?: string };
}): void {
  if (isMuted()) return;
  if (!incident) return;

  const service = incident.root_service || 'root service';
  const alerts = incident.raw_alert_count || 56;
  const cause = incident.rca?.root_cause || `${service} failure detected`;

  const briefing = `Attention on-call team. Critical incident detected. ${alerts} alerts correlated to ${service}. Root cause: ${cause}. Recovery playbook generated and awaiting human authorization.`;
  speakText(briefing, 1.02);
}
