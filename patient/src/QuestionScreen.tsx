// The question renderer.
//
// One component renders every question in the ontology, because the ontology is data
// and the screen is driven entirely by it. Adding a question to the YAML puts it on
// the kiosk with no code change — that is what "editable without a rebuild" means.
//
// Gate G2 is the shape of this file: the tappable answer and the spoken answer sit
// side by side and fill the same slot. The microphone is an addition to the tiles,
// never a replacement for them, so a patient who ignores it completes the whole
// interview by touch and one who cannot read completes it by voice.

import { useEffect, useMemo, useRef, useState } from "react";
import type { Lang, Question } from "./api";
import { Icon } from "./Icon";
import { armBargeIn, listen, speak, speechAvailable, stopSpeaking } from "./speech";
import type { BargeHandle } from "./speech";

type Props = {
  question: Question;
  lang: Lang;
  progress: { percent: number; answered: number };
  onAnswer: (value: unknown, source: string) => void;
  onUtterance: (text: string) => void;
  onSkip: () => void;
  busy: boolean;
  hint: string | null;
};

// How long after the prompt ends the barge-in detector stays armed. People answer on
// the beat, not after it; without this the most natural moment to speak is the one
// moment the terminal is not listening.
const BARGE_GRACE_MS = 2500;

const T = {
  listening: { en: "Listening…", hi: "सुन रहे हैं…" },
  tapOrSpeak: { en: "Tap an answer, or press the microphone and speak", hi: "जवाब छूइए, या माइक दबाकर बोलिए" },
  speakNow: { en: "Speak now", hi: "अब बोलिए" },
  done: { en: "Done", hi: "हो गया" },
  next: { en: "Next", hi: "आगे" },
  skip: { en: "Skip this", hi: "छोड़ दें" },
  repeat: { en: "Say it again", hi: "फिर से बोलिए" },
  didNotCatch: { en: "Sorry, I did not catch that. Please try again, or tap an answer.", hi: "माफ़ कीजिए, समझ नहीं आया। फिर से बोलिए, या जवाब छूइए।" },
  chooseMany: { en: "You can choose more than one", hi: "आप एक से ज़्यादा चुन सकते हैं" },
  patientReported: { en: "As reported by the patient", hi: "रोगी के अनुसार" },
};

