// D:\CoffeeOverflow\Agnitia\frontend\src\lib\voice.ts - Speech Synthesis Briefing
let isVoiceMuted = false; // Matches sounds.ts's default (store.ts: soundMuted: false) -- one mute button controls both

export function setVoiceMuted(muted: boolean) {
  isVoiceMuted = muted;
}

export function speakBriefing(text: string) {
  if (isVoiceMuted || typeof window === 'undefined' || !window.speechSynthesis) return;

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.05;
  utterance.pitch = 1.0;
  window.speechSynthesis.speak(utterance);
}
