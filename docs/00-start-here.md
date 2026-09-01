# SIH 2026 · PS 26047 — Patient Case-Taking Software

Everything decided, learned and observed so far. Start here.

## The 30-second version

We're building a **self-service intake terminal for hospital waiting halls**.
A patient walks up to a screen, answers questions by talking or tapping, holds up
their old prescriptions to a camera, and walks away. By the time they reach the
doctor, a complete structured medical history is already on the doctor's screen.

Sponsor is the **Ministry of Ayush**, so the Ayurvedic depth is the point, not garnish.

It is not a records app. It is not a chatbot. It never diagnoses anything.

## The files

| File | What's in it | When to read |
|---|---|---|
| `01-problem-statement.md` | **The official text, verbatim.** Source of truth. | First. Then whenever there's an argument about scope. |
| `02-product.md` | What we're building, in plain words. The Kamala walkthrough. | Second. Whenever someone's confused about the shape. |
| `03-requirements.md` | Five gates, must-haves, lose conditions. | Before designing anything. |
| `04-targets.md` | Numbers to hit, throughput math, the eval harness. | Before writing the first feature. |
| `05-domain-reference.md` | Glossary + official AYUSH/ABDM resources + the one architectural rule. | When a term is unfamiliar, or before touching the dialogue engine. |
| `06-decisions.md` | Decided vs open, with recommended defaults. | Now, and every time something is settled. |
| `07-build-plan.md` | Phase-by-phase order of work. | To pick what to do next. |

## The five things that decide this

1. **No smartphone, no sign-up, no assumed internet.** The brief explicitly rejects
   app-based solutions. A stranger walks up to a screen and uses it once.
2. **Every question answerable by voice OR touch.** Both, at parity, everywhere.
3. **Never diagnose.** Output is a history. The doctor decides.
4. **Red flags break the queue**, they don't get noted in a summary.
5. **AYUSH depth is the differentiator.** Official validated instruments exist —
   use them, don't invent a dosha quiz.

## The one architectural rule

**The flowchart drives the conversation, not the AI.** A deterministic question graph
decides which question comes next and when to stop. The LLM only maps what the patient
said onto a field, and phrases questions naturally. This is what gives bounded time,
provable coverage, no invented symptoms, and an auditable trail.

Build the ontology first. Details in `05-domain-reference.md`.

## Start here, today

1. Answer **D1** (how long the interview may take) and **D3** (AYUSH-first?) in `06-decisions.md`
2. Start collecting **handwritten prescriptions** — longest lead time in the project
3. Register for the **ABDM sandbox** — has a milestone process, takes time
4. Build **Phase 1** from `07-build-plan.md`: ontology + dialogue engine + eval harness.
   No UI, no models. Just the spine.

## Known unknowns

- The official text references a **Table 3.2 that the portal never renders**. Check
  again before submission in case they patch it.
- We don't have the dataset link, YouTube link or SPOC contact from the listing modal.
- Deadline: **20 September 2026**. Idea submissions were at 0/500 on 29 Aug 2026.
