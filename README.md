# Aapka

**Smart India Hackathon 2026 · PS 26047 — Patient Case-Taking Software**
Ministry of Ayush

A self-service **pre-consultation intake terminal** for government hospital outpatient
queues. A patient walks up to a touchscreen in the waiting hall — alone, first time,
no training, no smartphone — answers questions by **speaking or tapping**, and holds
their old prescriptions up to a camera. By the time their token is called, a structured
medical history is already on the doctor's screen.

It is not a records app, not a patient portal, not a chatbot. **It never diagnoses.**

## The three pieces

| Piece | What it is |
|---|---|
| **Patient screen** | Touchscreen kiosk in the waiting hall. Speaks, listens, has a camera. |
| **Doctor screen** | Web page in the consulting room. One-page summary, readable in 15 seconds. |
| **Server** | Question graph, speech-to-text, document OCR, summary generation, ABDM. |

## The one architectural rule

**The flowchart drives the conversation, not the AI.** A deterministic question graph
decides which question comes next and when to stop. Language models only map what the
patient said onto a field and phrase questions naturally. That is what gives bounded
interview time, provable coverage, no invented symptoms, and an auditable trail.

## Docs — read in this order

Everything decided so far lives in [`docs/`](docs/).

| File | What's in it |
|---|---|
| [`00-start-here.md`](docs/00-start-here.md) | The map. Start here. |
| [`01-problem-statement.md`](docs/01-problem-statement.md) | **The official text, verbatim. Source of truth.** |
| [`02-product.md`](docs/02-product.md) | What we're building, plain language. The end-to-end walkthrough. |
| [`03-requirements.md`](docs/03-requirements.md) | Five gates, must-haves, lose conditions. |
| [`04-targets.md`](docs/04-targets.md) | Numbers to hit, throughput math, the eval harness. |
| [`05-domain-reference.md`](docs/05-domain-reference.md) | Glossary, official AYUSH/ABDM resources, the architectural rule. |
| [`06-decisions.md`](docs/06-decisions.md) | Decided vs open, with recommended defaults. |
| [`07-build-plan.md`](docs/07-build-plan.md) | Phase-by-phase order of work. Pick what to do next here. |
| [`08-rules-and-conventions.md`](docs/08-rules-and-conventions.md) | The hard rules, in one page. |

## Status

Pre-code. Docs and decisions only.

**Next up — Phase 1, the spine:** question ontology as data, deterministic dialogue
engine, red-flag rule set, eval harness. No UI, no models yet.
See [`docs/07-build-plan.md`](docs/07-build-plan.md).

## Deadline

Idea submission closes **20 September 2026**.
