# Deferred work

Everything knowingly left incomplete, with what it blocks and what closing it costs.
Appended to as the build goes, not reconstructed at the end. Nothing here is a
surprise — if it is not in this file, we think it is done.

Status key: **BLOCKER** (submission fails without it) · **GAP** (weakens a claim) ·
**POLISH** (nice to have).

Last updated: 2026-09-04

---

## BLOCKER — needs real-world data we do not have

### D-01 · No handwritten prescriptions collected
The OCR pipeline is built and runs, but **no accuracy number for handwritten
documents can be reported** until we have real ones. `04-targets.md` demands
handwritten and printed be reported separately; right now both rows read
"pending real data".
**Closes when:** 50+ photographed real prescriptions exist in `eval/documents/`.
**Owner action:** Phase 0 item, longest lead time in the project. Start now.

### D-02 · No hospital ambient noise recordings
Every ASR number in the repo is therefore unreported, not optimistic. `03-requirements.md`
R4 is explicit that clean-audio numbers are meaningless for this deployment.
**Closes when:** an afternoon of recordings exists in `eval/noise/` and the harness
mixes them at several SNR levels.

### D-13 · Red-flag rules have not been reviewed by a clinician
`ontology/redflags.yaml` encodes widely-taught emergency triage patterns and is tuned
hard for recall, but no practising doctor has signed off on the rule set. Gate G4 is
the one place in this system where being wrong has a physical consequence.
**Closes when:** an emergency physician and an Ayurvedic practitioner have each read
the rule list and the sign-off is recorded in `06-decisions.md`.
**Owner action:** `07-build-plan.md` Phase 0 already calls for finding an Ayurvedic
practitioner. Add an EM doctor to that ask.

### D-03 · ABDM sandbox not registered
FHIR bundles are generated for real and validated structurally, but the transport is
a local mock (`abdm.py`, `ABDM_MODE=mock`). The brief's lose-condition list names
faking ABDM specifically.
**Closes when:** sandbox credentials exist and `ABDM_MODE=sandbox` is set. No code
changes expected beyond configuration — that is the point of the split.

---

## GAP — structurally present, values unsourced

These are tracked in detail in `10-unsourced.md`. Summarised here because they are
also deferred work, not just missing citations.

### D-04 · NAMASTE codes are placeholders
`ontology/codes.yaml` has the right shape and every entry is marked `PLACEHOLDER`.
The portal does not publish the code list without an account.
**Closes when:** someone with a NAMASTE portal login exports the Ayurveda morbidity
code list (7,340 codes per published figures) and we map our 14 chief complaints onto it.

### D-05 · CLOSED 2026-09-04 · ICD-11 codes are sourced
Credentials obtained, `server/tools/fetch_icd11.py` written, TM2 pulled and cached at
`ontology/cache/icd11-tm2-2025-01.json` — 710 entities, 648 coded. 16 entries in
`codes.yaml` are now `sourced`: 13 ICD-11 MMS symptom codes for the chief complaints,
and SR10 / SR15 / SR1A for the dosha findings. Both reach the FHIR bundle.

**One deliberate non-closure.** The TM2 field on every chief complaint is marked
`not_coded` rather than filled. TM2 codes *disorders* — "Cough disorder (TM2)" — and
attaching one to a patient who said they have a cough would be a diagnosis made by a
kiosk, which hard rule 1 forbids. We hold all 648 codes and decline to use them there.
A new provenance level, `not_coded`, distinguishes that refusal from a missing source.

### D-05 · superseded detail, kept for the trail
TM2 (Ayurveda / Siddha / Unani) was added to ICD-11 in 2025. The publicly downloadable
Chapter 26 PDF is **TM1** — East Asian medicine — and using those codes for an
Ayurveda intake would be wrong, not merely unsourced.
**Closes when:** WHO ICD-11 API credentials (free, application-based) are obtained and
the TM2 linearisation is pulled.

### D-06 · CCRAS Prakriti scale is abbreviated
The published standardized Prakriti Assessment Scale is 91 predictors across 30
domains in 4 traits. It is not publicly downloadable. `ayush.prakriti_screen` is a
9-item screen built from classical, public-domain Dashavidha descriptions and is
labelled as such in the data and on the doctor screen.
**Closes when:** the CCRAS manual or portal export is obtained. Until then the summary
must never call this a Prakriti *determination* — it is a screen.

### D-07 · Lab reference ranges are a small hand-entered set
`documents.py` flags out-of-range values only for the analytes in `REFERENCE_RANGES`.
Anything outside that set is extracted but not flagged.
**Closes when:** ranges are taken from the demo hospital's own lab report headers —
which is the correct source anyway, since ranges are assay-specific.

### D-08 · Drug interaction checking is a small curated pair list
Not a pharmacological database. It catches the demonstrable cases and says so.
**Closes when:** a licensed interaction dataset is available, or the scope is
formally narrowed to "flag for pharmacist review" rather than "check interactions".

---

## POLISH — known simplifications

### D-14 · A scanned ABHA number is not verified against ABDM
The identify step reads the number off the card and normalises it, and it reaches the
FHIR bundle as the Patient identifier. Nothing confirms the number is real, belongs to
this patient, or is currently active — that requires an ABDM lookup and therefore
sandbox credentials.
**Closes when:** D-03 closes. Until then a mistyped or misread card produces a bundle
with a wrong identifier, which is why the doctor screen shows the number rather than
silently trusting it.