export function QuestionScreen({
  question, lang, progress, onAnswer, onUtterance, onSkip, busy, hint,
}: Props) {
  const [multi, setMulti] = useState<unknown[]>([]);
  const [scale, setScale] = useState<number | null>(null);
  const [durationN, setDurationN] = useState<number | null>(null);
  const [durationUnit, setDurationUnit] = useState<string | null>(null);
  const [heard, setHeard] = useState("");
  const [listening, setListening] = useState(false);
  const handle = useRef<{ stop: () => void } | null>(null);
  const barge = useRef<BargeHandle | null>(null);
  const listenRef = useRef<() => void>(() => {});

  const disarmBargeIn = () => {
    barge.current?.stop();
    barge.current = null;
  };

  const text = (l: { en: string; hi: string } | null | undefined) =>
    l ? (lang === "hi" ? l.hi : l.en) : "";

  // Speak the prompt on arrival. This is the whole accessibility story: a patient who
  // cannot read hears every question without doing anything.
  useEffect(() => {
    setMulti([]);
    setScale(null);
    setDurationN(null);
    setDurationUnit(null);
    setHeard("");
    const prompt = text(question.prompt);
    const help = question.help ? ` ${text(question.help)}` : "";

    // Barge-in. The microphone is open only while the prompt is being spoken, plus a
    // short grace window for the very common case of someone answering the instant it
    // stops. It measures loudness and nothing else, and it closes itself either way.
    let grace: number | undefined;
    let cancelled = false;
    void armBargeIn(() => {
      barge.current = null;
      listenRef.current();
    }).then((armed) => {
      if (cancelled) armed?.stop();
      else barge.current = armed;
    });

    speak(prompt + help, lang, () => {
      grace = window.setTimeout(disarmBargeIn, BARGE_GRACE_MS);
    });

    return () => {
      cancelled = true;
      if (grace) window.clearTimeout(grace);
      disarmBargeIn();
      stopSpeaking();
      handle.current?.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question.id, lang]);

  const startListening = () => {
    disarmBargeIn();
    stopSpeaking();
    setHeard("");
    setListening(true);
    handle.current = listen(
      lang,
      (spoken, final) => {
        if (spoken) setHeard(spoken);
        if (final) {
          setListening(false);
          if (spoken) onUtterance(spoken);
        }
      },
      () => setListening(false),
    );
  };

  listenRef.current = startListening;

  const stopListening = () => {
    handle.current?.stop();
    setListening(false);
  };

  const toggleMulti = (value: unknown) => {
    const exclusive = question.exclusive_value;
    setMulti((current) => {
      if (exclusive !== null && exclusive !== undefined && value === exclusive) {
        // "None of these" clears everything else — choosing it alongside symptoms is
        // a contradiction the patient did not mean.
        return current.includes(value) ? [] : [value];
      }
      const without = current.filter((v) => v !== exclusive);
      return without.includes(value)
        ? without.filter((v) => v !== value)
        : [...without, value];
    });
  };

  const columns = useMemo(() => {
    const n = question.options.length;
    if (n <= 2) return "grid-cols-2";
    if (n <= 4) return "grid-cols-2";
    if (n <= 6) return "grid-cols-3";
    if (n <= 9) return "grid-cols-3";
    return "grid-cols-4";
  }, [question.options.length]);

  const voiceOk = speechAvailable();

  return (
    <div className="flex h-full flex-col">
      {/* Progress. Deliberately not a number or a question count: "3 of 27" makes a
          four-minute interview feel like a form. A filling bar reads as "nearly there". */}
      <div className="h-3 w-full bg-black/5">
        <div
          className="h-full bg-[var(--color-brand)] transition-all duration-500"
          style={{ width: `${Math.max(4, progress.percent)}%` }}
        />
      </div>

      <div className="flex flex-1 flex-col overflow-hidden px-8 pt-6 pb-4">
        <h1 className="text-[2.6rem] leading-tight font-bold tracking-tight">
          {text(question.prompt)}
        </h1>
        {question.help && (
          <p className="mt-2 text-2xl text-black/55">{text(question.help)}</p>
        )}
        {question.type === "multi_choice" && (
          <p className="mt-1 text-xl font-semibold text-[var(--color-accent)]">
            {text(T.chooseMany)}
          </p>
        )}
        {question.self_report_proxy && (
          <p className="mt-1 text-lg text-black/40">{text(T.patientReported)}</p>
        )}

        <div className="mt-5 flex-1 overflow-y-auto">
          {/* ------------------------------------------------ choices */}
          {(question.type === "single_choice" ||
            question.type === "multi_choice" ||
            question.type === "boolean") && (
            <div className={`grid ${columns} gap-4 pb-4`}>
              {question.options.map((option) => {
                const selected = multi.includes(option.value);
                return (
                  <button
                    key={String(option.value)}
                    disabled={busy}
                    className={`tile flex flex-col items-center justify-center gap-3 p-4 text-center ${
                      selected ? "tile-selected" : ""
                    }`}
                    onClick={() =>
                      question.type === "multi_choice"
                        ? toggleMulti(option.value)
                        : onAnswer(option.value, "touch")
                    }
                  >
                    <Icon name={option.icon} className="h-16 w-16 text-[var(--color-brand)]" />
                    <span className="text-xl font-semibold leading-snug">
                      {text(option.label)}
                    </span>
                  </button>
                );
              })}
            </div>
          )}

          {/* ------------------------------------------------ scale
              Faces, not numbers. A 0-10 pain scale is an abstraction; a row of faces
              is something a non-reading patient can answer instantly. */}
          {question.type === "scale" && (
            <div>
              <div className="grid grid-cols-6 gap-3 sm:grid-cols-11">
                {Array.from({ length: (question.max ?? 10) - (question.min ?? 0) + 1 }, (_, i) => {
                  const value = (question.min ?? 0) + i;
                  const ratio = value / (question.max ?? 10);
                  const selected = scale === value;
                  return (
                    <button
                      key={value}
                      disabled={busy}
                      onClick={() => setScale(value)}
                      className={`tile flex flex-col items-center justify-center gap-1 p-2 ${
                        selected ? "tile-selected" : ""
                      }`}
                      style={{ minHeight: 110 }}
                    >
                      <FaceScale ratio={ratio} />
                      <span className="text-lg font-bold">{value}</span>
                    </button>
                  );
                })}
              </div>
              {question.anchors && (
                <div className="mt-2 flex justify-between text-lg text-black/50">
                  <span>{text(question.anchors.low)}</span>
                  <span>{text(question.anchors.high)}</span>
                </div>
              )}
            </div>
          )}

          {/* ------------------------------------------------ duration */}
          {question.type === "duration" && (
            <div className="space-y-4">
              <div className="grid grid-cols-6 gap-3">
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20].map((n) => (
                  <button
                    key={n}
                    disabled={busy}
                    onClick={() => setDurationN(n)}
                    className={`tile flex items-center justify-center text-3xl font-bold ${
                      durationN === n ? "tile-selected" : ""
                    }`}
                    style={{ minHeight: 96 }}
                  >
                    {n}
                  </button>
                ))}
              </div>
              <div className="grid grid-cols-5 gap-3">
                {question.units.map((unit) => (
                  <button
                    key={unit.value}
                    disabled={busy}
                    onClick={() => setDurationUnit(unit.value)}
                    className={`tile flex items-center justify-center text-2xl font-semibold ${
                      durationUnit === unit.value ? "tile-selected" : ""
                    }`}
                    style={{ minHeight: 96 }}
                  >
                    {text(unit.label)}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* ------------------------------------------------ free text
              Voice-first by design. Typing a paragraph on a kiosk keyboard is not
              something a 62-year-old will do standing up, so the touch path here is a
              skip button and the coded slots carry the clinical content regardless. */}
          {question.type === "text" && (
            <div className="rounded-2xl bg-white p-6 text-2xl min-h-[180px]">
              {heard ? (
                <p>{heard}</p>
              ) : (
                <p className="text-black/35">{text(T.speakNow)}</p>
              )}
            </div>
          )}
        </div>

        {/* ------------------------------------------------ action bar */}
        <div className="mt-4 flex items-center gap-4">
          {voiceOk && (
            <button
              onClick={listening ? stopListening : startListening}
              disabled={busy}
              className={`btn relative flex w-[88px] shrink-0 items-center justify-center ${
                listening ? "bg-[var(--color-alarm)] text-white" : "bg-white text-[var(--color-brand)]"
              }`}
              aria-label={text(T.speakNow)}
            >
              {listening && (
                <span className="absolute inset-0 animate-listening rounded-full bg-[var(--color-alarm)]" />
              )}
              <MicIcon />
            </button>
          )}

          <div className="min-w-0 flex-1 text-xl text-black/55">
            {listening ? (
              <span className="font-semibold text-[var(--color-alarm)]">
                {text(T.listening)} {heard && <span className="text-black/70">“{heard}”</span>}
              </span>
            ) : hint ? (
              <span className="font-semibold text-[var(--color-accent)]">{hint}</span>
            ) : (
              text(T.tapOrSpeak)
            )}
          </div>

          {question.skippable && (
            <button onClick={onSkip} disabled={busy} className="btn px-8 text-xl text-black/50">
              {text(T.skip)}
            </button>
          )}

          {question.type === "multi_choice" && (
            <button
              onClick={() => onAnswer(multi, "touch")}
              disabled={busy || multi.length === 0}
              className="btn bg-[var(--color-brand)] px-12 text-2xl text-white disabled:opacity-30"
            >
              {text(T.done)}
            </button>
          )}
          {question.type === "scale" && (
            <button
              onClick={() => onAnswer(scale, "touch")}
              disabled={busy || scale === null}
              className="btn bg-[var(--color-brand)] px-12 text-2xl text-white disabled:opacity-30"
            >
              {text(T.next)}
            </button>
          )}
          {question.type === "duration" && (
            <button
              onClick={() => onAnswer({ n: durationN, unit: durationUnit }, "touch")}
              disabled={busy || durationN === null || durationUnit === null}
              className="btn bg-[var(--color-brand)] px-12 text-2xl text-white disabled:opacity-30"
            >
              {text(T.next)}
            </button>
          )}
          {question.type === "text" && (
            <button
              onClick={() => onAnswer(heard || "", "voice")}
              disabled={busy || !heard}
              className="btn bg-[var(--color-brand)] px-12 text-2xl text-white disabled:opacity-30"
            >
              {text(T.next)}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function FaceScale({ ratio }: { ratio: number }) {
  // Mouth curves from a smile at 0 to a frown at 10. One drawing, parameterised, so
  // the eleven faces are visibly a sequence rather than eleven unrelated pictures.
  const curve = 14 - ratio * 12;
  return (
    <svg viewBox="0 0 32 32" className="h-11 w-11 text-[var(--color-brand)]" aria-hidden>
      <circle cx="16" cy="16" r="13" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="11.5" cy="13" r="1.6" fill="currentColor" />
      <circle cx="20.5" cy="13" r="1.6" fill="currentColor" />
      <path
        d={`M10 ${22 - (14 - curve) / 3} Q16 ${curve + 8} 22 ${22 - (14 - curve) / 3}`}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" className="relative h-11 w-11" aria-hidden>
      <rect x="9" y="3" width="6" height="11" rx="3" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
