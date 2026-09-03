"""The 40 eval scenarios.

Held in Python rather than YAML on purpose: several scenarios need to assert things
about *behaviour* (this must escalate, this must escalate before question eight, this
must not escalate) and encoding that in YAML would mean inventing a second little
language to express it.

The mix is prescribed by `04-targets.md`: at least 5 red-flag, 5 proxy-respondent,
5 abandonment/partial, 5 AYUSH-specific, and several deliberately messy ones.

Each scenario carries:
    id            stable, appears in the results table
    tags          for the per-category breakdown
    mode          ayush | core
    script        slot -> value, the ground truth of what the patient would answer
    utterances    optional slot -> spoken text, to exercise the voice path offline
    expect        assertions the runner checks
"""

from __future__ import annotations

BASE_ADULT = {
    "identity.respondent": "self",
    "identity.age_band": "40_59",
    "identity.sex": "male",
}


def _s(**kw):
    out = dict(BASE_ADULT)
    out.update(kw)
    return out


SCENARIOS: list[dict] = [
    # ------------------------------------------------------------ 1-5 RED FLAG
    {
        "id": "rf-01-chest-pain-dyspnoea",
        "tags": ["red_flag", "cardiac"],
        "mode": "ayush",
        "note": "The brief's own example: acute chest pain with dyspnoea.",
        "script": _s(**{
            "cc.primary": "chest_pain", "hpi.onset": "sudden",
            "hpi.duration": {"n": 2, "unit": "hours"},
            "hpi.associated": ["breathlessness", "sweating"], "hpi.severity": 8,
        }),
        "expect": {"escalates": True, "rule": "rf.cardiac.chest_pain_dyspnoea", "within_questions": 10},
    },
    {
        "id": "rf-02-stroke-symptoms",
        "tags": ["red_flag", "neuro"],
        "mode": "ayush",
        "note": "Danger-sign screen must catch this even though ROS never gets reached.",
        "script": _s(**{
            "cc.primary": "weakness_fatigue", "hpi.onset": "sudden",
            "hpi.duration": {"n": 3, "unit": "hours"}, "hpi.associated": ["none"],
            "hpi.severity": 6, "ros.danger_signs": ["weakness_limb"],
        }),
        "expect": {"escalates": True, "rule": "rf.neuro.stroke_symptoms", "within_questions": 12},
    },
    {
        "id": "rf-03-gi-bleed",
        "tags": ["red_flag", "gi"],
        "mode": "ayush",
        "script": _s(**{
            "cc.primary": "abdominal_pain", "hpi.site": "upper_abdomen", "hpi.onset": "gradual",
            "hpi.duration": {"n": 4, "unit": "days"}, "hpi.associated": ["none"],
            "hpi.severity": 5, "ros.danger_signs": ["black_stool"],
        }),
        "expect": {"escalates": True, "rule": "rf.bleed.gi_bleeding", "within_questions": 12},
    },
    {
        "id": "rf-04-elderly-chest-pain-atypical",
        "tags": ["red_flag", "cardiac", "elderly"],
        "mode": "ayush",
        "note": "No second sign. Escalates on age alone, which is the intended behaviour.",
        "script": {
            "identity.respondent": "self", "identity.age_band": "75_plus", "identity.sex": "female",
            "cc.primary": "chest_pain", "hpi.onset": "gradual",
            "hpi.duration": {"n": 2, "unit": "days"}, "hpi.associated": ["none"], "hpi.severity": 3,
        },
        "expect": {"escalates": True, "rule": "rf.age.elderly_chest_pain", "within_questions": 10},
    },
    {
        "id": "rf-05-thunderclap-headache",
        "tags": ["red_flag", "neuro"],
        "mode": "ayush",
        "script": _s(**{
            "cc.primary": "headache", "hpi.site": "whole_head", "hpi.onset": "sudden",
            "hpi.duration": {"n": 1, "unit": "hours"}, "hpi.associated": ["vomiting"],
            "hpi.severity": 9,
        }),
        "expect": {"escalates": True, "within_questions": 10},
    },
    {
        "id": "rf-06-breathless-at-rest",
        "tags": ["red_flag", "respiratory"],
        "mode": "ayush",
        "script": _s(**{
            "cc.primary": "breathlessness", "hpi.onset": "gradual",
            "hpi.duration": {"n": 3, "unit": "days"}, "hpi.associated": ["none"],
            "hpi.severity": 6, "hpi.aggravating": ["rest"], "ros.danger_signs": ["none"],
        }),
        "expect": {"escalates": True, "rule": "rf.resp.breathlessness_at_rest"},
    },
    {
        "id": "rf-07-known-epileptic-no-escalation",
        "tags": ["red_flag", "specificity"],
        "mode": "ayush",
        "note": "A known epileptic reporting their usual fits must NOT break the queue. "
                "This is the false-positive control.",
        "script": _s(**{
            "cc.primary": "weakness_fatigue", "hpi.onset": "gradual",
            "hpi.duration": {"n": 2, "unit": "weeks"}, "hpi.associated": ["none"],
            "hpi.severity": 3, "past.conditions": ["epilepsy"],
            "ros.danger_signs": ["fits"],
        }),
        "expect": {"escalates": False},
    },
    {
        "id": "rf-08-severe-pain-any-site",
        "tags": ["red_flag", "catch_all"],
        "mode": "ayush",
        "script": _s(**{
            "cc.primary": "joint_pain", "hpi.site": "knee", "hpi.onset": "sudden",
            "hpi.duration": {"n": 1, "unit": "days"}, "hpi.associated": ["none"],
            "hpi.severity": 10,
        }),
        "expect": {"escalates": True},
    },

    # ------------------------------------------------------------ PROXY
    {
        "id": "px-01-son-answers-for-mother",
        "tags": ["proxy"],
        "mode": "ayush",
        "script": {
            "identity.respondent": "relative", "identity.age_band": "75_plus",
            "identity.sex": "female", "cc.primary": "weakness_fatigue",
            "hpi.onset": "gradual", "hpi.duration": {"n": 2, "unit": "months"},
            "hpi.associated": ["appetite_loss", "weight_loss"], "hpi.severity": 5,
            "hpi.timing": "constant", "hpi.progression": "getting_worse",
            "hpi.first_episode": True,
            "ros.danger_signs": ["none"], "past.conditions": ["diabetes"],
            "drugs.allergy_known": "unsure", "drugs.taking_now": True,
        },
        "expect": {"escalates": False, "proxy_marked": True, "min_coverage": {"hpi": 60}},
    },
    {
        "id": "px-02-attendant-limited-knowledge",
        "tags": ["proxy", "partial"],
        "mode": "ayush",
        "note": "An attendant genuinely does not know the past history. Unknowns must "
                "come through as unknowns, not as absences.",
        "script": {
            "identity.respondent": "attendant", "identity.age_band": "60_74",
            "identity.sex": "male", "cc.primary": "breathlessness",
            "hpi.onset": "gradual", "hpi.duration": {"n": 1, "unit": "weeks"},
            "hpi.associated": ["none"], "hpi.severity": 5,
            "ros.danger_signs": ["none"], "past.conditions": ["unsure"],
            "drugs.allergy_known": "unsure",
        },
        "expect": {"escalates": False, "proxy_marked": True},
    },
    {
        "id": "px-03-proxy-red-flag",
        "tags": ["proxy", "red_flag"],
        "mode": "ayush",
        "note": "Escalation must work identically when a relative is speaking.",
        "script": {
            "identity.respondent": "relative", "identity.age_band": "60_74",
            "identity.sex": "male", "cc.primary": "chest_pain", "hpi.onset": "sudden",
            "hpi.duration": {"n": 1, "unit": "hours"},
            "hpi.associated": ["sweating", "breathlessness"], "hpi.severity": 9,
        },
        "expect": {"escalates": True, "proxy_marked": True},
    },
    {
        "id": "px-04-parent-for-child",
        "tags": ["proxy", "paediatric"],
        "mode": "ayush",
        "script": {
            "identity.respondent": "relative", "identity.age_band": "under_18",
            "identity.sex": "male", "cc.primary": "fever", "hpi.onset": "sudden",
            "hpi.duration": {"n": 2, "unit": "days"}, "hpi.associated": ["vomiting"],
            "hpi.severity": 7,
        },
        "expect": {"escalates": True, "rule": "rf.age.infant_fever", "proxy_marked": True},
    },
    {
        "id": "px-05-proxy-ayush-block",
        "tags": ["proxy", "ayush"],
        "mode": "ayush",
        "note": "Constitutional questions answered by proxy are weak data. They must "
                "still be captured, and must still be marked proxy.",
        "script": {
            "identity.respondent": "relative", "identity.age_band": "75_plus",
            "identity.sex": "female", "cc.primary": "digestive_problem",
            "hpi.onset": "gradual", "hpi.duration": {"n": 6, "unit": "months"},
            "hpi.associated": ["appetite_loss"], "hpi.severity": 4,
            "ros.danger_signs": ["none"], "past.conditions": ["none"],
            "drugs.allergy_known": "none", "drugs.taking_now": False,
            "ayush.ahara_shakti": "poor_intake_poor_digestion", "ayush.agni": "manda",
            "ayush.prakriti_screen": ["kapha_slow_digestion", "vata_variable_appetite"],
            "ayush.vikriti": ["kapha_aggravated"], "personal.bowel": "constipated",
        },
        "expect": {"escalates": False, "proxy_marked": True, "min_dashavidha": 3},
    },

    # ------------------------------------------------------------ ABANDONMENT
    {
        "id": "ab-01-walks-away-after-complaint",
        "tags": ["abandonment"],
        "mode": "ayush",
        "note": "Only the complaint was given. Must not reach a doctor as a history.",
        "script": _s(**{"cc.primary": "headache"}),
        "abandon_after": 5,
        "expect": {"abandoned": True, "forwarded": False},
    },
    {
        "id": "ab-02-stops-mid-ayush",
        "tags": ["abandonment", "ayush"],
        "mode": "ayush",
        "script": _s(**{
            "cc.primary": "joint_pain", "hpi.site": "knee", "hpi.onset": "gradual",
            "hpi.duration": {"n": 1, "unit": "years"}, "hpi.associated": ["none"],
            "hpi.severity": 4, "ros.danger_signs": ["none"],
        }),
        "abandon_after": 12,
        "expect": {"abandoned": True, "forwarded": False},
    },
    {
        "id": "ab-03-abandons-at-first-question",
        "tags": ["abandonment"],
        "mode": "ayush",
        "script": {},
        "abandon_after": 1,
        "expect": {"abandoned": True, "forwarded": False},
    },
    {
        "id": "ab-04-abandons-after-red-flag-shown",
        "tags": ["abandonment", "red_flag"],
        "mode": "ayush",
        "note": "The escalation already fired. The ALERT must survive even though the "
                "interview did not — a patient walking away from a chest-pain warning "
                "is the one who most needs a nurse to go and find them.",
        "script": _s(**{
            "cc.primary": "chest_pain", "hpi.onset": "sudden",
            "hpi.duration": {"n": 1, "unit": "hours"},
            "hpi.associated": ["breathlessness"], "hpi.severity": 8,
        }),
        "abandon_after": 20,
        "expect": {"escalates": True, "alert_survives_abandonment": True},
    },
    {
        "id": "ab-05-partial-then-completes",
        "tags": ["abandonment", "partial"],
        "mode": "core",
        "script": _s(**{
            "cc.primary": "cough", "hpi.onset": "gradual",
            "hpi.duration": {"n": 3, "unit": "weeks"}, "hpi.associated": ["fever"],
            "hpi.severity": 4, "ros.danger_signs": ["none"],
            "past.conditions": ["none"], "drugs.allergy_known": "none",
            "drugs.taking_now": False, "docs.has_papers": False,
        }),
        "expect": {"escalates": False, "completes": True},
    },

    # ------------------------------------------------------------ AYUSH
    {
        "id": "ay-01-full-dashavidha",
        "tags": ["ayush"],
        "mode": "ayush",
        "note": "The headline claim: 10 of 10 Dashavidha parameters inside the budget.",
        "script": _s(**{
            "cc.primary": "digestive_problem", "hpi.onset": "gradual",
            "hpi.duration": {"n": 6, "unit": "months"}, "hpi.associated": ["constipation"],
            "hpi.severity": 4, "ros.danger_signs": ["none"], "past.conditions": ["none"],
            "drugs.allergy_known": "none", "drugs.taking_now": False,
            "personal.bowel": "constipated",
            "ayush.prakriti_screen": ["vata_lean_dry_restless", "vata_light_sleep", "vata_variable_appetite"],
            "ayush.vikriti": ["vata_aggravated"], "ayush.sara": "madhyama",
            "ayush.samhanana": "moderate", "ayush.pramana": "below_proportion",
            "ayush.satmya": "adapts_poorly", "ayush.sattva": "madhyama",
            "ayush.ahara_shakti": "poor_intake_poor_digestion",
            "ayush.vyayama_shakti": "low", "ayush.agni": "vishama",
        }),
        "expect": {"escalates": False, "min_dashavidha": 10},
    },
    {
        "id": "ay-02-pitta-presentation",
        "tags": ["ayush"],
        "mode": "ayush",
        "script": _s(**{
            "cc.primary": "abdominal_pain", "hpi.site": "upper_abdomen",
            "hpi.character": "burning", "hpi.onset": "gradual",
            "hpi.duration": {"n": 2, "unit": "months"}, "hpi.associated": ["nausea"],
            "hpi.timing": "worse_empty_stomach", "hpi.severity": 6,
            "ros.danger_signs": ["none"], "past.conditions": ["none"],
            "drugs.allergy_known": "none", "drugs.taking_now": True,
            "ayush.prakriti_screen": ["pitta_sharp_appetite", "pitta_warm_intolerant", "pitta_irritable"],
            "ayush.vikriti": ["pitta_aggravated"], "ayush.agni": "tikshna",
            "ayush.ahara_shakti": "good_intake_poor_digestion",
            "ahara.rasa_preference": ["katu", "amla"], "personal.bowel": "loose",
        }),
        "expect": {"escalates": False, "min_dashavidha": 4, "dosha_summary_contains": "Pitta"},
    },
    {
        "id": "ay-03-koshtha-derived-not-asked",
        "tags": ["ayush", "derivation"],
        "mode": "ayush",
        "note": "Nobody is asked about their bowels twice. Koshtha derives from "
                "personal.bowel and must never appear as its own question.",
        "script": _s(**{
            "cc.primary": "digestive_problem", "hpi.onset": "gradual",
            "hpi.duration": {"n": 1, "unit": "months"}, "hpi.associated": ["none"],
            "hpi.severity": 3, "ros.danger_signs": ["none"], "past.conditions": ["none"],
            "drugs.allergy_known": "none", "drugs.taking_now": False,
            "personal.bowel": "constipated",
        }),
        "expect": {
            "escalates": False,
            "slot_equals": {"ayush.koshtha": "krura"},
            "node_not_asked": "ayush.koshtha",
        },
    },
    {
        "id": "ay-04-vaya-derived-from-age",
        "tags": ["ayush", "derivation"],
        "mode": "ayush",
        "note": "Vaya costs the patient zero seconds. It comes from the age band.",
        "script": {
            "identity.respondent": "self", "identity.age_band": "75_plus",
            "identity.sex": "female", "cc.primary": "joint_pain", "hpi.site": "knee",
            "hpi.onset": "gradual", "hpi.duration": {"n": 5, "unit": "years"},
            "hpi.associated": ["none"], "hpi.severity": 5, "ros.danger_signs": ["none"],
        },
        "expect": {"slot_equals": {"ayush.vaya": "vriddha"}, "node_not_asked": "ayush.vaya"},
    },
    {
        "id": "ay-05-core-mode-skips-ayush",
        "tags": ["ayush", "mode"],
        "mode": "core",
        "note": "Core mode must ask NO Dashavidha questions at all.",
        "script": _s(**{
            "cc.primary": "fever", "hpi.onset": "sudden",
            "hpi.duration": {"n": 3, "unit": "days"}, "hpi.associated": ["none"],
            "hpi.severity": 5, "ros.danger_signs": ["none"], "past.conditions": ["none"],
            "drugs.allergy_known": "none", "drugs.taking_now": False,
        }),
        "expect": {"escalates": False, "max_dashavidha": 0},
    },
    {
        "id": "ay-06-ayurvedic-plus-allopathic-meds",
        "tags": ["ayush", "drugs"],
        "mode": "ayush",
        "note": "The common case in an AYUSH OPD, and the one nobody else asks about.",
        "script": _s(**{
            "cc.primary": "weakness_fatigue", "hpi.onset": "gradual",
            "hpi.duration": {"n": 3, "unit": "months"}, "hpi.associated": ["none"],
            "hpi.severity": 4, "ros.danger_signs": ["none"],
            "past.conditions": ["diabetes"], "drugs.allergy_known": "none",
            "drugs.taking_now": True, "drugs.systems": ["allopathic", "ayurvedic"],
            "drugs.adherence": "sometimes_missed",
        }),
        "expect": {"escalates": False, "slot_equals": {"drugs.systems": ["allopathic", "ayurvedic"]}},
    },

    # ------------------------------------------------------------ MESSY
    {
        "id": "ms-01-rambling-voice",
        "tags": ["messy", "voice"],
        "mode": "ayush",
        "note": "Real speech, with filler. The offline keyword rung must still land it.",
        "script": _s(**{
            "cc.primary": "abdominal_pain", "hpi.onset": "gradual",
            "hpi.duration": {"n": 3, "unit": "weeks"}, "hpi.severity": 6,
            "hpi.associated": ["nausea"], "ros.danger_signs": ["none"],
        }),
        "utterances": {
            "cc.primary": "doctor sahab mere pet mein bahut dard ho raha hai kai dino se",
            "hpi.duration": "yahi koi teen hafte se hoga",
            "hpi.onset": "dheere dheere shuru hua tha",
            "hpi.severity": "sat ke aas paas",
            "hpi.associated": "ji michalna bhi hota hai",
            "ros.danger_signs": "nahi aisa kuch nahi",
        },
        "expect": {"escalates": False, "voice_resolved_min": 5},
    },
    {
        "id": "ms-02-code-switching",
        "tags": ["messy", "voice"],
        "mode": "ayush",
        "note": "Hindi and English in one sentence, which is how people actually talk.",
        "script": _s(**{
            "cc.primary": "chest_pain", "hpi.onset": "gradual",
            "hpi.duration": {"n": 2, "unit": "days"}, "hpi.associated": ["none"],
            "hpi.severity": 4,
        }),
        "utterances": {
            "cc.primary": "mujhe chest pain ho raha hai",
            "hpi.duration": "two days se",
            "hpi.severity": "four",
        },
        "expect": {"voice_resolved_min": 3},
    },
    {
        "id": "ms-03-devanagari-input",
        "tags": ["messy", "voice"],
        "mode": "ayush",
        "script": _s(**{
            "cc.primary": "headache", "hpi.onset": "sudden",
            "hpi.duration": {"n": 2, "unit": "days"}, "hpi.severity": 5,
            "hpi.associated": ["none"],
        }),
        "utterances": {
            "cc.primary": "मुझे सिर दर्द है",
            "hpi.onset": "अचानक",
            "hpi.severity": "पाँच",
        },
        "expect": {"voice_resolved_min": 3},
    },
    {
        "id": "ms-04-contradicts-then-corrects",
        "tags": ["messy"],
        "mode": "ayush",
        "note": "Answers no to medication, then lists medicines. The later answer wins "
                "and the summary must not contain both.",
        "script": _s(**{
            "cc.primary": "urinary_problem", "hpi.onset": "gradual",
            "hpi.duration": {"n": 1, "unit": "weeks"}, "hpi.associated": ["none"],
            "hpi.severity": 5, "ros.danger_signs": ["none"], "past.conditions": ["diabetes"],
            "drugs.allergy_known": "none", "drugs.taking_now": True,
            "drugs.systems": ["allopathic"],
        }),
        "corrections": [("drugs.taking_now", False), ("drugs.taking_now", True)],
        "expect": {"escalates": False, "slot_equals": {"drugs.taking_now": True}},
    },
    {
        "id": "ms-05-unclear-utterance",
        "tags": ["messy", "voice"],
        "mode": "ayush",
        "note": "Nonsense in must produce unclear, never a guessed slot value. This is "
                "the anti-hallucination test.",
        "script": _s(**{"cc.primary": "fever"}),
        "utterances": {"cc.primary": "hmm woh kya kehte hain uske baare mein"},
        "expect": {"voice_unclear": ["cc.primary"]},
    },
    {
        "id": "ms-06-everything-unknown",
        "tags": ["messy", "partial"],
        "mode": "ayush",
        "note": "A patient who does not know anything about their own history. Should "
                "still produce a valid, honest, mostly-empty summary.",
        "script": _s(**{
            "cc.primary": "other", "hpi.onset": "unsure",
            "hpi.duration": {"n": 1, "unit": "months"}, "hpi.associated": ["none"],
            "hpi.severity": 5, "ros.danger_signs": ["none"],
            "past.conditions": ["unsure"], "drugs.allergy_known": "unsure",
            "drugs.taking_now": False,
        }),
        "expect": {"escalates": False, "completes": True},
    },

    # ------------------------------------------------------------ ROUTINE
    {
        "id": "rt-01-kamala-abdominal-pain",
        "tags": ["routine", "ayush"],
        "mode": "ayush",
        "note": "The walkthrough patient from docs/02-product.md.",
        "script": {
            "identity.respondent": "self", "identity.age_band": "60_74",
            "identity.sex": "female", "cc.primary": "abdominal_pain",
            "hpi.site": "upper_abdomen", "hpi.onset": "gradual",
            "hpi.duration": {"n": 3, "unit": "weeks"}, "hpi.character": "burning",
            "hpi.radiation": "none", "hpi.associated": ["nausea"],
            "hpi.timing": "worse_after_food", "hpi.severity": 5,
            "ros.danger_signs": ["none"], "past.conditions": ["hypertension"],
            "drugs.taking_now": True, "drugs.allergy_known": "none",
            "personal.bowel": "constipated",
            "ayush.ahara_shakti": "good_intake_poor_digestion", "ayush.agni": "tikshna",
            "ayush.prakriti_screen": ["pitta_sharp_appetite", "vata_light_sleep"],
            "ayush.vikriti": ["pitta_aggravated"], "ayush.vyayama_shakti": "moderate",
            "ayush.sara": "madhyama", "ayush.samhanana": "moderate",
            "ayush.pramana": "proportionate", "ayush.satmya": "adapts_moderately",
            "ayush.sattva": "madhyama", "docs.has_papers": True,
        },
        "expect": {"escalates": False, "min_socrates": 6, "min_dashavidha": 10},
    },
    {
        "id": "rt-02-young-fever",
        "tags": ["routine", "core"],
        "mode": "core",
        "script": _s(**{
            "identity.age_band": "18_39", "cc.primary": "fever", "hpi.onset": "sudden",
            "hpi.duration": {"n": 2, "unit": "days"}, "hpi.associated": ["none"],
            "hpi.severity": 5, "ros.danger_signs": ["none"], "past.conditions": ["none"],
            "drugs.allergy_known": "none", "drugs.taking_now": False,
            "docs.has_papers": False,
        }),
        "expect": {"escalates": False, "completes": True, "max_elapsed_s": 260},
    },
    {
        "id": "rt-03-chronic-joint-pain",
        "tags": ["routine", "ayush"],
        "mode": "ayush",
        "script": _s(**{
            "identity.age_band": "60_74", "cc.primary": "joint_pain",
            "hpi.site": "multiple_joints", "hpi.onset": "gradual",
            "hpi.duration": {"n": 4, "unit": "years"}, "hpi.character": "dull_ache",
            "hpi.radiation": "none", "hpi.associated": ["none"],
            "hpi.timing": "worse_morning", "hpi.severity": 6,
            "ros.danger_signs": ["none"], "past.conditions": ["arthritis"],
            "drugs.allergy_known": "none", "drugs.taking_now": True,
            "drugs.systems": ["ayurvedic"], "personal.bowel": "regular",
            "ayush.ahara_shakti": "good_intake_good_digestion", "ayush.agni": "sama",
            "ayush.prakriti_screen": ["vata_lean_dry_restless"],
            "ayush.vikriti": ["vata_aggravated"], "ayush.vyayama_shakti": "low",
            "ayush.sara": "avara", "ayush.samhanana": "loose_weak",
            "ayush.pramana": "proportionate", "ayush.satmya": "adapts_poorly",
            "ayush.sattva": "madhyama",
        }),
        "expect": {"escalates": False, "min_dashavidha": 10},
    },
    {
        "id": "rt-04-female-menstrual",
        "tags": ["routine", "gating"],
        "mode": "core",
        "note": "personal.menstrual is gated on sex and age. It must be reachable here.",
        "script": {
            "identity.respondent": "self", "identity.age_band": "18_39",
            "identity.sex": "female", "cc.primary": "menstrual_problem",
            "hpi.onset": "gradual", "hpi.duration": {"n": 6, "unit": "months"},
            "hpi.associated": ["none"], "hpi.severity": 6, "ros.danger_signs": ["none"],
            "past.conditions": ["none"], "drugs.allergy_known": "none",
            "drugs.taking_now": False, "personal.menstrual": "irregular",
            "docs.has_papers": False,
        },
        "expect": {"escalates": False, "slot_equals": {"personal.menstrual": "irregular"}},
    },
    {
        "id": "rt-05-male-never-offered-menstrual",
        "tags": ["routine", "gating"],
        "mode": "core",
        "note": "The gating control. A male patient must never be asked this.",
        "script": _s(**{
            "cc.primary": "cough", "hpi.onset": "gradual",
            "hpi.duration": {"n": 2, "unit": "weeks"}, "hpi.associated": ["none"],
            "hpi.severity": 3, "ros.danger_signs": ["none"], "past.conditions": ["none"],
            "drugs.allergy_known": "none", "drugs.taking_now": False,
            "docs.has_papers": False,
        }),
        "expect": {"node_not_asked": "personal.menstrual"},
    },
    {
        "id": "rt-06-cough-no-pain-questions",
        "tags": ["routine", "gating"],
        "mode": "core",
        "note": "A cough patient must not be asked where the pain radiates to.",
        "script": _s(**{
            "cc.primary": "cough", "hpi.onset": "gradual",
            "hpi.duration": {"n": 1, "unit": "weeks"}, "hpi.associated": ["fever"],
            "hpi.severity": 3, "ros.danger_signs": ["none"], "past.conditions": ["none"],
            "drugs.allergy_known": "none", "drugs.taking_now": False,
        }),
        "expect": {"node_not_asked": "hpi.radiation"},
    },
    {
        "id": "rt-16-returning-carries-and-shortens",
        "tags": ["routine", "returning", "budget"],
        "mode": "ayush",
        "returning": True,
        "note": (
            "The fast path, measured. A patient we already know arrives with the same "
            "kind of complaint. What was carried must not be asked again, and the "
            "interview must be materially shorter than the same patient as a stranger."
        ),
        "prefill": {
            "identity.age_band": "40_59", "identity.sex": "female",
            "past.conditions": ["diabetes"], "past.surgeries": "no",
            "past.hospitalisation": "no", "drugs.allergy_known": "none",
            "family.conditions": ["diabetes"], "personal.diet": "vegetarian",
            "personal.tobacco": "never", "personal.alcohol": "never",
            "ayush.prakriti_screen": ["pitta_sharp_appetite"],
        },
        "script": _s(**{
            "cc.primary": "abdominal_pain", "hpi.onset": "gradual",
            "hpi.duration": {"n": 3, "unit": "days"}, "hpi.associated": ["none"],
            "hpi.severity": 4, "ros.danger_signs": ["none"],
            "drugs.taking_now": False, "docs.has_papers": False,
        }),
        "expect": {
            "escalates": False,
            "required_all_asked": True,
            "prefilled_min": 10,
            "carried_not_reasked": True,
            # Time, not question count, is the constraint the throughput argument rests
            # on. A carried fact costs zero seconds, so the engine spends the freed
            # time on the current complaint instead — the visit gets shorter *and*
            # deeper, which is the opposite of what "fast path" usually means.
            "max_elapsed_s": 130,
        },
    },
    {
        "id": "rt-17-returning-never-carries-this-visit",
        "tags": ["returning", "safety"],
        "mode": "ayush",
        "returning": True,
        "note": (
            "The store is data from a previous version of this software and is treated "
            "as untrusted. A complaint, an HPI answer or a current imbalance sitting in "
            "it must be refused, not seeded — a patient arriving with a new problem who "
            "is handed last visit's chief complaint is the worst failure this path has."
        ),
        "prefill": {
            "identity.age_band": "60_74",
            "drugs.allergy_known": "none",
            # None of the following may ever be carried.
            "cc.primary": "chest_pain",
            "hpi.severity": 9,
            "ayush.vikriti": "pitta",
            "ros.danger_signs": ["chest_pain_radiating"],
        },
        "script": _s(**{
            "identity.age_band": "60_74",
            "cc.primary": "joint_pain", "hpi.onset": "gradual",
            "hpi.duration": {"n": 6, "unit": "months"}, "hpi.associated": ["none"],
            "hpi.severity": 5, "ros.danger_signs": ["none"],
            "drugs.taking_now": False, "docs.has_papers": False,
        }),
        "expect": {
            "escalates": False,
            "never_carried": ["cc.primary", "hpi.severity", "ayush.vikriti",
                              "ros.danger_signs"],
            "required_all_asked": True,
        },
    },
    {
        "id": "rt-07-returning-patient-budget",
        "tags": ["routine", "budget"],
        "mode": "ayush",
        "returning": True,
        "note": "90 second budget. Must still capture the required nodes.",
        "script": _s(**{
            "cc.primary": "abdominal_pain", "hpi.onset": "gradual",
            "hpi.duration": {"n": 2, "unit": "days"}, "hpi.associated": ["none"],
            "hpi.severity": 4, "ros.danger_signs": ["none"], "past.conditions": ["none"],
            "drugs.allergy_known": "none", "drugs.taking_now": False,
            "docs.has_papers": False,
        }),
        "expect": {"escalates": False, "required_all_asked": True},
    },
    {
        "id": "rt-08-skin-complaint",
        "tags": ["routine", "core"],
        "mode": "core",
        "script": _s(**{
            "cc.primary": "skin_problem", "hpi.onset": "gradual",
            "hpi.duration": {"n": 2, "unit": "months"}, "hpi.associated": ["none"],
            "hpi.severity": 3, "ros.danger_signs": ["none"], "past.conditions": ["none"],
            "drugs.allergy_known": "none", "drugs.taking_now": False,
            "docs.has_papers": False,
        }),
        "expect": {"escalates": False, "completes": True, "node_not_asked": "hpi.site"},
    },
    {
        "id": "rt-09-drug-allergy-always-asked",
        "tags": ["routine", "safety"],
        "mode": "ayush",
        "note": "Allergy is required. It must be asked even in the tightest budget.",
        "returning": True,
        "script": _s(**{
            "cc.primary": "headache", "hpi.onset": "gradual",
            "hpi.duration": {"n": 1, "unit": "days"}, "hpi.associated": ["none"],
            "hpi.severity": 3, "ros.danger_signs": ["none"],
            "drugs.allergy_known": "drug_allergy",
            "drugs.allergy_detail": "penicillin rash", "past.conditions": ["none"],
            "drugs.taking_now": False, "docs.has_papers": False,
        }),
        "expect": {"node_asked": "drugs.allergy_known", "escalates": False},
    },
    {
        "id": "rt-10-urinary-complaint",
        "tags": ["routine", "core"],
        "mode": "core",
        "script": _s(**{
            "cc.primary": "urinary_problem", "hpi.onset": "sudden",
            "hpi.duration": {"n": 3, "unit": "days"}, "hpi.associated": ["fever"],
            "hpi.severity": 6, "ros.danger_signs": ["none"], "past.conditions": ["none"],
            "drugs.allergy_known": "none", "drugs.taking_now": False,
            "docs.has_papers": False,
        }),
        "expect": {"escalates": False, "completes": True},
    },
    {
        "id": "rt-11-tobacco-and-alcohol",
        "tags": ["routine", "personal"],
        "mode": "core",
        "script": _s(**{
            "cc.primary": "cough", "hpi.onset": "gradual",
            "hpi.duration": {"n": 8, "unit": "weeks"}, "hpi.associated": ["weight_loss"],
            "hpi.severity": 4, "ros.danger_signs": ["none"], "past.conditions": ["none"],
            "drugs.allergy_known": "none", "drugs.taking_now": False,
            "personal.tobacco": "smoking", "personal.alcohol": "regular",
            "docs.has_papers": False,
        }),
        "expect": {"escalates": False, "slot_equals": {"personal.tobacco": "smoking"}},
    },
    {
        "id": "rt-12-injury",
        "tags": ["routine", "core"],
        "mode": "core",
        "script": _s(**{
            "cc.primary": "injury", "hpi.site": "knee", "hpi.onset": "sudden",
            "hpi.duration": {"n": 6, "unit": "hours"}, "hpi.associated": ["none"],
            "hpi.severity": 6, "ros.danger_signs": ["none"], "past.conditions": ["none"],
            "drugs.allergy_known": "none", "drugs.taking_now": False,
        }),
        "expect": {"escalates": False},
    },
    {
        "id": "rt-13-budget-never-drops-required",
        "tags": ["budget", "safety"],
        "mode": "ayush",
        "note": "The core invariant of the budget rule: required nodes are never "
                "displaced, no matter how tight the clock.",
        "returning": True,
        "script": _s(**{
            "cc.primary": "abdominal_pain", "hpi.onset": "sudden",
            "hpi.duration": {"n": 1, "unit": "days"}, "hpi.associated": ["none"],
            "hpi.severity": 5, "ros.danger_signs": ["none"], "past.conditions": ["none"],
            "drugs.allergy_known": "none", "drugs.taking_now": False,
            "ayush.ahara_shakti": "good_intake_good_digestion", "docs.has_papers": False,
        }),
        "expect": {"required_all_asked": True},
    },
    {
        "id": "rt-14-audit-trail-complete",
        "tags": ["audit"],
        "mode": "ayush",
        "note": "Every asked question must carry the reason it was asked.",
        "script": _s(**{
            "cc.primary": "chest_pain", "hpi.onset": "gradual",
            "hpi.duration": {"n": 5, "unit": "days"}, "hpi.associated": ["none"],
            "hpi.severity": 3, "identity.age_band": "18_39",
        }),
        "expect": {"audit_covers_asked": True},
    },
    {
        "id": "rt-15-determinism",
        "tags": ["determinism"],
        "mode": "ayush",
        "note": "Same input, same questions, same order. Run twice and compare.",
        "script": _s(**{
            "cc.primary": "headache", "hpi.site": "one_side_head", "hpi.onset": "gradual",
            "hpi.duration": {"n": 1, "unit": "months"}, "hpi.associated": ["nausea"],
            "hpi.severity": 5, "ros.danger_signs": ["none"], "past.conditions": ["none"],
            "drugs.allergy_known": "none", "drugs.taking_now": False,
        }),
        "expect": {"deterministic": True},
    },
]


def by_tag(tag: str) -> list[dict]:
    return [s for s in SCENARIOS if tag in s["tags"]]
