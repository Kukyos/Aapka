// The read-back.
//
// Module C in the brief asks for "patient-facing audio confirmation in local language".
// This is it: before anything is sent, the terminal reads back what it understood and
// gives the patient a chance to say it is wrong.
//
// Why it earns its seconds: this is the only point in the whole flow where the patient
// can correct the machine. Everything before it is the machine asking; everything after
// it is a doctor reading. A patient who hears "burning pain in the upper stomach for
// three weeks" and knows it is actually two days can say so here, and nowhere else.
//
// It is read aloud automatically, line by line, because the audience for this screen is
// specifically the person who cannot read it.

import { useEffect, useMemo, useState } from "react";
import { api, type Lang } from "../api";
import { speak, stopSpeaking } from "../speech";

const T = {
  title: { en: "This is what we understood", hi: "हमने यह समझा है" },
  body: {
    en: "Listen, and tell us if anything is wrong. Your doctor will see this.",
    hi: "सुनिए, और अगर कुछ ग़लत हो तो बताइए। आपके डॉक्टर यही देखेंगे।",
  },
  correct: { en: "Yes, that is right", hi: "हाँ, यह सही है" },
  wrong: { en: "Something is wrong", hi: "कुछ ग़लत है" },
  replay: { en: "Read it again", hi: "फिर से पढ़िए" },
  flagged: {
    en: "Thank you. We have marked this for the doctor to check with you.",
    hi: "धन्यवाद। हमने डॉक्टर के लिए यह निशान लगा दिया है कि वे आपसे पूछ लें।",
  },
  loading: { en: "One moment…", hi: "एक पल…" },
};

// Only the sections a patient can meaningfully confirm. Reading the full Dashavidha
// block back to someone standing in a queue would cost forty seconds and confirm
// nothing — they answered those questions two minutes ago and have no way to check
// our wording of them.
const READ_BACK = ["cc", "hpi", "past", "drugs"];

export function Review({
  sessionId, lang, onConfirm,
}: {
  sessionId: string;
  lang: Lang;
  onConfirm: (patientDisputed: boolean) => void;
}) {
  const [sections, setSections] = useState<{ key: string; title: string; lines: string[] }[]>([]);
  const [loading, setLoading] = useState(true);
  const [disputed, setDisputed] = useState(false);
  const text = (l: { en: string; hi: string }) => (lang === "hi" ? l.hi : l.en);

  useEffect(() => {
    api
      .summary(sessionId)
      .then((body) => {
        setSections(
          body.sections.filter((s) => READ_BACK.includes(s.key) && s.lines.length > 0),
        );
      })
      .catch(() => setSections([]))
      .finally(() => setLoading(false));
    return stopSpeaking;
  }, [sessionId]);

  const spoken = useMemo(
    () =>
      sections
        .flatMap((section) => section.lines)
        .map((line) => line.replace(/^\s+/, "").replace(/[·—]/g, ","))
        .join(". "),
    [sections],
  );

  useEffect(() => {
    if (!loading && spoken) speak(`${text(T.title)}. ${spoken}`, lang);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, spoken]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-3xl text-black/40">
        {text(T.loading)}
      </div>
    );
  }

  if (disputed) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-12 text-center">
        <p className="max-w-3xl text-4xl font-semibold leading-snug">{text(T.flagged)}</p>
        <button
          onClick={() => onConfirm(true)}
          className="btn mt-12 bg-[var(--color-brand)] px-20 text-3xl text-white"
        >
          {lang === "hi" ? "ठीक है" : "All right"}
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col px-8 py-7">
      <h1 className="text-5xl font-bold">{text(T.title)}</h1>
      <p className="mt-2 text-2xl text-black/55">{text(T.body)}</p>

      <div className="mt-6 flex-1 overflow-y-auto">
        {sections.map((section) => (
          <section key={section.key} className="mb-6">
            <h2 className="text-lg font-bold uppercase tracking-wider text-black/35">
              {section.title}
            </h2>
            <ul className="mt-1.5 space-y-1.5">
              {section.lines.map((line, i) => (
                <li key={i} className="text-3xl leading-snug">
                  {line.trim()}
                </li>
              ))}
            </ul>
          </section>
        ))}
        {sections.length === 0 && (
          <p className="text-2xl text-black/40">
            {lang === "hi" ? "कुछ दर्ज नहीं हुआ।" : "Nothing was recorded."}
          </p>
        )}
      </div>

      <div className="mt-5 flex items-center gap-5">
        <button
          onClick={() => speak(spoken, lang)}
          className="btn bg-white px-10 text-xl text-[var(--color-brand)]"
        >
          {text(T.replay)}
        </button>
        <button
          onClick={() => setDisputed(true)}
          className="btn flex-1 bg-white text-2xl text-[var(--color-accent)]"
        >
          {text(T.wrong)}
        </button>
        <button
          onClick={() => onConfirm(false)}
          className="btn flex-[2] bg-[var(--color-brand)] text-3xl text-white"
        >
          {text(T.correct)}
        </button>
      </div>
    </div>
  );
}
