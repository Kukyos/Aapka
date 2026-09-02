// The kiosk shell and its state machine.
//
//   attract -> language -> consent -> interview -> documents -> done
//                                          |
//                                          +-> escalate   (red flag; interview over)
//
// Two rules run underneath every screen:
//
//   Inactivity resets the terminal (R3). A public machine used by strangers back to
//   back must never show the previous person's answers, so a timeout discards the
//   session rather than parking it.
//
//   Every prompt is spoken (G2). A patient who cannot read a single word on this
//   screen can still complete the whole intake.

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Action, type Lang, type Question } from "./api";
import { Icon } from "./Icon";
import { QuestionScreen } from "./QuestionScreen";
import { speak, stopSpeaking, warmVoices } from "./speech";

type Stage = "attract" | "language" | "consent" | "interview" | "documents" | "done" | "escalate";

const IDLE_RESET_MS = 90_000;

const T = {
  welcome: { en: "Namaste. Touch anywhere to begin.", hi: "नमस्ते। शुरू करने के लिए कहीं भी छूइए।" },
  chooseLanguage: { en: "Choose your language", hi: "अपनी भाषा चुनिए" },
  consentTitle: { en: "May we ask you some questions?", hi: "क्या हम आपसे कुछ सवाल पूछ सकते हैं?" },
  consentBody: {
    en: "We will ask about your health and show what you tell us to your doctor. Nothing is kept on this machine afterwards. You can stop at any time.",
    hi: "हम आपकी सेहत के बारे में पूछेंगे और जो आप बताएँगे वह आपके डॉक्टर को दिखाएँगे। बाद में इस मशीन में कुछ नहीं रहेगा। आप कभी भी रोक सकते हैं।",
  },
  agree: { en: "Yes, go ahead", hi: "हाँ, पूछिए" },
  decline: { en: "No, thank you", hi: "नहीं, धन्यवाद" },
  docsTitle: { en: "Do you have any old papers with you?", hi: "क्या आपके पास कोई पुराने काग़ज़ हैं?" },
  docsBody: {
    en: "Hold each paper up to the camera. Crumpled and handwritten is fine.",
    hi: "हर काग़ज़ कैमरे के सामने रखिए। मुड़े हुए और हाथ से लिखे काग़ज़ भी चलेंगे।",
  },
  capture: { en: "Take the picture", hi: "फ़ोटो लीजिए" },
  addAnother: { en: "Add another paper", hi: "एक और काग़ज़" },
  finish: { en: "I am finished", hi: "मेरा हो गया" },
  noPapers: { en: "I have no papers", hi: "मेरे पास काग़ज़ नहीं हैं" },
  reading: { en: "Reading the paper…", hi: "काग़ज़ पढ़ रहे हैं…" },
  thankYou: { en: "Thank you. Please wait for your number to be called.", hi: "धन्यवाद। कृपया अपने नंबर का इंतज़ार कीजिए।" },
  wiped: { en: "Your answers have been sent to the doctor and cleared from this screen.", hi: "आपके जवाब डॉक्टर को भेज दिए गए हैं और इस स्क्रीन से हटा दिए गए हैं।" },
  goToStaff: { en: "Please go to the staff desk now", hi: "कृपया अभी स्टाफ़ काउंटर पर जाइए" },
  starting: { en: "One moment…", hi: "एक पल…" },
  problem: { en: "Something went wrong. Please see the staff desk.", hi: "कुछ गड़बड़ हो गई। कृपया स्टाफ़ काउंटर पर जाइए।" },
};

