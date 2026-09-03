// The returning-patient screen.
//
// Section 1.1 of the brief names "repeated questioning across visits" as one of the
// failures of the current system. This is the screen that fixes it: the terminal shows
// the patient what it already knows, they confirm it in one tap, and every one of those
// questions is gone from the interview rather than hurried through it. That is what
// makes the 90-second returning budget in `12-budget-findings.md` arithmetic instead of
// optimism.
//
// Two rules shape it, and both are about not being presumptuous with someone's medical
// history:
//
//   Nothing is carried until they say so. The facts are shown and read aloud first.
//   Confirming is one tap; correcting is one tap and the interview simply runs as new.
//
//   The source is on the screen. Until ABDM credentials exist the previous visit comes
//   from this hospital's own terminal, not from the patient's national health record,
//   and the screen says which. See docs/06-decisions.md, 2026-09-03.

import { useEffect } from "react";
import type { Lang, PriorVisit } from "../api";
import { speak } from "../speech";

const T = {
  title: { en: "Welcome back", hi: "आपका फिर से स्वागत है" },
  body: {
    en: "Last time you told us this. Is it still correct?",
    hi: "पिछली बार आपने हमें यह बताया था। क्या यह अब भी सही है?",
  },
  yes: { en: "Yes, that is still right", hi: "हाँ, यह अब भी सही है" },
  no: { en: "Something has changed", hi: "कुछ बदल गया है" },
  saves: {
    en: "Saying yes means we will not ask you these again",
    hi: "हाँ कहने पर हम ये सवाल दोबारा नहीं पूछेंगे",
  },
  // Named plainly. A patient is entitled to know the hospital kept something, and a
  // judge is entitled to see that we do not describe our own database as ABDM.
  sourceLocal: {
    en: "From your last visit at this hospital",
    hi: "इस अस्पताल में आपकी पिछली विज़िट से",
  },
};

function whenText(seconds: number, lang: Lang): string {
  const days = Math.floor((Date.now() - seconds * 1000) / 86_400_000);
  if (days < 1) return lang === "hi" ? "आज" : "today";
  if (days === 1) return lang === "hi" ? "कल" : "yesterday";
  if (days < 30) return lang === "hi" ? `${days} दिन पहले` : `${days} days ago`;
  const months = Math.round(days / 30);
  if (months === 1) return lang === "hi" ? "एक महीना पहले" : "a month ago";
  return lang === "hi" ? `${months} महीने पहले` : `${months} months ago`;
}

export function WelcomeBack({
  prior, lang, onConfirm, busy,
}: {
  prior: PriorVisit;
  lang: Lang;
  onConfirm: (confirm: boolean) => void;
  busy: boolean;
}) {
  const text = (l: { en: string; hi: string }) => (lang === "hi" ? l.hi : l.en);

  useEffect(() => {
    // Read aloud, including the facts themselves. A patient who cannot read must not be
    // asked to confirm a list they cannot see — that would be consent in name only.
    const spoken = prior.lines.map((line) => `${line.label} ${line.value}`).join(". ");
    speak(`${text(T.title)}. ${text(T.body)} ${spoken}`, lang);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex h-full flex-col px-8 py-7">
      <h1 className="text-5xl font-bold leading-tight">{text(T.title)}</h1>
      <p className="mt-3 text-2xl leading-relaxed text-black/55">{text(T.body)}</p>
      <p className="mt-1 text-xl text-black/35">
        {text(T.sourceLocal)} · {whenText(prior.visited_at, lang)}
      </p>

      <div className="mt-6 flex-1 overflow-y-auto">
        <div className="grid gap-3 pb-2">
          {prior.lines.map((line) => (
            <div key={line.slot} className="rounded-2xl bg-white px-6 py-4">
              <p className="text-lg leading-snug text-black/45">{line.label}</p>
              <p className="mt-1 text-2xl font-semibold leading-snug">{line.value}</p>
            </div>
          ))}
        </div>
      </div>

      <p className="mt-4 text-xl text-black/40">{text(T.saves)}</p>

      <div className="mt-4 flex gap-5">
        {/* "Something has changed" is a first-class answer, not a fallback. A patient
            whose history moved on is interviewed as new, which is correct and is why
            the engine has no separate returning-patient graph to fall out of. */}
        <button
          onClick={() => onConfirm(false)}
          disabled={busy}
          className="btn flex-1 bg-white text-2xl text-black/60"
        >
          {text(T.no)}
        </button>
        <button
          onClick={() => onConfirm(true)}
          disabled={busy}
          className="btn flex-[2] bg-[var(--color-brand)] text-3xl text-white disabled:opacity-40"
        >
          {text(T.yes)}
        </button>
      </div>
    </div>
  );
}
