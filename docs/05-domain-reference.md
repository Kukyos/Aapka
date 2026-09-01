# Domain reference

Glossary first, then the things that actually exist and are worth using.

---

## Glossary

**OPD** — Outpatient Department. The walk-in clinic queue. Where this all happens.

**ABHA** — Ayushman Bharat Health Account. A free government health ID number.
Like Aadhaar, but for health records. The patient's key.

**ABDM** — Ayushman Bharat Digital Mission. The national health data network that
ABHA belongs to. If we push a record into it, the patient's *next* hospital can see it.

**HIS / EMR** — Hospital Information System / Electronic Medical Record. The hospital's
own internal software. We push our summary into it.

**FHIR** — an agreed format for writing health data down so different hospital systems
can read each other's files. Structurally it's just JSON with standardised field names.

**ASR** — Automatic Speech Recognition. Speech → text.

**TTS** — Text To Speech. The machine talking out loud.

**OCR** — Optical Character Recognition. Reading text out of a photo of a document.

**Ontology** — for our purposes: a structured list of the questions and how they connect.
A flowchart of questions. Nothing more mystical than that.

**Dialogue manager** — the code that decides which question comes next.
**Important:** this should be *our flowchart*, not an LLM improvising. See below.

**HPI** — History of Present Illness. The story of the current complaint.

**ROS** — Review of Systems. A quick sweep of every body system for anything missed.

**SOCRATES** — a standard checklist for probing pain:
Site, Onset, Character, Radiation, Associations, Time course, Exacerbating/relieving
factors, Severity. The brief names it explicitly.

**DPDP Act 2023** — India's data protection law. Governs how we handle health data.

### Ayurveda terms

**Dashavidha Pariksha** — the ten-point examination. The brief names all ten:
Prakriti, Vikriti, Sara, Samhanana, Pramana, Satmya, Sattva, Ahara Shakti,
Vyayama Shakti, Vaya.

**Prakriti** — a person's constitutional type. Considered stable for life.
**Vikriti** — the current imbalance / deviation from Prakriti.
**Agni** — digestive capacity.
**Koshtha** — bowel nature.
**Ahara-Vihara** — diet and lifestyle.
**Nidana** — causative factors.
**Samprapti** — pathogenesis, how the disease developed.
**Trividha / Ashtavidha / Dashavidha Pariksha** — three-fold, eight-fold and ten-fold
examination frameworks. Increasing depth.

---

## Things that exist — use them, don't reinvent

### For the AYUSH module (this is where the marks are)

**CCRAS standardized Prakriti Assessment Tool.** The Central Council for Research in
Ayurvedic Sciences has already developed and validated a standardized Prakriti
assessment scale, and runs an *Ayur Prakriti* web portal. Implementing the official
instrument instead of inventing our own questionnaire is the single cheapest
credibility win available to us.
- https://journals.lww.com/aayu/fulltext/2022/43040/development_of_a_standardized_assessment_scale_for.1.aspx

**NAMASTE Portal** — National AYUSH Morbidity and Standardized Terminologies
Electronic portal. The official code list for Ayurveda / Siddha / Unani diagnoses
and terminology. If our structured output emits NAMASTE codes, we are literally
speaking the Ministry's own language.
- https://namaste.ayush.gov.in/about-namaste-portal

**ICD-11 TM Module 2.** The WHO's traditional-medicine chapter. India has a live
roadmap to dual-code NAMASTE against ICD-11 TM2. Dual-coding our output
(NAMASTE + ICD-11) is a strong, checkable move.
- https://journals.lww.com/ijar/fulltext/2025/10000/india_s_roadmap_for_icd_11_tm2_implementation_.18.aspx

**Prakriti200** — a public dataset of 200 questionnaire-based Prakriti assessments
(arXiv, 2025). Small, but it's real data and it exists.
- https://arxiv.org/html/2510.06262v1

### For speech

**AI4Bharat IndicConformer 600M multilingual** — open-weight multilingual Indian
ASR on HuggingFace. **Runs locally**, which is what lets us satisfy the
no-assumed-connectivity gate.
- https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual
- Model family / benchmarks: https://ai4bharat.iitm.ac.in/areas/asr

**Bhashini** — the government's language platform, named in the brief. Worth citing
even if we run IndicConformer locally.

### For ABDM

**ABDM Sandbox** — real developer sandbox with a defined M1 / M2 / M3 milestone
integration path. Faking ABDM is checkable; using the sandbox is not much harder.
- https://kiranma72.github.io/abdm-docs/
- https://docs.coronasafe.network/abdm-documentation/implementers-guide/abdm-sandbox-integration-and-exit-process

---

## The one architectural call that matters

**The dialogue manager must not be an LLM.**

The brief's own wording is *"a dialogue manager constrained by a clinical history
ontology."* Note "constrained by."

If you prompt an LLM to "take a patient history" you get:
- unbounded conversation length (kills the 4-minute target)
- invented symptoms the patient never mentioned
- no guarantee any particular field was covered
- non-deterministic structure
- nothing you can audit or explain to a Ministry

The correct shape:

```
Deterministic question graph  →  decides WHICH question, WHEN, and when to STOP
        (our ontology)

LLM                           →  used only for:
                                 - NLU: map a free-form utterance onto a slot value
                                 - NLG: phrase the next question naturally in the
                                        patient's language
```

Consequences of getting this right:
- Bounded, predictable interview time
- Provable coverage — "we captured 9 of 9 SOCRATES dimensions"
- No hallucinated history
- Fully auditable — you can show exactly why each question was asked
- Small enough to run on-device

**Build the ontology first. It is the actual product. The models are components.**
