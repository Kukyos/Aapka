// Brief 3.4 Step 1 — Identify.
//
// The patient holds their ABHA card to the camera, or says they do not have one.
// **Both paths are first-class.** Gate G1 is explicit that the primary flow must work
// for a walk-in, first-visit patient carrying nothing, so "I don't have one" is a
// recorded answer that leads to an identical interview — never a lesser path, never a
// blocked one.
//
// The card is read with the same OCR ladder the document pipeline uses, then matched
// against the 14-digit ABHA pattern. A miss is not an error: try the card again, or
// carry on without it.

import { useEffect, useRef, useState } from "react";
import { api, type Lang, type PriorVisit } from "../api";
import { speak } from "../speech";

const T = {
  title: { en: "Do you have a health ID card?", hi: "क्या आपके पास हेल्थ आईडी कार्ड है?" },
  body: {
    en: "If you have an ABHA card, hold it up to the camera. If you do not have one, that is completely fine.",
    hi: "अगर आपके पास आभा कार्ड है तो उसे कैमरे के सामने रखिए। अगर नहीं है तो भी कोई बात नहीं।",
  },
  scan: { en: "Read my card", hi: "मेरा कार्ड पढ़िए" },
  none: { en: "I do not have one", hi: "मेरे पास नहीं है" },
  reading: { en: "Reading the card…", hi: "कार्ड पढ़ रहे हैं…" },
  found: { en: "Card read. Thank you.", hi: "कार्ड पढ़ लिया। धन्यवाद।" },
  notFound: {
    en: "We could not read the card. Hold it flatter, or carry on without it.",
    hi: "कार्ड पढ़ नहीं पाए। इसे सीधा रखिए, या इसके बिना ही आगे बढ़िए।",
  },
  carryOn: { en: "Carry on without it", hi: "इसके बिना आगे बढ़िए" },
  noCamera: { en: "No camera on this terminal", hi: "इस टर्मिनल पर कैमरा नहीं है" },
};

export function Identify({
  sessionId, lang, onDone,
}: { sessionId: string; lang: Lang; onDone: (prior?: PriorVisit | null) => void }) {
  const video = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [reading, setReading] = useState(false);
  const [outcome, setOutcome] = useState<"idle" | "found" | "missed">("idle");
  const text = (l: { en: string; hi: string }) => (lang === "hi" ? l.hi : l.en);

  useEffect(() => {
    let active = true;
    navigator.mediaDevices
      ?.getUserMedia({ video: { facingMode: "environment", width: 1280, height: 720 } })
      .then((got) => {
        if (!active) {
          got.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = got;
        if (video.current) video.current.srcObject = got;
      })
      .catch(() => {
        streamRef.current = null;
      });
    speak(`${text(T.title)} ${text(T.body)}`, lang);
    return () => {
      active = false;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const scan = async () => {
    if (!video.current || !streamRef.current) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.current.videoWidth;
    canvas.height = video.current.videoHeight;
    canvas.getContext("2d")?.drawImage(video.current, 0, 0);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", 0.92),
    );
    if (!blob) return;
    setReading(true);
    try {
      const result = await api.scanAbha(sessionId, blob);
      if (result?.found) {
        setOutcome("found");
        speak(text(T.found), lang);
        // The card may be one we have seen before. Handing that up rather than acting
        // on it here keeps the decision with the patient one screen later.
        const prior = result.prior_visit ?? null;
        window.setTimeout(() => onDone(prior), 1400);
      } else {
        setOutcome("missed");
        speak(text(T.notFound), lang);
      }
    } catch {
      setOutcome("missed");
    } finally {
      setReading(false);
    }
  };

  const withoutCard = async () => {
    // Recorded, not skipped. The doctor screen and the FHIR bundle both need to know
    // this patient has no ABHA rather than that we forgot to ask.
    await api.abha(sessionId, { declined: true }).catch(() => {});
    onDone(null);
  };

  return (
    <div className="flex h-full flex-col px-8 py-7">
      <h1 className="text-5xl font-bold leading-tight">{text(T.title)}</h1>
      <p className="mt-3 max-w-4xl text-2xl leading-relaxed text-black/55">{text(T.body)}</p>

      <div className="mt-6 flex flex-1 items-center justify-center overflow-hidden">
        <div className="relative h-full w-full max-w-4xl overflow-hidden rounded-3xl bg-black">
          {streamRef.current || video.current?.srcObject ? (
            <video ref={video} autoPlay playsInline muted className="h-full w-full object-cover" />
          ) : (
            <video ref={video} autoPlay playsInline muted className="h-full w-full object-cover" />
          )}
          {/* A card-shaped guide, not a full-frame one. Told where to hold it, people
              hold it there; left to guess, they hold it too close and too crooked. */}
          <div className="pointer-events-none absolute left-1/2 top-1/2 h-[46%] w-[72%] -translate-x-1/2 -translate-y-1/2 rounded-2xl border-4 border-dashed border-white/70" />
          {reading && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/65 text-3xl font-bold text-white">
              {text(T.reading)}
            </div>
          )}
          {outcome === "found" && (
            <div className="absolute inset-0 flex items-center justify-center bg-[var(--color-brand)]/85 text-4xl font-bold text-white">
              {text(T.found)}
            </div>
          )}
        </div>
      </div>

      {outcome === "missed" && (
        <p className="mt-4 text-center text-2xl font-semibold text-[var(--color-accent)]">
          {text(T.notFound)}
        </p>
      )}

      <div className="mt-6 flex gap-5">
        <button
          onClick={scan}
          disabled={reading}
          className="btn flex-[2] bg-[var(--color-brand)] text-3xl text-white disabled:opacity-40"
        >
          {text(T.scan)}
        </button>
        <button onClick={withoutCard} className="btn flex-1 bg-white text-2xl text-[var(--color-brand)]">
          {outcome === "missed" ? text(T.carryOn) : text(T.none)}
        </button>
      </div>
    </div>
  );
}
