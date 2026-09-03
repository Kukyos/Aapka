# What needs doing, and who has to do it

Written 2026-09-03, after a verbatim re-read of `01-problem-statement.md` and a check
of what has actually executed on this machine.

Two lists. The first is work only the owner can do, ordered by how long the clock runs
once it starts — not by how important it is. The second is work waiting on the first.
Existing D-numbers are not re-explained here; they live in `11-deferred.md`.

---

## The finding that reorders everything

There is no `.env` on this machine, Tesseract is not installed, and Ollama is not
running. Verified, not assumed:

```
tesseract installed: False
llm rungs          : {'groq': False, 'ollama': False}
groq key           : False
```

Consequences, stated plainly:

- **The document pipeline has never run. On either rung.** `documents.py` and `ocr.py`
  are written, typed and unit-tested against fixtures, but no image has ever been
  through them. This is not "the cloud tier is untested" — it is the whole of Module B.
- **All three NLU rungs above the keyword matcher have never executed.** Every number
  in `13-eval-results.md` is the deterministic floor with the models switched off.
  That floor is the honest headline for gate G1 and should stay the headline — but
  right now it is also the *ceiling*, because nothing above it has been exercised once.
- **Server-side ASR has never run.** The browser recogniser is what has been used.

None of this is a defect; the fallbacks are the design. But it means three subsystems
are currently claims rather than measurements, and two of the three unblock for free.

---

## Your list

### Today, minutes each — these unblock the most per unit of your time

**1 · ICD-11 API credentials.** Free, application-based, at <https://icd.who.int/icdapi>.
Closes D-05 and item 3 of `10-unsourced.md` — the TM2 traditional-medicine codes and
the MMS biomedical codes. This is the single most visible credibility item available:
it converts every `PLACEHOLDER` in `ontology/codes.yaml` that is not NAMASTE into a
real, judge-checkable code. Note the trap already documented — the free Chapter 26 PDF
is **TM1** (East Asian medicine) and is wrong for an Ayurveda intake, which is why the
API is the only correct route.

**2 · A Groq API key.** Free tier, <https://console.groq.com>. Two minutes. Turns on the
LLM rung, the vision-OCR rung and the Whisper path in one move, and makes
`python -m eval.run_eval --llm` meaningful — a second measured number to sit beside the
offline 11/13 utterance-mapping baseline. Goes in `.env`; `.env.example` already lists
every key with a comment.

**3 · Decide the Aadhaar question.** See finding C in the audit below. It is a decision,
not a build, and it should be logged in `06-decisions.md` either way.

### Today, because the clock is measured in weeks

**4 · Start photographing handwritten prescriptions.** D-01. Target 50+. Family,
friends, a local clinic, anyone who will let you photograph a paper. This is the
longest-lead item in the project and no OCR claim exists until it is done — and, per
the finding above, we do not currently know whether the pipeline extracts anything at
all from a real crumpled prescription. **Even five photographs this week is a
qualitative change**, because it moves Module B from untested to tested.

**5 · Record hospital ambient noise.** D-02. An afternoon in an actual OPD waiting
hall with a phone. Every ASR number stays unreportable without it, and it is also the
trip on which the barge-in thresholds get tuned (D-17) — same afternoon, two items.

**6 · Line up two clinicians.** D-13, and it is the one place in this system where
being wrong has a physical consequence: an emergency physician to read
`ontology/redflags.yaml`, and an Ayurvedic practitioner for the Dashavidha block.
Thirty minutes each. `04-targets.md` already says one conversation beats a week of
reading. Their sign-off gets recorded in `06-decisions.md`.

### Registration queues — start them, then forget them

**7 · ABDM sandbox registration.** D-03. Has a milestone process and takes time.
Closes D-03, D-14, D-15 and unblocks D-10, the returning-patient fast path that
`04-targets.md` calls an economic necessity rather than a feature.

**8 · NAMASTE portal account.** D-04, at <https://namaste.ayush.gov.in>. The code list
is not downloadable without one.

### Hard, may not close, worth one attempt

**9 · The CCRAS Prakriti Assessment Scale.** D-06. 91 predictors across 30 domains; not
publicly downloadable and the AYU paper is paywalled. Realistically needs an
institutional contact — a college library, or the Ayurvedic practitioner from item 6.
If it closes, `04-ayush-dashavidha.yaml` is replaced wholesale, never blended.

**10 · Re-check the SIH portal.** `01-problem-statement.md` records that section 3.2 is
a literal unrendered placeholder — `Insert Table*3.2` — and that we never got the
dataset link, YouTube link or SPOC contact. Worth one look before submission in case
they patched it.

---

## Adherence audit against the brief, read verbatim

Findings from re-reading `01-problem-statement.md` line by line. Everything below is a
gap between the official text and what exists, or a deliberate omission that needs to
read as a decision rather than an oversight.

### A · Bhashini / AI4Bharat are named in the brief and we use neither