export default function App() {
  const [stage, setStage] = useState<Stage>("attract");
  const [lang, setLang] = useState<Lang>("hi");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [progress, setProgress] = useState({ percent: 0, answered: 0 });
  const [redFlag, setRedFlag] = useState<Action["red_flag"]>(null);
  const [busy, setBusy] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const idle = useRef<number | null>(null);

  const text = (l: { en: string; hi: string }) => (lang === "hi" ? l.hi : l.en);

  useEffect(warmVoices, []);

  // ---------------------------------------------------------------- idle reset
  const reset = useCallback(() => {
    stopSpeaking();
    if (sessionId && stage !== "done" && stage !== "attract") {
      // Requirement R2: an abandoned half-history is worse than none, so it is
      // discarded rather than forwarded.
      void api.abandon(sessionId);
    }
    setSessionId(null);
    setQuestion(null);
    setRedFlag(null);
    setProgress({ percent: 0, answered: 0 });
    setHint(null);
    setError(false);
    setStage("attract");
  }, [sessionId, stage]);

  useEffect(() => {
    const bump = () => {
      if (idle.current) window.clearTimeout(idle.current);
      if (stage === "attract") return;
      idle.current = window.setTimeout(reset, IDLE_RESET_MS);
    };
    bump();
    const events: (keyof WindowEventMap)[] = ["pointerdown", "keydown"];
    events.forEach((e) => window.addEventListener(e, bump));
    return () => {
      events.forEach((e) => window.removeEventListener(e, bump));
      if (idle.current) window.clearTimeout(idle.current);
    };
  }, [stage, reset]);

  // ---------------------------------------------------------------- flow
  const applyAction = (action: Action) => {
    setProgress({ percent: action.progress.percent, answered: action.progress.answered });
    if (action.action === "escalate") {
      setRedFlag(action.red_flag);
      setQuestion(null);
      setStage("escalate");
      stopSpeaking();
      // Spoken immediately and unprompted. Someone who cannot read the warning must
      // still hear it.
      if (action.red_flag) speak(action.red_flag.instruction, lang);
      return;
    }
    if (action.action === "complete") {
      setQuestion(null);
      setStage("documents");
      return;
    }
    setQuestion(action.question);
  };

  const begin = async (chosen: Lang) => {
    setLang(chosen);
    setStage("consent");
    speak(text(T.consentTitle) + " " + (chosen === "hi" ? T.consentBody.hi : T.consentBody.en), chosen);
  };

  const accept = async () => {
    setBusy(true);
    try {
      const created = await api.createSession(lang, "ayush");
      setSessionId(created.session_id);
      await api.consent(created.session_id, {
        capture: true,
        share_with_hospital: true,
        link_to_abha: false,
        audio_played: true,
      });
      applyAction(await api.next(created.session_id));
      setStage("interview");
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  const submitAnswer = async (value: unknown, source: string) => {
    if (!sessionId || !question) return;
    setBusy(true);
    setHint(null);
    try {
      applyAction(await api.answer(sessionId, { node_id: question.id, value, source }));
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  const submitUtterance = async (utterance: string) => {
    if (!sessionId || !question) return;
    setBusy(true);
    try {
      const action = await api.answer(sessionId, {
        node_id: question.id,
        utterance,
        source: "voice",
      });
      if (action.accepted === false) {
        // The NLU said unclear rather than guessing. Ask again — a worse interview,
        // never a wrong one.
        const message = lang === "hi"
          ? "माफ़ कीजिए, समझ नहीं आया। फिर से बोलिए, या जवाब छूइए।"
          : "Sorry, I did not catch that. Please try again, or tap an answer.";
        setHint(message);
        speak(message, lang);
        return;
      }
      applyAction(action);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  const skip = async () => {
    if (!sessionId || !question) return;
    setBusy(true);
    try {
      applyAction(await api.skip(sessionId, question.id));
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  const finish = async () => {
    if (!sessionId) return;
    setBusy(true);
    try {
      await api.submit(sessionId);
      setStage("done");
      speak(text(T.thankYou), lang);
      window.setTimeout(reset, 12_000);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  // ---------------------------------------------------------------- render
  if (error) {
    return (
      <Centered>
        <p className="text-4xl font-bold text-[var(--color-alarm)]">{text(T.problem)}</p>
        <button onClick={reset} className="btn mt-10 bg-[var(--color-brand)] px-16 text-2xl text-white">
          ↻
        </button>
      </Centered>
    );
  }

  if (stage === "attract") {
    return (
      <button
        onClick={() => setStage("language")}
        className="flex h-full w-full flex-col items-center justify-center gap-10 bg-[var(--color-brand)] text-white"
      >
        <div className="animate-tap-hint">
          <HandIcon />
        </div>
        <p className="text-6xl font-bold">नमस्ते</p>
        <p className="max-w-3xl px-10 text-center text-4xl leading-snug opacity-90">
          {T.welcome.hi}
        </p>
        <p className="max-w-3xl px-10 text-center text-3xl leading-snug opacity-70">
          {T.welcome.en}
        </p>
      </button>
    );
  }

  if (stage === "language") {
    return (
      <Centered>
        <h1 className="mb-12 text-center text-5xl font-bold">
          अपनी भाषा चुनिए
          <span className="mt-2 block text-3xl font-normal text-black/50">
            Choose your language
          </span>
        </h1>
        <div className="grid w-full max-w-4xl grid-cols-2 gap-8">
          {([
            { code: "hi" as Lang, native: "हिंदी", english: "Hindi" },
            { code: "en" as Lang, native: "English", english: "English" },
          ]).map((option) => (
            <button
              key={option.code}
              // Each language is spoken aloud on hover/press so a non-reader can find
              // their own without reading any of the others.
              onPointerDown={() => speak(option.native, option.code)}
              onClick={() => begin(option.code)}
              className="tile flex flex-col items-center justify-center gap-3 p-10"
              style={{ minHeight: 220 }}
            >
              <span className="text-5xl font-bold">{option.native}</span>
              <span className="text-2xl text-black/45">{option.english}</span>
            </button>
          ))}
        </div>
      </Centered>
    );
  }

  if (stage === "consent") {
    return (
      <Centered>
        <h1 className="max-w-4xl text-center text-5xl font-bold leading-tight">
          {text(T.consentTitle)}
        </h1>
        <p className="mt-8 max-w-3xl text-center text-3xl leading-relaxed text-black/65">
          {text(T.consentBody)}
        </p>
        <button
          onClick={() => speak(text(T.consentBody), lang)}
          className="btn mt-6 flex items-center gap-3 px-8 text-xl text-[var(--color-brand)]"
        >
          <SpeakerIcon /> {lang === "hi" ? "फिर से सुनिए" : "Listen again"}
        </button>
        <div className="mt-12 flex w-full max-w-3xl gap-6">
          <button onClick={reset} className="btn flex-1 bg-white text-2xl text-black/60">
            {text(T.decline)}
          </button>
          <button
            onClick={accept}
            disabled={busy}
            className="btn flex-[2] bg-[var(--color-brand)] text-3xl text-white"
          >
            {busy ? text(T.starting) : text(T.agree)}
          </button>
        </div>
      </Centered>
    );
  }

  if (stage === "interview" && question) {
    return (
      <QuestionScreen
        question={question}
        lang={lang}
        progress={progress}
        onAnswer={submitAnswer}
        onUtterance={submitUtterance}
        onSkip={skip}
        busy={busy}
        hint={hint}
      />
    );
  }

  if (stage === "escalate" && redFlag) {
    return (
      <div className="flex h-full flex-col items-center justify-center bg-[var(--color-alarm-soft)] px-10 text-center">
        <div className="text-[var(--color-alarm)]">
          <AlertIcon />
        </div>
        {/* No disease is named here, on screen or in the staff alert. Hard rule 1:
            this tells a person what to DO. */}
        <h1 className="mt-8 max-w-4xl text-6xl font-bold leading-tight text-[var(--color-alarm)]">
          {redFlag.instruction}
        </h1>
        <p className="mt-8 max-w-3xl text-3xl text-black/60">{redFlag.label}</p>
        <p className="mt-12 text-2xl text-black/40">
          {lang === "hi" ? "स्टाफ़ को सूचित कर दिया गया है।" : "The staff have been told."}
        </p>
      </div>
    );
  }

  if (stage === "documents") {
    return <DocumentsScreen sessionId={sessionId!} lang={lang} onFinish={finish} busy={busy} />;
  }

  if (stage === "done") {
    return (
      <Centered>
        <div className="text-[var(--color-brand)]">
          <TickIcon />
        </div>
        <h1 className="mt-8 max-w-4xl text-center text-5xl font-bold leading-tight">
          {text(T.thankYou)}
        </h1>
        <p className="mt-8 max-w-3xl text-center text-2xl text-black/50">{text(T.wiped)}</p>
      </Centered>
    );
  }

  return <Centered><p className="text-3xl text-black/40">{text(T.starting)}</p></Centered>;
}

// ---------------------------------------------------------------- documents

function DocumentsScreen({
  sessionId, lang, onFinish, busy,
}: { sessionId: string; lang: Lang; onFinish: () => void; busy: boolean }) {
  const video = useRef<HTMLVideoElement | null>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [captured, setCaptured] = useState<{ kind: string; date: string | null; meds: number }[]>([]);
  const [reading, setReading] = useState(false);
  const text = (l: { en: string; hi: string }) => (lang === "hi" ? l.hi : l.en);

  useEffect(() => {
    let active = true;
    navigator.mediaDevices
      ?.getUserMedia({ video: { facingMode: "environment", width: 1920, height: 1080 } })
      .then((got) => {
        if (!active) {
          got.getTracks().forEach((t) => t.stop());
          return;
        }
        setStream(got);
        if (video.current) video.current.srcObject = got;
      })
      .catch(() => setStream(null));
    speak(text(T.docsTitle) + " " + text(T.docsBody), lang);
    return () => {
      active = false;
      stream?.getTracks().forEach((t) => t.stop());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const capture = async () => {
    if (!video.current) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.current.videoWidth;
    canvas.height = video.current.videoHeight;
    canvas.getContext("2d")?.drawImage(video.current, 0, 0);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", 0.9),
    );
    if (!blob) return;
    setReading(true);
    try {
      const result = await api.document(sessionId, blob);
      if (result?.ok) {
        setCaptured((c) => [
          ...c,
          { kind: result.kind, date: result.date, meds: (result.medications ?? []).length },
        ]);
      }
    } finally {
      setReading(false);
    }
  };

  return (
    <div className="flex h-full flex-col px-8 py-6">
      <h1 className="text-4xl font-bold">{text(T.docsTitle)}</h1>
      <p className="mt-2 text-2xl text-black/55">{text(T.docsBody)}</p>

      <div className="mt-5 flex flex-1 gap-6 overflow-hidden">
        <div className="relative flex-1 overflow-hidden rounded-3xl bg-black">
          {stream ? (
            <video ref={video} autoPlay playsInline muted className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full items-center justify-center text-2xl text-white/50">
              {lang === "hi" ? "कैमरा उपलब्ध नहीं है" : "No camera available"}
            </div>
          )}
          {/* Framing guide. A patient holding a crumpled paper at arm's length needs to
              be told where to put it, not left to guess. */}
          <div className="pointer-events-none absolute inset-8 rounded-2xl border-4 border-dashed border-white/60" />
          {reading && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/60 text-3xl font-bold text-white">
              {text(T.reading)}
            </div>
          )}
        </div>

        <div className="w-80 shrink-0 overflow-y-auto">
          {captured.map((doc, i) => (
            <div key={i} className="tile mb-3 flex items-center gap-3 p-4" style={{ minHeight: 90 }}>
              <Icon name="doc-papers" className="h-10 w-10 text-[var(--color-brand)]" />
              <div className="text-left">
                <p className="text-lg font-semibold">{doc.kind.replace(/_/g, " ")}</p>
                <p className="text-base text-black/45">
                  {doc.date ?? "—"} · {doc.meds} {lang === "hi" ? "दवाएँ" : "medicines"}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-5 flex gap-5">
        <button
          onClick={capture}
          disabled={!stream || reading}
          className="btn flex-[2] bg-[var(--color-brand)] text-3xl text-white disabled:opacity-30"
        >
          {captured.length ? text(T.addAnother) : text(T.capture)}
        </button>
        <button
          onClick={onFinish}
          disabled={busy}
          className="btn flex-1 bg-white text-2xl text-[var(--color-brand)]"
        >
          {captured.length ? text(T.finish) : text(T.noPapers)}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- bits

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-10">{children}</div>
  );
}

function HandIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-32 w-32" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 11V5.5a1.5 1.5 0 0 1 3 0V11m0-1.5a1.5 1.5 0 0 1 3 0V12m0-1a1.5 1.5 0 0 1 3 0v5a5 5 0 0 1-5 5h-2a5 5 0 0 1-4.3-2.4L6 16c-.6-1 .3-2.2 1.4-1.7L9 15" />
    </svg>
  );
}

function SpeakerIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-8 w-8" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round">
      <path d="M4 9v6h4l5 4V5L8 9z" />
      <path d="M16.5 9.5a3.5 3.5 0 0 1 0 5M19 7a7 7 0 0 1 0 10" />
    </svg>
  );
}

function AlertIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-40 w-40" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
      <path d="M12 3l9 17H3z" />
      <path d="M12 10v5" />
      <circle cx="12" cy="17.5" r=".9" fill="currentColor" />
    </svg>
  );
}

function TickIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-36 w-36" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M7.5 12.5l3 3 6-6.5" />
    </svg>
  );
}
