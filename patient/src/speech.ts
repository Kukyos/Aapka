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
  // Chrome's recogniser needs a secure context, same as the microphone. Over plain
  // HTTP — which is the phone-handoff path on a hospital LAN — it will construct and
  // then fail silently on start, so check here rather than showing a dead button.
  return recogniser() !== null && window.isSecureContext;
}

// Whether the camera can be opened at all. Same secure-context rule; the documents
// stage asks before it offers.
export function cameraAvailable(): boolean {
  return window.isSecureContext && Boolean(navigator.mediaDevices?.getUserMedia);
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

// ---------------------------------------------------------------- barge-in

// A patient should be able to answer before the prompt has finished. Waiting politely
// for a slow, deliberately-slowed TTS voice to stop is how a four-minute interview
// becomes a six-minute one, and it is not how anyone talks to a person.
//
// Detecting that means listening while the machine is still talking — and on a kiosk
// the microphone sits next to the speaker, so the loudest thing in the room is the
// prompt itself. `echoCancellation` does not help: it cancels what the browser routes
// through its own audio graph, and `speechSynthesis` output is not in that graph.
//
// So the floor is calibrated *while the prompt plays*. The first BARGE_CALIBRATE_MS of
// audio is the machine's own voice plus the hall, and that becomes the baseline. Only a
// person speaking over the top of it clears the margin.
//
// This measures loudness only. No audio is captured, buffered or sent anywhere, and the
// stream is closed the moment the prompt ends — the microphone is not hot for the rest
// of the interview.
//
// TUNING. These numbers were set on a quiet desk. A waiting hall is not a quiet desk and
// a kiosk speaker is not a laptop speaker; expect to sit in the real hall and move them.
// Every failure here is safe in both directions: a missed barge-in means the prompt
// finishes and the patient presses the microphone, exactly as before, and a false
// barge-in means the prompt stops and the screen says "Listening…", which the patient
// can ignore and tap an answer instead.
const BARGE_CALIBRATE_MS = 700; // measured against the prompt, not against silence
const BARGE_MARGIN = 2.6;       // how far above the floor counts as a person
const BARGE_FLOOR_MIN = 0.018;  // absolute floor, for a room quieter than the model expects
const BARGE_SUSTAIN_MS = 220;   // ignore a cough, a dropped file, a chair

export type BargeHandle = { stop: () => void };

export async function armBargeIn(onSpeech: () => void): Promise<BargeHandle | null> {
  // getUserMedia needs a secure context. On the phone-handoff path over plain HTTP
  // there is no microphone at all, and the touch path — which was always the primary
  // path — carries the whole interview. See D-16 in docs/11-deferred.md.
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) return null;

  let stopped = false;
  let stream: MediaStream | null = null;
  let ctx: AudioContext | null = null;
  let frame = 0;

  const teardown = () => {
    stopped = true;
    if (frame) cancelAnimationFrame(frame);
    stream?.getTracks().forEach((track) => track.stop());
    void ctx?.close().catch(() => {});
    stream = null;
    ctx = null;
  };

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: false },
    });
  } catch {
    // Permission refused, or no microphone. Not an error — the terminal is fully
    // usable by touch and the prompt simply plays to the end.
    return null;
  }
  if (stopped) {
    stream.getTracks().forEach((track) => track.stop());
    return null;
  }

  ctx = new AudioContext();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  ctx.createMediaStreamSource(stream).connect(analyser);

  const samples = new Uint8Array(analyser.fftSize);
  const startedAt = performance.now();
  let floor = 0;
  let calibrationCount = 0;
  let sustained = 0;
  let lastTick = startedAt;

  const tick = () => {
    if (stopped) return;
    analyser.getByteTimeDomainData(samples);
    let sum = 0;
    for (let i = 0; i < samples.length; i += 1) {
      const centred = (samples[i] - 128) / 128;
      sum += centred * centred;
    }
    const rms = Math.sqrt(sum / samples.length);

    const now = performance.now();
    const delta = now - lastTick;
    lastTick = now;

    if (now - startedAt < BARGE_CALIBRATE_MS) {
      floor = (floor * calibrationCount + rms) / (calibrationCount + 1);
      calibrationCount += 1;
    } else if (rms > Math.max(floor * BARGE_MARGIN, BARGE_FLOOR_MIN)) {
      sustained += delta;
      if (sustained >= BARGE_SUSTAIN_MS) {
        // Release the microphone before the recogniser asks for it.
        teardown();
        onSpeech();
        return;
      }
    } else {
      sustained = 0;
    }
    frame = requestAnimationFrame(tick);
  };

  frame = requestAnimationFrame(tick);
  return { stop: teardown };
}

// ---------------------------------------------------------------- language

// Picking the language is the first thing the terminal asks and the first place it can
// lose someone: a patient who reads neither tile has to guess. So the screen listens,
// and whatever it hears moves the highlight onto the likely language.
//
// It is a *pre-selection and never a replacement*. The two tiles stay exactly where
// they are and the patient still confirms with one tap, so a wrong detection costs a
// tap rather than an interview in a language nobody in the room speaks. Gate G2 is why:
// the touch path is not allowed to degrade because the voice path had an opinion.
//
// The heuristic is script, not vocabulary. Chrome's hi-IN recogniser returns Devanagari
// when it hears Hindi and Latin when it hears English, which is a far more robust signal
// than any word list and costs nothing — it runs on the recogniser that is already
// there, with no network, which is the only kind of detection gate G1 permits.
const DEVANAGARI = /[ऀ-ॿ]/g;
const LATIN = /[A-Za-z]/g;

// Below this many script-bearing characters there is not enough to decide. "Haan" is
// two syllables of noise; a sentence is a signal.
const LANG_MIN_CHARS = 4;

export function detectLanguage(text: string): Lang | null {
  const devanagari = (text.match(DEVANAGARI) ?? []).length;
  const latin = (text.match(LATIN) ?? []).length;
  if (devanagari + latin < LANG_MIN_CHARS) return null;
  if (devanagari === latin) return null;
  return devanagari > latin ? "hi" : "en";
}

// Listen once, for the language screen only. Resolves to null on anything unclear —
// silence, a hall full of other people talking, no recogniser, a refused permission.
// Every one of those leaves the screen exactly as it was.
export function listenForLanguage(
  onDetected: (lang: Lang, heard: string) => void,
): ListenHandle | null {
  if (!speechAvailable()) return null;
  // hi-IN rather than en-IN: it is the recogniser that emits both scripts, which is
  // the entire basis of the heuristic above.
  return listen(
    "hi",
    (spoken, final) => {
      if (!final || !spoken) return;
      const detected = detectLanguage(spoken);
      if (detected) onDetected(detected, spoken);
    },
    () => {},
  );
}
