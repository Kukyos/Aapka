# Build plan

Ordered so that the riskiest, longest-lead things start first and the demo is
always in a showable state.

Principle: **the ontology and the eval harness come before the models.**
Everything else is replaceable; those two are the product.

---

## Phase 0 — Unblock the long poles (do these in parallel, week 1)

- [ ] Start collecting **real handwritten prescriptions**. Photos. Family, friends,
      local clinics. Target 50+. Longest lead time in the project.
- [ ] Record **hospital ambient noise** for the ASR eval.
- [ ] Find an **Ayurvedic practitioner** to talk to for 30 minutes. One conversation
      beats a week of reading.
- [ ] Register for the **ABDM sandbox** — there's a milestone process, it takes time.
- [ ] Re-check the portal for the **missing Table 3.2** and pull the dataset link,
      YouTube link and SPOC contact.
- [ ] Answer **D1 (interview time budget)** and **D3 (AYUSH-first?)** from `06-decisions.md`.

## Phase 1 — The spine

Nothing here needs a model. All of it is testable.

- [ ] **Question ontology as data.** JSON/YAML. Each node needs: id, slot it fills,
      spoken prompt (per language), tappable options with icon references, answer type,
      branching rules, and whether it's core or AYUSH-mode.
- [ ] **Deterministic dialogue engine.** Walks the graph, tracks filled slots, decides
      the next question, knows when to stop. Pure function, unit-testable, no AI.
- [ ] **Red-flag rule set.** A written list, evaluated deterministically. Not LLM judgement.
- [ ] **Eval harness.** 40 scripted scenarios with hand-written ground-truth histories,
      a runner, and a scorer that prints a table. Include red-flag, proxy-respondent,
      abandonment, AYUSH and deliberately-messy cases.

**Milestone:** you can run the whole interview as a text script in a terminal and the
eval harness prints coverage and accuracy numbers. No UI, no models. If this is solid,
everything after it is decoration.

## Phase 2 — The patient screen

- [ ] Kiosk shell: fullscreen, no browser chrome, no keyboard, huge targets
- [ ] Attract loop → language select (spoken + scripts) → consent (audio-explained)
- [ ] Question renderer driven entirely by the ontology data
- [ ] **Touch path first**, complete and usable on its own (satisfies G2 from one side)
- [ ] Icon set for symptoms and options — a real design task, not clip art
- [ ] Session reset and inactivity timeout

**Milestone:** a person who cannot read can complete a full intake by tapping icons
and listening. Test this on an actual person.

## Phase 3 — Voice

- [ ] TTS prompts per language
- [ ] IndicConformer ASR running locally
- [ ] Utterance → slot mapping (this is where the LLM earns its keep)
- [ ] Barge-in, retry, "I didn't catch that" handling
- [ ] Run the eval harness **with noise mixed in** and report WER honestly

**Milestone:** same intake completes by voice alone, and you have a WER number
measured in noise.

## Phase 4 — Documents

- [ ] Camera capture with framing guides
- [ ] OCR pipeline, printed first then handwritten
- [ ] Entity extraction: diagnoses, medications + dosages, lab values + reference ranges
- [ ] Date extraction and chronological ordering
- [ ] Out-of-range value flagging
- [ ] Drug interaction flagging

**Milestone:** hold a real crumpled prescription to the camera, get structured
medications out, with an F1 number for handwritten specifically.

## Phase 5 — Doctor screen

- [ ] One-page summary in the brief's exact section order
- [ ] Abnormal values highlighted, timeline of prior documents
- [ ] Proxy-sourced fields visibly marked
- [ ] Accept / amend / reject — nothing permanent until confirmed
- [ ] Optimised to be *read in 15 seconds*, not to be comprehensive

**Milestone:** hand it to someone who has never seen it and time how long they take
to understand the patient.

## Phase 6 — ABDM and consent

- [ ] ABHA authentication, plus the no-ABHA fallback path
- [ ] Granular, revocable, audio-explained consent
- [ ] FHIR bundle generation
- [ ] Push to sandbox HIS / link to ABHA record
- [ ] Session data wipe on submission — and prove it

## Phase 7 — The pitch layer

- [ ] Returning-patient fast path (pull last visit, confirm, ask only what's new)
- [ ] Red-flag escalation demo — rehearse this, it's the most memorable 20 seconds
- [ ] The throughput slide from `04-targets.md`
- [ ] Final numbers table from the eval harness
- [ ] The headline: minutes of consultation time saved per patient

---

## What "done" looks like for the demo

A judge walks up to a real touchscreen. They tap through an intake as a
non-reading patient in under four minutes, hold up a handwritten prescription, and
then walk to a second screen where their history is already waiting. Then you say
"and if I'd said chest pain and breathlessness —" and show the escalation.
Then you show the numbers table.

Nothing on any screen ever tells them what disease they have.
