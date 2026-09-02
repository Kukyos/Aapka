// The icon set.
//
// Every option in the ontology carries an `icon` key and this resolves it. The brief
// requires an "intuitive icon-driven UI" for low-literacy users, and gate G2 means the
// picture has to be there on every option, not most of them.
//
// These are geometric line drawings, not illustrations. They are honest placeholders
// with a known ceiling: a real icon set for a non-reading audience is a design task,
// needs testing on actual patients, and is listed in 07-build-plan.md Phase 2 and
// docs/11-deferred.md D-11. What matters now is that the key resolves, the shape is
// distinguishable at arm's length, and nothing renders blank.
//
// Unknown keys fall back to a lettered disc rather than to nothing, so a missing icon
// is visible in testing instead of silently degrading the touch path.

type Props = { name: string | null; className?: string };

const S = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

const PATHS: Record<string, JSX.Element> = {
  // ---- body regions
  "body-abdomen": <><circle cx="12" cy="13" r="7" {...S} /><path d="M9 11h6M9 15h6" {...S} /></>,
  "body-chest": <><path d="M6 7h12v6a6 6 0 0 1-12 0z" {...S} /><path d="M12 9v6" {...S} /></>,
  "body-head": <><circle cx="12" cy="10" r="6" {...S} /><path d="M8 20h8" {...S} /></>,
  "body-joint": <><circle cx="9" cy="9" r="3" {...S} /><circle cx="15" cy="15" r="3" {...S} /><path d="M11 11l2 2" {...S} /></>,
  "body-lungs": <><path d="M12 4v10" {...S} /><path d="M12 8c-4 0-6 3-6 7 0 2 3 3 4 1l2-4" {...S} /><path d="M12 8c4 0 6 3 6 7 0 2-3 3-4 1l-2-4" {...S} /></>,
  "body-skin": <><rect x="5" y="5" width="14" height="14" rx="3" {...S} /><circle cx="9" cy="10" r="1.2" {...S} /><circle cx="14" cy="14" r="1.2" {...S} /><circle cx="15" cy="9" r="1" {...S} /></>,
  "body-urinary": <><path d="M8 6h8l-1 8a3 3 0 0 1-6 0z" {...S} /><path d="M12 17v3" {...S} /></>,
  "body-menstrual": <><circle cx="12" cy="10" r="5" {...S} /><path d="M12 15v6M9 18h6" {...S} /></>,

  // ---- symptoms
  "symptom-fever": <><path d="M10 4h2a2 2 0 0 1 2 2v8a4 4 0 1 1-6 0V6a2 2 0 0 1 2-2z" {...S} /><circle cx="11" cy="17" r="2" fill="currentColor" /></>,
  "symptom-cough": <><path d="M4 12a5 5 0 0 1 10 0" {...S} /><path d="M16 9l3-1M17 12h3M16 15l3 1" {...S} /></>,
  "symptom-weak": <><path d="M12 5v8M8 20l4-7 4 7" {...S} /><path d="M7 9l5 2 5-2" {...S} /></>,
  "symptom-digestion": <><path d="M7 6v6a5 5 0 0 0 10 0V9" {...S} /><path d="M12 17v3" {...S} /></>,
  "symptom-injury": <><path d="M5 12h5l2-4 2 8 2-4h3" {...S} /></>,
  "symptom-other": <><circle cx="12" cy="12" r="8" {...S} /><path d="M9.5 10a2.5 2.5 0 1 1 3 2.5v1.5" {...S} /><circle cx="12" cy="17" r=".8" fill="currentColor" /></>,

  // ---- people
  "person-self": <><circle cx="12" cy="8" r="3.5" {...S} /><path d="M5 20a7 7 0 0 1 14 0" {...S} /></>,
  "person-family": <><circle cx="8" cy="8" r="3" {...S} /><circle cx="16" cy="9" r="2.5" {...S} /><path d="M3 19a5 5 0 0 1 10 0M13 19a4 4 0 0 1 8 0" {...S} /></>,
  "person-helper": <><circle cx="9" cy="8" r="3" {...S} /><path d="M4 19a5 5 0 0 1 10 0" {...S} /><path d="M17 10v6M14 13h6" {...S} /></>,

  // ---- ages
  "age-child": <><circle cx="12" cy="9" r="4" {...S} /><path d="M8 20a4 4 0 0 1 8 0" {...S} /></>,
  "age-young": <><circle cx="12" cy="8" r="3.5" {...S} /><path d="M6 20a6 6 0 0 1 12 0" {...S} /></>,
  "age-middle": <><circle cx="12" cy="8" r="3.5" {...S} /><path d="M6 20a6 6 0 0 1 12 0M9 14h6" {...S} /></>,
  "age-senior": <><circle cx="11" cy="8" r="3.5" {...S} /><path d="M5 20a6 6 0 0 1 12 0" {...S} /><path d="M19 10v10" {...S} /></>,
  "age-elder": <><circle cx="11" cy="8" r="3.5" {...S} /><path d="M5 20c0-3 2-5 5-5" {...S} /><path d="M19 9v11M19 9l-3 2" {...S} /></>,

  "sex-female": <><circle cx="12" cy="9" r="5" {...S} /><path d="M12 14v7M9 18h6" {...S} /></>,
  "sex-male": <><circle cx="10" cy="14" r="5" {...S} /><path d="M14.5 9.5L20 4M15 4h5v5" {...S} /></>,
  "sex-other": <><circle cx="12" cy="12" r="5" {...S} /><path d="M12 3v3M12 18v3M3 12h3M18 12h3" {...S} /></>,

  // ---- generic answers
  yes: <><circle cx="12" cy="12" r="9" {...S} /><path d="M8 12.5l2.5 2.5L16 9.5" {...S} /></>,
  no: <><circle cx="12" cy="12" r="9" {...S} /><path d="M9 9l6 6M15 9l-6 6" {...S} /></>,
  none: <><circle cx="12" cy="12" r="9" {...S} /><path d="M6 12h12" {...S} /></>,
  unsure: <><circle cx="12" cy="12" r="9" {...S} /><path d="M9.5 10a2.5 2.5 0 1 1 3 2.5v1" {...S} /><circle cx="12" cy="16.5" r=".9" fill="currentColor" /></>,
  skip: <><path d="M6 6l7 6-7 6zM17 6v12" {...S} /></>,

  // ---- onset, character, timing
  "onset-sudden": <><path d="M13 3L6 13h5l-1 8 7-10h-5z" {...S} /></>,
  "onset-gradual": <><path d="M4 18c4 0 6-2 8-6s4-6 8-6" {...S} /></>,
  "char-burning": <><path d="M12 3c3 4 5 6 5 9a5 5 0 0 1-10 0c0-2 1-3 2-4 0 2 1 3 2 3 0-3 1-5 1-8z" {...S} /></>,
  "char-dull": <><circle cx="12" cy="12" r="7" {...S} strokeDasharray="2 3" /></>,
  "char-sharp": <><path d="M4 20L20 4M16 4h4v4" {...S} /></>,
  "char-cramp": <><path d="M5 12c2-4 4 4 6 0s4-4 6 0" {...S} /><path d="M5 17c2-4 4 4 6 0s4-4 6 0" {...S} /></>,
  "char-throb": <><path d="M3 12h4l2-5 3 10 2-5h7" {...S} /></>,
  "char-pressure": <><path d="M5 6h14M12 8v6M9 12l3 3 3-3" {...S} /><path d="M5 20h14" {...S} /></>,
  "char-tingle": <><path d="M6 8h2M6 12h2M6 16h2M11 6l3 3-3 3 3 3-3 3" {...S} /></>,
  "time-constant": <><circle cx="12" cy="12" r="8" {...S} /><path d="M12 7v5l3 2" {...S} /></>,
  "time-intermittent": <><path d="M3 12h4M10 12h4M17 12h4" {...S} /></>,
  "time-morning": <><circle cx="12" cy="14" r="4" {...S} /><path d="M3 19h18M12 6v3M6 9l2 2M18 9l-2 2" {...S} /></>,
  "time-night": <><path d="M17 13A6 6 0 0 1 10 6a7 7 0 1 0 7 7z" {...S} /></>,
  "time-after-food": <><path d="M5 5v6a3 3 0 0 0 6 0V5M8 11v8" {...S} /><path d="M17 5c-2 2-2 6 0 8v6" {...S} /></>,
  "time-empty-stomach": <><circle cx="12" cy="13" r="6" {...S} strokeDasharray="3 3" /></>,
  "prog-worse": <><path d="M4 18L10 12l3 3 7-8M20 7v5h-5" {...S} /></>,
  "prog-better": <><path d="M4 6l6 6 3-3 7 8M20 17v-5h-5" {...S} /></>,
  "prog-same": <><path d="M4 12h16" {...S} /></>,
  "prog-fluctuating": <><path d="M3 14l4-6 4 8 4-8 4 6" {...S} /></>,

  // ---- conditions
  "cond-diabetes": <><path d="M12 4c3 4 5 6 5 9a5 5 0 0 1-10 0c0-3 2-5 5-9z" {...S} /></>,
  "cond-bp": <><path d="M4 13h4l2-5 3 9 2-4h5" {...S} /></>,
  "cond-heart": <><path d="M12 20s-7-4.5-7-9a4 4 0 0 1 7-2.5A4 4 0 0 1 19 11c0 4.5-7 9-7 9z" {...S} /></>,
  "cond-asthma": <><path d="M12 5v9" {...S} /><path d="M12 9c-3 0-5 2-5 5 0 2 2 3 3 1l2-3" {...S} /><path d="M12 9c3 0 5 2 5 5 0 2-2 3-3 1l-2-3" {...S} /></>,
  "cond-tb": <><path d="M6 8h12v8H6z" {...S} /><path d="M9 11h6M9 14h4" {...S} /></>,
  "cond-thyroid": <><path d="M8 7c0 4-2 5-2 7a3 3 0 0 0 6 0 3 3 0 0 0 6 0c0-2-2-3-2-7" {...S} /></>,
  "cond-kidney": <><path d="M9 6c-3 0-4 3-4 6s1 6 4 6c2 0 2-3 2-6s0-6-2-6z" {...S} /><path d="M15 6c3 0 4 3 4 6s-1 6-4 6c-2 0-2-3-2-6s0-6 2-6z" {...S} /></>,
  "cond-liver": <><path d="M4 9c5-2 11-2 16 0-1 6-4 9-8 9S5 15 4 9z" {...S} /></>,
  "cond-stroke": <><circle cx="12" cy="10" r="6" {...S} /><path d="M9 9l6 3M15 9l-6 3" {...S} /></>,
  "cond-cancer": <><circle cx="12" cy="12" r="3" {...S} /><circle cx="12" cy="12" r="8" {...S} strokeDasharray="2 4" /></>,
  "cond-epilepsy": <><path d="M13 3L7 13h4l-1 8 7-11h-4z" {...S} /></>,
  "cond-arthritis": <><circle cx="8" cy="8" r="3" {...S} /><circle cx="16" cy="16" r="3" {...S} /><path d="M10 10l4 4M6 14l2-1M18 10l-2 1" {...S} /></>,
  "cond-mental": <><circle cx="12" cy="11" r="6" {...S} /><path d="M9 11a3 3 0 0 1 6 0" {...S} /></>,

  // ---- associated
  "assoc-nausea": <><path d="M7 7v6a5 5 0 0 0 10 0V7" {...S} /><path d="M9 17c2 1 4 1 6 0" {...S} /></>,
  "assoc-vomiting": <><path d="M8 5h8v5a4 4 0 0 1-8 0z" {...S} /><path d="M12 14v5M10 17l2 2 2-2" {...S} /></>,
  "assoc-sweating": <><circle cx="12" cy="9" r="4" {...S} /><path d="M7 15c0 2 1 3 2 3M12 15c0 2 1 3 2 3M17 15c0 2-1 3-2 3" {...S} /></>,
  "assoc-dizzy": <><circle cx="12" cy="12" r="8" {...S} /><path d="M8 10c2-2 6-2 8 0M9 15c2 1 4 1 6 0" {...S} /></>,
  "assoc-palpitations": <><path d="M12 19s-6-4-6-8a3.5 3.5 0 0 1 6-2 3.5 3.5 0 0 1 6 2c0 4-6 8-6 8z" {...S} /><path d="M3 12h3l1-2 1 4 1-2h2" {...S} /></>,
  "assoc-loose": <><path d="M8 5h8v6a4 4 0 0 1-8 0z" {...S} /><path d="M9 16h6M10 19h4" {...S} /></>,
  "assoc-constipation": <><circle cx="12" cy="12" r="7" {...S} /><path d="M9 12h6" {...S} /><path d="M12 8v8" {...S} strokeDasharray="2 2" /></>,
  "assoc-weight-loss": <><path d="M5 8h14l-1.5 12h-11z" {...S} /><path d="M9 14l6-3" {...S} /></>,
  "assoc-appetite": <><path d="M6 4v7a3 3 0 0 0 6 0V4M9 11v9" {...S} /><path d="M18 4c-2 2-2 6 0 8v8" {...S} /><path d="M4 4l16 16" {...S} /></>,

  // ---- ayush
  "agni-good-good": <><path d="M12 4c3 4 5 6 5 9a5 5 0 0 1-10 0c0-3 2-5 5-9z" {...S} /><path d="M9.5 13l1.8 1.8L15 11" {...S} /></>,
  "agni-good-poor": <><path d="M12 4c3 4 5 6 5 9a5 5 0 0 1-10 0c0-3 2-5 5-9z" {...S} /><path d="M9 15h6" {...S} /></>,
  "agni-poor-good": <><path d="M12 8c2 2 3 3 3 5a3 3 0 0 1-6 0c0-2 1-3 3-5z" {...S} /><path d="M9.5 16l1.5 1.5L14 14" {...S} /></>,
  "agni-poor-poor": <><path d="M12 8c2 2 3 3 3 5a3 3 0 0 1-6 0c0-2 1-3 3-5z" {...S} /><path d="M10 17l4-4M10 13l4 4" {...S} /></>,
  "agni-sama": <><path d="M12 5c3 4 5 6 5 9a5 5 0 0 1-10 0c0-3 2-5 5-9z" {...S} /></>,
  "agni-vishama": <><path d="M4 14l3-5 3 6 3-8 3 7 4-4" {...S} /></>,
  "agni-tikshna": <><path d="M13 3L7 13h4l-1 8 7-11h-4z" {...S} /></>,
  "agni-manda": <><path d="M12 10c2 2 3 3 3 4a3 3 0 0 1-6 0c0-1 1-2 3-4z" {...S} /></>,
  "koshtha-soft": <><circle cx="12" cy="12" r="7" {...S} strokeDasharray="1 3" /></>,
  "koshtha-mid": <><circle cx="12" cy="12" r="7" {...S} strokeDasharray="4 3" /></>,
  "koshtha-hard": <><circle cx="12" cy="12" r="7" {...S} /></>,
  "rasa-sweet": <><path d="M6 10h12l-1 9H7z" {...S} /><path d="M9 10V7a3 3 0 0 1 6 0v3" {...S} /></>,
  "rasa-sour": <><circle cx="12" cy="13" r="6" {...S} /><path d="M12 7v12M7 13h10" {...S} /></>,
  "rasa-salty": <><path d="M9 6h6l1 13H8z" {...S} /><circle cx="11" cy="10" r=".7" fill="currentColor" /><circle cx="13" cy="12" r=".7" fill="currentColor" /></>,
  "rasa-pungent": <><path d="M13 6c0 6-2 12-5 12-2 0-3-2-2-4 2-4 5-6 7-8z" {...S} /><path d="M13 6c1-2 3-2 4-1" {...S} /></>,
  "rasa-bitter": <><path d="M8 6c4 2 6 6 8 12" {...S} /><path d="M8 6c-1 5 0 9 3 12" {...S} /></>,
  "rasa-astringent": <><ellipse cx="12" cy="12" rx="7" ry="4" {...S} /><path d="M9 12h6" {...S} /></>,
  "vaya-bala": <><circle cx="12" cy="9" r="4" {...S} /><path d="M8 20a4 4 0 0 1 8 0" {...S} /></>,
  "vaya-madhya": <><circle cx="12" cy="8" r="3.5" {...S} /><path d="M6 20a6 6 0 0 1 12 0" {...S} /></>,
  "vaya-vriddha": <><circle cx="11" cy="8" r="3.5" {...S} /><path d="M5 20c0-3 2-5 5-5" {...S} /><path d="M19 9v11" {...S} /></>,

  // ---- documents
  "doc-papers": <><path d="M7 4h7l4 4v12H7z" {...S} /><path d="M14 4v4h4M10 13h6M10 16h4" {...S} /></>,
};