### D-15 · Prior visits are remembered locally, which ABDM should be doing
**Partially closed 2026-09-03.** Scanning a card now does pull a previous visit, so the
fast path is genuinely faster — but from a table we keep, which is a thing we would
rather not keep. The row is written only on explicit `link_to_abha` consent, keyed by a
SHA-256 of the ABHA number rather than the number, holds only slots the ontology marks
`carry_over: true`, and has an erasure route (`DELETE /api/session/{id}/prior-visit`)
because the DPDP Act gives the patient that right.

It remains a compromise: the correct home for a longitudinal record is the patient's
ABHA, not a hospital terminal's SQLite file.
**Closes when:** D-03 closes and `PRIOR_VISIT_SOURCE=abdm`, at which point the local
table is dropped rather than migrated.

### D-19 · Which slots carry between visits has not been clinician-reviewed
`ontology/slots.yaml` marks 15 slots `carry_over: true`. The reasoning is written out
above the block and the Prakriti/Vikriti split follows classical doctrine — Prakriti is
constitutional and fixed, Vikriti is the present imbalance — but the list is ours.
Carrying something that should have been re-asked is a clinical error, not a UX one.
**Closes when:** it goes to the same clinicians as D-13. It is one extra page in an
existing conversation, not a separate ask.

### D-16 · The phone handoff is touch-only over plain HTTP
The QR on the attract screen opens the same intake on a patient's own phone, and the
whole interview works there — but a browser gives a page no microphone and no camera
outside a secure context, so on `http://<lan-ip>:5173` the phone path has no voice
option and cannot run the document step. The kiosk says so on the QR panel and the
documents screen tells the patient to bring their papers to the doctor, rather than
offering a camera button that does nothing.

Gate G2 survives this because the touch path was never the fallback — it is the primary
path, complete on its own, and the phone is a secondary convenience under G1. What is
actually lost is Module B on that one path.
**Closes when:** the handoff is served over HTTPS. `PUBLIC_BASE_URL` exists for exactly
this and no code changes — any real hospital deployment terminates TLS anyway. A
self-signed certificate would also work technically but puts a browser security
interstitial in front of a patient in a waiting hall, which is worse than touch-only.

### D-17 · Barge-in thresholds were tuned on a quiet desk
`patient/src/speech.ts` detects the patient speaking over the prompt by calibrating a
noise floor during the first 700 ms of the prompt itself and triggering above a fixed
margin. The four constants are named and commented, but they have never been in a room
with fifty people in it and a kiosk speaker at OPD volume.
Both failure directions are safe by construction — a missed barge-in means the prompt
finishes and the patient presses the microphone, a false one means the prompt stops and
the screen says "Listening…", which can be ignored — so this is tuning, not a defect.
**Closes when:** the constants are set from a session in a real waiting hall, alongside
the D-02 noise recordings, which is the same trip.

### D-18 · Language detection is a script heuristic, not a language model
The language screen listens and pre-selects Hindi or English by counting Devanagari
against Latin characters in what Chrome's `hi-IN` recogniser returns. It is a
pre-selection the patient still confirms with a tap, it needs no network, and below four
script-bearing characters it declines to guess. It will not extend to a third language
that shares a script with one already listed.
**Closes when:** a third language is added (D-12). Whisper already reports a detected
language and `asr.py` now returns it, so the server path is the seam — but it needs a
network, and the offline heuristic has to stay underneath it either way for G1.

### D-09 · Interview budget is estimated, not measured
`cost_s` on each node is an estimate. Once real users run the kiosk, replace the
estimates with observed per-node timings and the budget arithmetic in `04-targets.md`
becomes measured rather than modelled.

### D-10 · Returning-patient fast path runs on a local source, not ABHA
**Built 2026-09-03.** The mechanism is complete and real: `engine.prefill()` seeds
carried slots as already-answered nodes at zero time cost, the patient confirms them on
the `welcome_back` screen before anything is used, and the budget moves to 90 s only if
something was actually carried. What is not real is the *source* — the previous visit
comes from our own `prior_visits` table rather than from the patient's ABHA record.

`PRIOR_VISIT_SOURCE=local|abdm|off` is the switch, mirroring `ABDM_MODE`. It is
surfaced as "local" in `/api/health`, in `summary.carried_over.source`, on the doctor
screen banner and on the patient's own confirmation screen — never described as ABDM,
because faking ABDM is a named lose condition.
**Closes when:** D-03 closes. `_prior_visit_offer()` in `api.py` is the single function
that changes and its return shape does not.

### D-11 · Icon set is keys, not artwork
Every option carries an `icon` key and the patient app resolves it. The current
resolution is a built-in inline SVG set covering the keys in use, with a labelled
fallback. Real illustrated icons for a low-literacy audience are a design task
listed in `07-build-plan.md` Phase 2.

### D-12 · Only English and Hindi
The ontology schema is per-language and adding a language is data-only, no code.
Tamil and Malayalam are the strongest next two for an AYUSH deployment.
