# Aapka

**Smart India Hackathon 2026 · PS 26047 — Patient Case-Taking Software**
Ministry of Ayush

A self-service **pre-consultation intake terminal** for government hospital outpatient
queues. A patient walks up to a touchscreen in the waiting hall — alone, first time,
no training, no smartphone — answers questions by **speaking or tapping**, and holds
their old prescriptions up to a camera. By the time their token is called, a structured
medical history is already on the doctor's screen.

It is not a records app, not a patient portal, not a chatbot. **It never diagnoses.**

---

## Run it

```powershell
git clone https://github.com/Kukyos/Aapka.git
cd Aapka
.\run.ps1 -Setup     # once
.\run.ps1
```

| | |
|---|---|
| Patient kiosk | http://localhost:5173 |
| Doctor screen | http://localhost:5174 — token `demo-doctor-token` |
| Server health | http://localhost:8000/api/health |

Use **Chrome** — the kiosk uses its built-in speech recognition and synthesis.

No Docker, no Postgres, no API keys required. With no `.env` at all the whole system
runs on its deterministic paths, which is the behaviour gate G1 demands anyway. Add a
`GROQ_API_KEY` to `.env` to switch on the model rungs.

```powershell
.\run.ps1 -Test      # unit tests, eval harness, budget sweep
```

---

## The one architectural rule

**The flowchart drives the conversation, not the AI.**

```
Deterministic question graph  ->  decides WHICH question, WHEN, and when to STOP
        (ontology/, as data)

Language model                ->  only ever:
                                  - maps one utterance onto one already-chosen slot,
                                    returning a declared option or "unclear"
                                  - phrases a question that already exists
```

A slot declares its legal values and the model is held to them. That single constraint
is what makes invented history **structurally impossible** rather than merely unlikely,
and it is why the interview has a bounded length, provable coverage, and an audit trail
you can put in front of a ministry.

Details in [`docs/09-architecture.md`](docs/09-architecture.md).

---

## What it does

| Module | Status |
|---|---|
| **A — Conversational history engine** | 59-node ontology, deterministic dialogue engine, 20 red-flag rules, dual input on every question, English + Hindi |
| **B — Document digitisation** | Vision-LLM OCR with Tesseract fallback, entity extraction, dated timeline, out-of-range flagging, interaction screening |
| **C — Summary generator** | Templated assembly in the brief's exact section order, spoken read-back to the patient before submission, editable by the doctor, accept / amend / reject |
| **D — Consent, privacy, ABDM** | Audio-explained granular consent, ABHA card scan **and** a working no-ABHA path, real FHIR R4 bundles, session wipe on submission (asserted by a test) |

---

## Measured, not claimed

Every number here comes from `server/eval/` and is reproducible with `.\run.ps1 -Test`.

| | |
|---|---|
| Eval scenarios passing | **47 / 47** |
| Red-flag recall | **1.00** (9 / 9) with the false-positive control passing |
| Voice mapped **offline** — no network, no model | **0.85** (11 / 13) |
| Voice mapped with the model rung on | **0.92** (12 / 13) |
| Returning patient, 11 facts carried | **101 s** against 364 s as a stranger |
| Dashavidha Pariksha captured in a 6-minute AYUSH interview | **10 of 10** |
| SOCRATES dimensions captured | **7 of 7** |
| Unit + API tests | **64 passing** |

**Not measured, and not quoted anywhere:** ASR word error rate and OCR accuracy. Those
need hospital noise recordings and real handwritten prescriptions, and neither exists
yet. See [`docs/11-deferred.md`](docs/11-deferred.md).

Two things the harness found that no screen would have shown:

- A four-minute AYUSH interview captures only **5 of 10** Dashavidha parameters. The
  budget is now 360 s for AYUSH mode, with the full trade-off curve in
  [`docs/12-budget-findings.md`](docs/12-budget-findings.md).
- Seven red-flag rules read review-of-systems answers that the budget always displaced,
  so those rules **could never fire**. Fixed with a required danger-signs screen asked
  early.