Section 1.3 names the enabling technologies explicitly: *"robust automatic speech
recognition (ASR) for Indian languages and accents (**Bhashini / AI4Bharat models**)"*.
We use the browser's Web Speech API and Groq Whisper, with IndicConformer deferred
behind an adapter.

This is the largest strategic gap in the project. Bhashini is the Government of India's
own language platform, this is a Ministry problem statement, and the brief points at it
by name. Adopting it would also close finding B, since Indian language coverage is
Bhashini's entire purpose. `asr.py` was written with exactly one seam for this and
nothing above that seam changes.

**Needs a decision:** ULCA / Bhashini API access. Free but registration-gated.

### B · "Major regional languages" is in the brief; we ship two

Section 2.3 asks for *"Hindi, English, and major regional languages"*. D-12 records the
two-language scope, but the ledger undersells it — this sits in the brief's own list of
challenges a solution must overcome, not in a nice-to-have list. The ontology is
per-language and adding one is data-only, so the cost is translation effort rather than
engineering. Tamil and Malayalam are the strongest next two for an AYUSH deployment.

### C · Step 1 names Aadhaar and new registration; we have neither

Section 3.4 Step 1: *"enters/scans ABHA ID **or Aadhaar details or registers as new**"*.
We have the ABHA scan path and a first-class decline path, which satisfies G1's
walk-in-carrying-nothing requirement. We do not have Aadhaar entry, and we do not have
an ABHA creation flow for a patient who has never had one.

Deliberately not built without a decision. Collecting Aadhaar numbers carries real legal
weight under the DPDP Act, and ABHA creation from Aadhaar is an ABDM flow that needs the
sandbox anyway. **The question:** do we implement Aadhaar-based ABHA creation as the
brief describes once sandbox credentials exist, or do we state in the submission that we
deliberately support ABHA-or-nothing to minimise the identifiers we touch? Both are
defensible; only one of them is defensible *silently*, and it is not the second.

### D · The physician summary is English-only

Module C: *"Bilingual output: patient-facing audio confirmation in local language;
**physician-facing summary in English/Hindi**"*. The patient-facing half is built — the
review screen reads back in the patient's language before anything is sent. The
physician-facing half is English only. A Hindi rendering of the doctor summary is small,
self-contained work.

### E · HIS/EMR push and ABHA linking are one path, not two

Section 3.1 and Step 4 both describe the summary being *"pushed to the hospital
information system (HIS)"* **and** *"linked to the patient's ABHA record"*. We generate
one FHIR bundle and hand it to `abdm.py`. In the demo the doctor screen is the HIS — the
summary does appear on the physician's screen the moment it is submitted, which is what
the brief asks for functionally. Worth naming that seam explicitly rather than letting a
judge conclude one of the two destinations is missing.

### F · Samprapti is absent, and should stay absent

Section 1.1 names *"Prakriti, Vikriti, Agni, Koshtha, Ahara-Vihara, Nidana, and
Samprapti"*. We cover all ten Dashavidha parameters plus Agni, Koshtha, Nidana and
Ahara-Vihara — checked against the ontology files, not from memory.

**Samprapti is the one omission and it is deliberate:** Samprapti is pathogenesis, the
physician's synthesis of how the disease came about. A kiosk that produced one would be
diagnosing, which hard rule 1 and gate G3 both forbid. This needs to be a sentence in
the submission, because an Ayush judge will notice it is missing, and the difference
between "they left it out" and "they refused to put it in" is the whole argument.

---

## My list, and what each item waits on

| Work | Waits on |
|---|---|
| Run the `--llm` eval, report online numbers beside the offline floor | Groq key |
| Put a real prescription through the OCR pipeline and find out what breaks | Groq key or Tesseract, plus one photo |
| Pull the TM2 + MMS linearisations, fill `codes.yaml`, flip provenance to `sourced` | ICD-11 credentials |
| Hindi rendering of the physician summary (finding D) | nothing |
| Name the HIS seam explicitly in `09-architecture.md` (finding E) | nothing |
| Write the Samprapti and Aadhaar reasoning into the submission narrative (F, C) | your Aadhaar decision |
| Bhashini adapter behind the existing ASR seam (finding A) | your decision + ULCA access |
| Returning-patient fast path (D-10) | **your decision** — see below |
| Tune the barge-in thresholds (D-17) | noise recordings |

### The one question where your answer changes the work

The returning-patient fast path is designed and the engine already supports it — a
prefilled slot is just an already-answered node. What it lacks is a source for the
previous visit, which is ABDM, which is D-03.

It could be built now against a **local** store of previous visits: the prefill
mechanism would be entirely real, and only the source would be our own SQLite instead of
ABHA. That turns `04-targets.md`'s "economic necessity" from a slide into a live demo.

It has not been built, because `03-requirements.md` lists faking ABDM as a lose
condition, and "previous visit pulled from our own database" is one careless slide
caption away from being read as exactly that. **Your call:** build it with a local source
and label it unmistakably, or leave it designed-not-built until sandbox credentials
arrive.