// Keys that share a drawing. Cheaper than duplicating paths, and keeps the set honest
// about which distinctions the current artwork actually makes.
const ALIASES: Record<string, string> = {
  "site-upper-abdomen": "body-abdomen", "site-lower-abdomen": "body-abdomen",
  "site-whole-abdomen": "body-abdomen", "site-central-chest": "body-chest",
  "site-left-chest": "body-chest", "site-right-chest": "body-chest",
  "site-forehead": "body-head", "site-back-head": "body-head",
  "site-one-side-head": "body-head", "site-whole-head": "body-head",
  "site-knee": "body-joint", "site-shoulder": "body-joint", "site-lower-back": "body-joint",
  "site-neck": "body-joint", "site-hip": "body-joint", "site-multiple-joints": "cond-arthritis",
  "site-other": "symptom-other",
  "radiate-none": "none", "radiate-back": "prog-same", "radiate-left-arm": "char-sharp",
  "radiate-jaw": "char-sharp", "radiate-shoulder": "body-joint",
  "radiate-groin": "body-urinary", "radiate-leg": "body-joint",
  "char-other": "symptom-other",
  "agg-eating": "time-after-food", "agg-movement": "prog-fluctuating",
  "agg-rest": "time-night", "agg-lying": "time-night", "agg-stress": "cond-mental",
  "agg-cold": "time-night", "agg-heat": "char-burning", "agg-foods": "time-after-food",
  "rel-medicine": "med-allopathic", "rel-food": "time-after-food",
  "rel-stool": "assoc-loose", "rel-warmth": "char-burning",
  "med-allopathic": "cond-bp", "med-ayurvedic": "rasa-bitter", "med-homeopathic": "rasa-sweet",
  "med-siddha": "rasa-bitter", "med-unani": "rasa-bitter", "med-self": "symptom-other",
  "adhere-good": "yes", "adhere-partial": "time-intermittent", "adhere-stopped": "no",
  "allergy-drug": "cond-bp", "allergy-food": "time-after-food", "allergy-both": "symptom-other",
  "time-recent": "time-constant", "time-mid": "time-intermittent", "time-old": "time-night",
  "diet-veg": "rasa-bitter", "diet-nonveg": "symptom-other", "diet-egg": "rasa-sweet",
  "diet-vegan": "rasa-bitter",
  "tobacco-chew": "symptom-cough", "tobacco-smoke": "symptom-cough",
  "tobacco-both": "symptom-cough", "tobacco-quit": "no",
  "alcohol-occasional": "time-intermittent", "alcohol-regular": "time-constant",
  "sleep-good": "time-night", "sleep-onset": "time-night", "sleep-broken": "prog-fluctuating",
  "sleep-little": "time-night", "sleep-much": "time-night",
  "sleep-early": "time-morning", "sleep-late": "time-night",
  "sleep-day": "time-morning", "sleep-irregular": "prog-fluctuating",
  "bowel-regular": "time-constant", "bowel-alternating": "prog-fluctuating",
  "work-sitting": "person-self", "work-standing": "person-self",
  "work-heavy": "symptom-weak", "work-night": "time-night", "work-none": "none",
  "mens-regular": "time-constant", "mens-irregular": "prog-fluctuating",
  "mens-painful": "char-sharp", "mens-heavy": "body-menstrual", "mens-stopped": "no",
  "ros-weight-gain": "assoc-weight-loss", "ros-night-sweats": "assoc-sweating",
  "ros-blood-sputum": "symptom-cough", "ros-ankle-swelling": "body-joint",
  "ros-blood-stool": "assoc-loose", "ros-black-stool": "assoc-loose",
  "ros-swallowing": "body-chest", "ros-fainting": "assoc-dizzy",
  "ros-limb-weakness": "symptom-weak", "ros-vision": "cond-mental",
  "uro-burning": "char-burning", "uro-blood": "body-urinary",
  "uro-frequency": "time-intermittent", "uro-retention": "no",
  "prakriti-vata-build": "symptom-weak", "prakriti-vata-appetite": "agni-vishama",
  "prakriti-vata-sleep": "time-night", "prakriti-pitta-appetite": "agni-tikshna",
  "prakriti-pitta-heat": "char-burning", "prakriti-pitta-temper": "cond-mental",
  "prakriti-kapha-build": "assoc-weight-loss", "prakriti-kapha-digestion": "agni-manda",
  "prakriti-kapha-sleep": "time-night",
  "vikriti-vata": "prog-fluctuating", "vikriti-pitta": "char-burning",
  "vikriti-kapha": "char-pressure",
  "sara-high": "yes", "sara-mid": "prog-same", "sara-low": "symptom-weak",
  "build-compact": "yes", "build-moderate": "prog-same", "build-loose": "symptom-weak",
  "size-proportionate": "prog-same", "size-above": "prog-worse", "size-below": "prog-better",
  "satmya-easy": "yes", "satmya-mid": "prog-same", "satmya-poor": "no",
  "sattva-high": "yes", "sattva-mid": "prog-same", "sattva-low": "cond-mental",
  "exert-high": "prog-worse", "exert-mid": "prog-same", "exert-low": "symptom-weak",
  "exert-none": "no",
  "meal-regular": "time-constant", "meal-irregular": "prog-fluctuating",
  "meal-skipped": "assoc-appetite",
  "water-low": "assoc-appetite", "water-mid": "prog-same", "water-high": "prog-worse",
  "activity-none": "no", "activity-light": "prog-better",
  "activity-moderate": "prog-same", "activity-heavy": "symptom-weak",
};

export function Icon({ name, className = "w-14 h-14" }: Props) {
  const key = name ?? "";
  const resolved = PATHS[key] ?? PATHS[ALIASES[key] ?? ""] ?? null;

  if (!resolved) {
    // Deliberately visible. A blank space would quietly break the touch path for
    // someone who cannot read the label beside it.
    return (
      <span
        className={`${className} inline-flex items-center justify-center rounded-full border-2 border-dashed border-current opacity-50 text-base font-bold`}
        aria-hidden
      >
        {(key.replace(/[^a-z]/g, "")[0] ?? "?").toUpperCase()}
      </span>
    );
  }

  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden focusable="false">
      {resolved}
    </svg>
  );
}