---

## Docs — read in this order

| File | What's in it |
|---|---|
| [`00-start-here.md`](docs/00-start-here.md) | The map. Start here. |
| [`01-problem-statement.md`](docs/01-problem-statement.md) | **The official text, verbatim. Source of truth.** |
| [`02-product.md`](docs/02-product.md) | What we're building, plain language. |
| [`03-requirements.md`](docs/03-requirements.md) | Five gates, must-haves, lose conditions. |
| [`04-targets.md`](docs/04-targets.md) | Numbers to hit and the eval harness. |
| [`05-domain-reference.md`](docs/05-domain-reference.md) | Glossary, official AYUSH/ABDM resources. |
| [`06-decisions.md`](docs/06-decisions.md) | Decided vs open. |
| [`07-build-plan.md`](docs/07-build-plan.md) | Phase-by-phase order of work. |
| [`08-rules-and-conventions.md`](docs/08-rules-and-conventions.md) | The hard rules, one page. |
| [`09-architecture.md`](docs/09-architecture.md) | **The two contracts.** Read before writing code. |
| [`10-unsourced.md`](docs/10-unsourced.md) | Every value we could not source, and where the real one comes from. |
| [`11-deferred.md`](docs/11-deferred.md) | Everything knowingly incomplete. |
| [`12-budget-findings.md`](docs/12-budget-findings.md) | What fits in the interview, measured. |
| [`13-eval-results.md`](docs/13-eval-results.md) | Generated by the harness. |
| [`14-novelties.md`](docs/14-novelties.md) | Proposed differentiators, and which survived the gates. |
| [`15-what-you-can-unblock.md`](docs/15-what-you-can-unblock.md) | Owner-only work, and the audit against the brief. |

---

## Layout

```
ontology/     the question graph, as data. Edit without a rebuild.
server/       FastAPI at the edge, pure modules underneath
  aapka/      engine, red flags, NLU, OCR, summary, FHIR, ABDM
  eval/       47 scenarios, runner, scorer, budget sweep
  tests/      64 tests
patient/      React kiosk
doctor/       React consultation view
```

The kiosk flow is
`attract -> language -> consent -> identify -> [welcome back] -> interview -> documents -> read-back -> done`,
with a red flag cutting straight to the escalation screen from anywhere in the
interview.

`server/aapka/engine.py` imports no web framework and touches no database. It is a
pure function of (ontology, session) to next action — which is what makes the eval
harness cheap and the behaviour reproducible.

---

## Honesty notes

Stated up front because a judge will look for exactly these:

- **ABDM transport is mocked.** The FHIR R4 bundle is real and structurally validated;
  the sandbox is not yet registered. Every mock response says so and the doctor screen
  renders the notice in its footer. One config flag switches it.
- **ICD-11 codes are sourced; NAMASTE codes are not.** The 13 complaint codes and the
  three dosha pattern codes were pulled from the WHO ICD-11 API on 2026-09-04 and are
  checkable at <https://icd.who.int/browse/2025-01/mms/en>. NAMASTE stays empty — that
  list is not publicly downloadable, and a fabricated code is the specific failure mode
  the ministry that owns the portal would catch. A test enforces that no unverified
  code can leave the system.
- **No TM2 code is attached to a chief complaint, and that is deliberate.** TM2 codes
  disorders — "Cough disorder (TM2)" — so attaching one to a patient who said they have
  a cough would be a diagnosis made by a kiosk. We hold all 648 TM2 codes and decline
  to use them there. The dosha *pattern* codes are different: they carry what the
  patient said about their own imbalance, marked unconfirmed for the physician.
- **The Prakriti block is an abbreviated screen** built from classical public-domain
  descriptions, not the CCRAS 91-item instrument. It is labelled as a screen everywhere
  it appears, and never as a determination.
- **Red-flag rules have not been reviewed by a clinician.** That review is a submission
  blocker.

---

## Deadline

Idea submission closes **20 September 2026**.
