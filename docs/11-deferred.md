# Deferred work

Everything knowingly left incomplete, with what it blocks and what closing it costs.
Appended to as the build goes, not reconstructed at the end. Nothing here is a
surprise — if it is not in this file, we think it is done.

Status key: **BLOCKER** (submission fails without it) · **GAP** (weakens a claim) ·
**POLISH** (nice to have).

Last updated: 2026-09-02

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

### D-05 · ICD-11 TM2 codes are placeholders
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
`documents.py` flags out-of-range values only for the analytes in `reference_ranges`.
Anything outside that set is extracted but not flagged.
**Closes when:** ranges are taken from the demo hospital's own lab report headers —
which is the correct source anyway, since ranges are assay-specific.

### D-08 · Drug interaction checking is a small curated pair list
Not a pharmacological database. It catches the demonstrable cases and says so.
**Closes when:** a licensed interaction dataset is available, or the scope is
formally narrowed to "flag for pharmacist review" rather than "check interactions".

---

## POLISH — known simplifications

### D-09 · Interview budget is estimated, not measured
`cost_s` on each node is an estimate. Once real users run the kiosk, replace the
estimates with observed per-node timings and the budget arithmetic in `04-targets.md`
becomes measured rather than modelled.

### D-10 · Returning-patient fast path is designed, not built
`04-targets.md` calls it an economic necessity (90 s vs 4 min). The engine supports it
— slots pre-filled from a previous visit are simply already-answered nodes — but the
ABHA fetch that would populate them depends on D-03.

### D-11 · Icon set is keys, not artwork
Every option carries an `icon` key and the patient app resolves it. The current
resolution is a built-in inline SVG set covering the keys in use, with a labelled
fallback. Real illustrated icons for a low-literacy audience are a design task
listed in `07-build-plan.md` Phase 2.

### D-12 · Only English and Hindi
The ontology schema is per-language and adding a language is data-only, no code.
Tamil and Malayalam are the strongest next two for an AYUSH deployment.
