# Requirements

Three tiers: **Gates** (fail one = disqualified in spirit), **Must-haves**
(the brief demands them), **Lose conditions** (actively costs us).

---

## Tier 0 — The five gates

Each is stated or directly implied in the official text. Judges from Ayush will check.

### G1 · No smartphone, no prior enrolment, no assumed connectivity

Section 2.2 explicitly rejects mobile apps and tele-triage chatbots for requiring
"smartphone literacy, stable connectivity, and patient enrolment ahead of the visit."

The primary flow must work for a **walk-in, first-visit patient carrying nothing**.
A companion phone app may exist as a *secondary* convenience, never as the main path.
Network must be assumed unreliable: degrade to local operation and sync later.

### G2 · Dual-mode input on every question

Section 3.3 Module A: "every question answerable by speaking OR tapping."

Not voice-with-a-fallback. **Both, at parity, on every single node** of the interview.
Every question in our model therefore needs:
- a spoken form (TTS prompt)
- a tappable form (icon + large-target options)
- a way to accept either as the answer to the same slot

This constrains the entire question schema. Design it in from the start; retrofitting
touch onto a voice-first flow does not work.

### G3 · The physician is the authority

"The summary is a draft to accept, amend, or reject, never an autonomous diagnosis."

- No screen anywhere states or implies a diagnosis
- The doctor view is editable, with accept / amend / reject
- Nothing is written to the permanent record until the doctor confirms

### G4 · Red flags escalate, never queue

"Triggers immediate priority alert to triage staff rather than routine queueing."

- A defined, written list of red-flag conditions (not LLM judgement alone)
- Tune for **recall**, accept false positives
- The system may **upgrade** urgency, never downgrade it
- Escalation stops the interview and alerts staff — it is not a note in the summary

### G5 · AYUSH mode is the point, not a feature

This is a **Ministry of Ayush** problem statement. A generic allopathic intake with a
dosha quiz bolted on reads as not having done the homework.

The brief names all ten Dashavidha Pariksha parameters explicitly:
Prakriti, Vikriti, Sara, Samhanana, Pramana, Satmya, Sattva, Ahara Shakti,
Vyayama Shakti, Vaya — plus Ahara-Vihara (diet and lifestyle).

See `05-domain-reference.md` for the official instruments and code systems that exist.
**Use the official ones. Do not invent a dosha questionnaire.**

---

## Tier 1 — Must-haves from the brief

### Module A — Conversational history engine
- Adaptive branching driven by chief complaint and prior answers
- SOCRATES probing for pain complaints (onset, character, radiation, aggravating/relieving, etc.)
- Full standard history: chief complaint, HPI, past medical/surgical, drug & allergy,
  family, personal, review of systems
- AYUSH extended mode (see G5)
- Indian-language ASR, multi-accent, **in noise**
- TTS audio prompts
- Red-flag detection (see G4)

### Module B — Document digitization
- OCR of **printed and handwritten**, multilingual
- Extract: diagnoses, medications with dosages, investigation results with values
  and reference ranges, procedure/surgery history
- Auto-date and chronologically order into a timeline
- Flag out-of-range lab values
- Flag potential drug interactions

### Module C — Summary generator
- Standard clinical format, in the brief's stated order:
  Chief complaint → HPI → Past medical/surgical → Drug & allergy → Family →
  Personal → ROS → Prior investigations summary
- Editable and verifiable by the physician
- Bilingual: patient-facing audio confirmation in local language; physician-facing
  summary in English/Hindi

### Module D — Consent, privacy, ABDM
- ABHA ID authentication (with a no-ABHA fallback path — see G1)
- Explicit, granular, revocable consent
- **Audio-explained consent** for low-literacy patients
- DPDP Act 2023 compliance
- Push structured history to hospital HIS/EMR and link to ABHA record via FHIR
- **Session data cleared immediately after submission**

---

## Tier 2 — Requirements the brief doesn't state but reality does

### R1 · Who is actually answering?
In an Indian OPD the son routinely answers for his mother. "I have chest pain" from a
proxy is a different clinical fact from the patient saying it. Capture respondent
identity (self / relative / attendant) and mark proxy-sourced fields in the summary.
This is data integrity, not a nice-to-have.

### R2 · Abandonment
People walk away mid-session. Define what happens: partial save? discard? resume?
A half-finished history reaching the doctor unmarked is worse than none.

### R3 · Shared-device hygiene
Public terminal, back-to-back strangers. Hard session reset, visible "session ended"
state, no back button into the previous person's data, timeout on inactivity.

### R4 · Noise
Hospital waiting halls are loud. Clean-audio ASR numbers are meaningless here.
Every voice claim must be measured with realistic noise mixed in.

---

## Lose conditions

Things that actively cost us marks:

| Don't | Why |
|---|---|
| Build a diagnosis engine | Violates G3, and it's the most common failure mode |
| Demo a chatbot in a browser window | It must look and behave like a terminal — big targets, no keyboard, no scrolling text walls |
| Fake the ABDM integration | The sandbox is real and has a defined integration path. Faking it is checkable. |
| Cloud-only architecture | Violates G1. Assume the network drops. |
| Treat AYUSH mode as a checkbox | Violates G5, and it's the sponsor's own reason for posting |
| Keep session data after submission | Explicitly forbidden in the brief; DPDP 2023 backs it |
| Require the patient to read | Every prompt must be spoken and icon-supported |
| Invent our own Prakriti questionnaire | An official validated one exists. Using ours looks amateur. |
