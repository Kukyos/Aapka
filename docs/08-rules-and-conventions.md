# Rules and conventions

The short version of everything else. If you read one file before writing code,
read this one — then check the doc it points at.

## What this is

A self-service **pre-consultation intake terminal** for Indian government hospital
outpatient queues, sponsored by the Ministry of Ayush. A patient uses a touchscreen in
the waiting hall — alone, first time, no training — to record their medical history by
voice or touch and scan their old prescriptions. A structured summary is waiting on the
doctor's screen before the patient walks in.

Three deliverables: **patient screen**, **doctor screen**, **server**.

## Hard rules

Do not violate these without an explicit decision logged in `06-decisions.md`.

1. **Never diagnose.** No screen states or implies a diagnosis. Output is a history.
2. **Dual input everywhere.** Every question answerable by speaking OR tapping, at parity.
3. **No smartphone / no sign-up / no assumed connectivity** in the primary flow.
4. **The ontology drives the dialogue, not an LLM.** A deterministic question graph decides
   which question comes next and when to stop. Language models do utterance→slot mapping
   and phrasing only.
5. **Red flags escalate immediately**, stopping the interview. Tune for recall.
6. **Session data is wiped on submission.**
7. **AYUSH mode is core, not a feature.** Use official CCRAS / NAMASTE instruments,
   never an invented dosha questionnaire.
8. **Interview time budget is a hard constraint.** New questions displace old ones.

## Working defaults

From `06-decisions.md`. These exist so nobody is ever blocked — override freely,
just log it.

- Interview budget: 4 min new patient, 90 s returning
- AYUSH-first, allopathic as general mode
- Ontology hand-built; output emits NAMASTE + ICD-11 codes
- On-device ASR (IndicConformer), cloud for heavier work with local fallback
- Patient + doctor screens: React + TypeScript + Vite + Tailwind
- Server: Python / FastAPI. DB: Postgres
- Ontology lives as data (JSON/YAML), not code

## Build order

Phase 1 first: **question ontology + deterministic dialogue engine + eval harness.**
No UI, no models. If the spine and its measuring tool are solid, everything after is
decoration. Details in `07-build-plan.md`.

## Conventions

- Ontology is data, editable without a rebuild
- Every claim about accuracy or speed comes from the eval harness, never a guess
- ASR numbers are only valid with hospital noise mixed in
- OCR numbers for handwritten and printed are reported separately
- `01-problem-statement.md` is the official text, verbatim. Never paraphrase it in place;
  quote it.

## Deadline

Idea submission closes **20 September 2026**.
