# Decisions log

Append-only. When a decision is made, move it up and date it.
Recommended defaults exist so a build session is never blocked — override freely.

---

## Decided

**2026-08-29 · PS choice.** Going with SIH26047 (Patient Case-Taking Software),
Ministry of Ayush. Other shortlisted PS for reference: 26003, 26043, 26044, 26188,
26031, 26067, 26175, 26104.

**2026-09-02 · D1 answered, on measurement.** Interview budget is per mode, not one
number: **360 s AYUSH, 240 s core, 90 s returning.** D1's original 240 s default was
measured against the real graph and found to capture only 5 of the 10 Dashavidha
parameters, which undercuts gate G5. 360 s captures 10 of 10 and 7 of 7 SOCRATES; past
that the curve is flat and only the terminal count grows. Full curve, throughput
arithmetic and the returning-patient offset in `12-budget-findings.md`.

**2026-09-02 · D3 answered. AYUSH-first**, as recommended. Expressed in the ontology as
priority ordering: the Dashavidha block sits ahead of the review-of-systems sweep, so
when the budget runs out it is the general sweep that gets displaced. Allopathic intake
ships as core mode.

**2026-09-02 · D7 answered. Stack** as recommended, with two changes forced by the
"git clone and one command" constraint: **SQLite instead of Postgres** (one line to
switch back) and **no Docker**. Groq for cloud inference with an Ollama local fallback
and a deterministic keyword matcher underneath, so the kiosk still completes an intake
with no network at all.

**2026-09-03 · Aadhaar. We do not take it.** Brief section 3.4 Step 1 offers three ways
to identify a patient — ABHA ID, Aadhaar details, or register as new. We implement the
ABHA path and a first-class "I do not have one" path, and we do not implement Aadhaar
entry or on-the-spot ABHA creation.

Reasoning, to be stated in the submission rather than left silent: creating an ABHA from
an Aadhaar number is an ABDM flow that needs sandbox credentials we do not have (D-03),
so it cannot be built truthfully today either way; handling Aadhaar numbers carries real
DPDP Act weight for no demonstrable benefit; and collecting the fewest identifiers that
do the job is a stronger position in front of a judge than collecting more. Gate G1 —
a walk-in carrying nothing completes an intake — is already satisfied by the decline
path. Revisit if the sandbox lands early.

**2026-09-03 · Returning-patient fast path ships with a local source.** The prefill
mechanism is real; the source of the previous visit is our own store rather than ABHA
until D-03 closes. Mirrors the existing `ABDM_MODE=mock|sandbox` split — one config flag
swaps the source and nothing above it changes. Labelled on the doctor screen and in
`/api/health` as local, never as ABDM, because faking ABDM is a named lose condition.

**2026-09-03 · Bhashini adopted as the ASR and TTS path for Indian languages.** Brief
section 1.3 names Bhashini / AI4Bharat by name. It is the government's own language
platform on a Ministry problem statement, its speech-to-text takes a `medical` domain
parameter, and it is the route to the "major regional languages" section 2.3 asks for.
Goes behind the existing adapter in `asr.py`; the browser recogniser stays underneath it
as the offline rung, because gate G1 does not permit a network dependency.

**2026-08-29 · Product shape.** Self-service pre-consultation intake terminal, not a
records app. Patient screen + doctor screen + server. See `02-product.md`.

---

## Open — with a recommended default

### D1 · How long is the interview allowed to take?
**This decides everything else.** Question count, branching depth, whether AYUSH mode
is full or abbreviated, and how many terminals a hospital needs.

*Recommended default:* **4 minutes for a new patient, 90 seconds for a returning one.**
Treat it as a hard budget — new questions must displace existing ones, not add to them.

### D2 · What backs the interview ontology?
Options: (a) hand-build from SOCRATES + standard history structure;
(b) map onto SNOMED CT; (c) ICD-11 + NAMASTE dual coding.

*Recommended default:* **hand-build the question graph ourselves, but emit NAMASTE +
ICD-11 codes on the output side.** Full SNOMED mapping is a time sink with little
visible payoff. The output coding is the part judges can see.

### D3 · AYUSH-first or allopathic-first?
Can't do both excellently in the time available.

*Recommended default:* **AYUSH-first.** The PS is from the Ministry of Ayush; the
Ayurvedic depth is the stated gap; and it's where the differentiation lives. Ship
allopathic intake as the general mode, AYUSH as the deep mode.

### D4 · On-device or cloud inference, and what does offline degradation look like?
*Recommended default:* **on-device ASR (IndicConformer runs locally), cloud for the
heavier language work with a local fallback.** Must keep working when the network
drops — queue and sync. Gate G1 depends on this.

### D5 · What is the demo device?
*Recommended default:* **a real touchscreen — a cheap Android tablet on a stand, or a
touch monitor.** A laptop running fullscreen reads as a web app and undercuts the
whole pitch. Decide now: it changes target sizes, input model, and layout.

### D6 · How do we get handwritten prescriptions to test on?
*Recommended default:* start collecting **this week** from family, friends, local
clinics. This is the longest lead-time item in the project and OCR claims are
worthless without it.

### D7 · Stack
*Recommended default (change if you disagree):*
- Patient screen: React + TypeScript + Vite + Tailwind, kiosk mode
- Doctor screen: same stack, separate app
- Server: Python (FastAPI) — needed anyway for ASR/OCR
- DB: Postgres
- Keep the ontology as data (JSON/YAML), not code, so it can be edited without a rebuild

### D8 · Team split
Unresolved. Last two SIH attempts ran with one builder and no team contribution —
worth deciding explicitly up front who owns what, and what happens if they don't
deliver. The doc-and-ontology work is genuinely parallelisable; the ontology,
the eval scenarios, the icon set, and the AYUSH content are all things someone
non-technical can own.

---

## Rejected

**Mobile app as the primary flow.** Explicitly rejected by the problem statement
(section 2.2) for requiring smartphone literacy, connectivity and prior enrolment.
May exist as a secondary convenience only.

**Inventing our own Prakriti questionnaire.** A CCRAS-validated standardized
instrument already exists. See `05-domain-reference.md`.

**LLM-driven dialogue.** See the architectural note at the end of
`05-domain-reference.md`. Ontology drives; LLM assists.
