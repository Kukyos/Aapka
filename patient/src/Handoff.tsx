// The phone handoff.
//
// There are more people in an OPD queue than there will ever be terminals.
// `docs/12-budget-findings.md` puts a number on it and calls that number the weakest
// one in the project: 84 kiosks for a 5,000-patient hospital. A patient who fills the
// intake in on their own phone, from the bench, occupies none of them.
//
// Gate G1 is why this is a corner of the attract screen and not the attract screen.
// The brief rejects the smartphone as the main route in and permits it only as "a
// secondary convenience". So the wording is always "or scan this", never "scan this
// instead", and a patient carrying nothing walks up and touches the screen exactly as
// before. Nothing here is enrolment: scanning opens the same anonymous, temporary
// session, with no account and no install, and it is wiped on submission like any
// other.

import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { api, type Lang } from "./api";

const T = {
  offer: {
    en: "Or use your own phone — point its camera here",
    hi: "या अपना फ़ोन इस्तेमाल कीजिए — कैमरा यहाँ रखिए",
  },
  papers: {
    en: "On a phone, bring your papers to the counter",
    hi: "फ़ोन पर, अपने काग़ज़ काउंटर पर लाइए",
  },
};

export function Handoff({ lang }: { lang: Lang }) {
  const [png, setPng] = useState<string | null>(null);
  const [secure, setSecure] = useState(true);

  useEffect(() => {
    let live = true;
    api
      .handoff()
      .then(async ({ url, secure: isSecure }) => {
        if (!live || !url) return;
        setSecure(isSecure);
        // High error correction: this is a code on a screen in a bright waiting hall,
        // read by a cheap phone camera held at an angle.
        setPng(
          await QRCode.toDataURL(url, {
            errorCorrectionLevel: "H",
            margin: 1,
            width: 320,
            color: { dark: "#000000", light: "#ffffff" },
          }),
        );
      })
      // No QR is a correct outcome, not an error: the terminal in front of them works.
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  if (!png) return null;

  const text = (l: { en: string; hi: string }) => (lang === "hi" ? l.hi : l.en);

  return (
    <div className="flex items-center gap-5 rounded-2xl bg-white p-5 shadow-lg">
      <img src={png} alt="" className="h-32 w-32" />
      <div className="max-w-[16rem]">
        <p className="text-xl font-semibold leading-snug text-black">{text(T.offer)}</p>
        {/* Over plain HTTP the phone gets no camera, so the document step cannot run
            there. Saying so on the kiosk is cheaper than a patient discovering it
            halfway through. D-16 in docs/11-deferred.md. */}
        {!secure && (
          <p className="mt-2 text-base leading-snug text-black/45">
            {text(T.papers)}
          </p>
        )}
      </div>
    </div>
  );
}
