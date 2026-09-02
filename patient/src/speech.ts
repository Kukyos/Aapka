// Browser speech: the machine talking, and the machine listening.
//
// Both use what Chrome already ships. That is what makes `git clone` and one command
// enough, and it means the kiosk speaks and listens with no server round trip — which
// is also the offline story from gate G1.
//
// Everything here degrades to silence rather than to an error. A terminal whose voice
// stops working must still be completely usable by touch, because the touch path was
// never the fallback: it is the primary path with a voice option beside it.

export type Lang = "en" | "hi";

const VOICE_LOCALE: Record<Lang, string> = { en: "en-IN", hi: "hi-IN" };

// ---------------------------------------------------------------- speaking

let currentUtterance: SpeechSynthesisUtterance | null = null;

function pickVoice(lang: Lang): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis?.getVoices?.() ?? [];
  const want = VOICE_LOCALE[lang];
  return (
    voices.find((v) => v.lang === want) ??
    voices.find((v) => v.lang?.startsWith(lang)) ??
    null
  );
}

export function speak(text: string, lang: Lang, onEnd?: () => void): void {
  if (!("speechSynthesis" in window) || !text) {
    onEnd?.();
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = VOICE_LOCALE[lang];
  const voice = pickVoice(lang);
  if (voice) utterance.voice = voice;
  // Slower than default. The audience is elderly, often hard of hearing, and standing
  // in a loud hall. Rushing the prompt is the fastest way to lose them.
  utterance.rate = 0.88;
  utterance.pitch = 1;
  utterance.onend = () => onEnd?.();
  utterance.onerror = () => onEnd?.();
  currentUtterance = utterance;
  window.speechSynthesis.speak(utterance);
}

export function stopSpeaking(): void {
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  currentUtterance = null;
}

export function isSpeaking(): boolean {
  return Boolean(currentUtterance) && window.speechSynthesis?.speaking;
}

// Voices load asynchronously in Chrome and are empty on first paint. Warm them so the
// first prompt is not silent.
export function warmVoices(): void {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.getVoices();
  window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
}

// ---------------------------------------------------------------- listening

type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onend: (() => void) | null;
};

function recogniser(): SpeechRecognitionLike | null {
  const Ctor =
    (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition;
  return Ctor ? (new Ctor() as SpeechRecognitionLike) : null;
}

export function speechAvailable(): boolean {
  return recogniser() !== null;
}

export type ListenHandle = { stop: () => void };

export function listen(
  lang: Lang,
  onResult: (text: string, final: boolean) => void,
  onError: (reason: string) => void,
): ListenHandle | null {
  const recognition = recogniser();
  if (!recognition) {
    onError("no-recogniser");
    return null;
  }
  recognition.lang = VOICE_LOCALE[lang];
  recognition.continuous = false;
  // Interim results drive the "we are hearing you" feedback. A patient who cannot
  // tell whether the machine is listening will simply stop talking.
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;

  recognition.onresult = (event: any) => {
    let text = "";
    let final = false;
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      text += event.results[i][0].transcript;
      if (event.results[i].isFinal) final = true;
    }
    onResult(text.trim(), final);
  };
  recognition.onerror = (event: any) => onError(event?.error ?? "unknown");
  recognition.onend = () => onResult("", true);

  try {
    recognition.start();
  } catch {
    onError("already-started");
    return null;
  }
  return { stop: () => recognition.abort() };
}
