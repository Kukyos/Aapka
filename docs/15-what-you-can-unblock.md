# What needs doing, and who has to do it

Written 2026-09-03, after a verbatim re-read of `01-problem-statement.md` and a check
of what has actually executed on this machine.

Two lists. The first is work only the owner can do, ordered by how long the clock runs
once it starts — not by how important it is. The second is work waiting on the first.
Existing D-numbers are not re-explained here; they live in `11-deferred.md`.

---

## Status, 2026-09-04

Updated after the Groq and ICD-11 credentials landed. What follows is what is *still*
outstanding; the closed items stay recorded so this list is honest about its own age.

### Closed

**ICD-11 API credentials — obtained.** TM2 is pulled and cached, sixteen codes in
`ontology/codes.yaml` are `sourced`, and both code systems reach the FHIR bundle. Closes
D-05 and item 3 of `10-unsourced.md`. Re-pull with `python -m tools.fetch_icd11`.

**Groq API key — obtained and working.** Three things stood between the key and a live
model rung, none of them the key: `urllib`'s default User-Agent is refused by the CDN
with a 403 that reads exactly like an auth failure, the configured model id had been
retired, and the account carries no vision model. The first two are fixed in code.

With the rung live, `13-eval-results.md` carries both the offline and the with-models
numbers. Voice mapping goes from 11/13 to 12/13. Red-flag recall is 9/9 either way,
because escalation is decided by rules rather than by a model.

### The blocker is no longer a key

**Tesseract is not installed, and the Groq account has no vision model.** The OCR ladder
therefore has no rung at all, on either side. `documents.py` and `ocr.py` are written,
typed and unit-tested against fixtures, but **no image has ever been through them**.
That is not "the cloud tier is untested" — it is the whole of Module B.

---

## Your list

### Today, minutes each

**1 · Install Tesseract.** The one remaining item that unblocks an entire module and
needs nobody else's approval. `winget install UB-Mannheim.TesseractOCR`, then restart the
shell. The installer does not add itself to PATH, and Hindi language data is a checkbox at install time.

**2 · ~~Get a NAMASTE portal account~~ — done 2026-09-04.** An official SIH export of
all four morbidity code lists was obtained, and it turned out to carry the official
NAMASTE-to-ICD-11-TM2 crosswalk as well. D-04 closed.

**3 · Bhashini access — requested 2026-09-04, awaiting approval.** Registered at
<https://bhashini.gov.in/ulca/user/register>; the key request needs a manager's approval
and was told to expect at least two days. Three values come back and all three are
needed: `userId`, `ulcaApiKey`, `InferenceApiKey`.

Bhashini is the Government of India's own speech and translation service — speech to
text, text to speech, translation, 22 Indian languages. Its speech-to-text takes a
`domain` parameter that includes **medical**, which is exactly our case. See finding A.

### Where the keys go

All of them go in a `.env` file in the project root, which is gitignored and never
committed. Copy `.env.example` to `.env` and paste values next to the matching names —
nothing else is needed, and anything left blank falls back to the offline path.

**`.env.example` is committed. Never put a real value in it.** A live key was pasted
there on 2026-09-04 and caught before it was committed; that is the one file in this
repo where a secret would be published.

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

**8 · NAMASTE portal account.** Moved up to item 2 — it is the last unsourced code
system now that ICD-11 is closed.

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

**Status:** adopted and requested on 2026-09-04, awaiting a manager's approval on the ULCA portal. Still true that we use neither today.

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

| Work | Waits on | Status |
|---|---|---|
| Run the `--llm` eval beside the offline floor | Groq key | **done 2026-09-04** |
| Pull TM2 + MMS, fill `codes.yaml`, flip provenance | ICD-11 credentials | **done 2026-09-04** |
| Returning-patient fast path (D-10) | your decision | **done 2026-09-03**, local source |
| Put a real prescription through the OCR pipeline | Tesseract + one photo | blocked on both |
| Hindi rendering of the physician summary (finding D) | nothing | open |
| Name the HIS seam explicitly in `09-architecture.md` (finding E) | nothing | open |
| Write the Samprapti and Aadhaar reasoning into the narrative (F, C) | nothing — both decided | open |
| Bhashini adapter behind the existing ASR seam (finding A) | ULCA approval | waiting |
| NAMASTE codes (D-04) | portal account | waiting |
| Tune the barge-in thresholds (D-17) | noise recordings | waiting |

### Decided 2026-09-03

Three answers, now logged in `06-decisions.md`:

- **Returning-patient fast path ships with a local source.** The prefill mechanism is
  real; only the source of the previous visit is ours rather than ABHA. Mirrors the
  existing `ABDM_MODE=mock|sandbox` split and is labelled local everywhere it surfaces.
- **We do not take Aadhaar.** Finding C is answered by argument rather than by code, and
  the argument goes in the submission rather than being left silent.
- **Bhashini is adopted** behind the existing ASR adapter, with the browser recogniser
  staying underneath it as the offline rung.
