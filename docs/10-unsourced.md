# Unsourced values ledger

Every value in this system that a judge could check, but that we could not verify
against a published source. Each one is **structurally present and visibly marked**
rather than filled with something plausible.

This file exists because the alternative is worse. `03-requirements.md` lists
"invent our own Prakriti questionnaire" and "fake the ABDM integration" as lose
conditions, and the people evaluating this submission own the NAMASTE portal. A
fabricated code is not a shortcut, it is the specific failure mode they are watching
for. An empty field with a citation trail is defensible; a plausible-looking wrong
one is not.

Every consumer of these values checks `provenance` and renders anything marked
`PLACEHOLDER` as pending — never as a code, never as a finding.

Last verified: 2026-09-04

---

## How to read this

| Provenance | Meaning |
|---|---|
| `sourced` | Verified against a published, citable source. Safe to display. |
| `PLACEHOLDER` | Structure only. Rendered as "pending" everywhere it appears. |

`test_codes_file_invariant_holds` in `server/tests/test_core.py` enforces the
invariant: anything marked `sourced` must have a non-empty value, and anything with a
non-empty value must be marked `sourced`. You cannot quietly promote a guess.

---

## 1 · NAMASTE morbidity codes — `ontology/codes.yaml`

**Status: SOURCED for dosha findings, deliberately `not_coded` for complaints.**

An official SIH-purposed export of the morbidity code lists was obtained on 2026-09-04
and the four workbooks are committed at `ontology/source/`:

| System | Terms |
|---|---|
| NAMC, National Ayurveda Morbidity Codes | 2,910 |
| NSMC, National Siddha Morbidity Codes | 1,926 |
| NUMC, National Unani Morbidity Codes | 2,522 |
| NAMASTE ICD-10 mapping sheet | 11,145 rows |

`python -m tools.fetch_namaste` parses them to `ontology/cache/`. Sourced from it:
`AAA-2.1` vātaprakopaḥ, `ABA-2.1` pittaprakopaḥ, `ACA-2.1` kaphaprakopaḥ, which are
exactly our three dosha findings.

### The crosswalk was hiding in the code column

The NAMC export carries the **official NAMASTE to ICD-11 TM2 mapping**, undocumented and
unlabelled, inside its `NAMC_CODE` field: a row reading `SR11 (AAA-1)` is a NAMASTE code
paired with the WHO TM2 code it maps to. 807 of the 2,910 rows carry one.

Two properties make it trustworthy rather than merely present:

- **It cross-validates.** 374 of the pairs carry an English label character-identical to
  the title the WHO API independently returns for that TM2 code. Two separate published
  sources agreeing is a stronger citation than either alone.
- **It distinguishes exact from approximate.** Rows whose English name ends in `⇒` are
  approximate mappings; rows without it are exact equivalences. The split is almost
  perfect — 374 no-arrow exact against 428 arrow-marked divergent, with 5 anomalies —
  so the marker is theirs, not our inference. We record it as FHIR ConceptMap
  `equivalence`, and only `equivalent` pairs are emitted as codes.

Token order is not reliable — `SR11 (AAA-1)` and `AAB-39(SP1Y)` reverse it — so the WHO
cache decides which token is which, and `fetch_namaste` refuses to run without it rather
than guessing.

### Why the complaints stay uncoded

NAMC answers at the **disorder** register: "Fever disorder (TM2)", "Abdominal pain
disorder (TM2)", "Dyspnoea disorder (TM2)". Its own root node is
`AYU vyādhi-viniścayaḥ`, *diagnostic conditions*. Attaching one to a patient who said
they have a fever would be a diagnosis made by a kiosk.

This was decided before the list was read — see the rule recorded below — which is the
only reason it can be trusted now that the codes are in hand and attaching them would
have been easy.

**Superseded notes from 2026-09-02:**

**What we know, and can cite:**
- The National Ayush Morbidity Codes (NAMC, plus NSMC for Siddha and NUMC for Unani)
  are real and are the Ministry's own classification.
- Published figure: **7,340 Ayush morbidity codes**, described in the context of
  migrating them into the ABDM ecosystem via an ABDM- and FHIR-compliant A-HMIS.
- Portal: <https://namaste.ayush.gov.in/about-namaste-portal>

**What we could not get:** the code list itself, or the code format. The portal
publishes an *about* page, a user manual link, dashboards and training material —
not a downloadable terminology file. No public API was found.

**How to close it:** an account on namaste.ayush.gov.in, then export the NAMC list
for Ayurveda and map our 14 complaints onto it.

**The rule that governs that mapping, decided in advance.** Our fourteen complaints are
patient-reported *symptoms*. If NAMC turns out to be a list of Ayurvedic *diagnoses* —
the way ICD-11 TM2 did — then the same refusal applies: hold the codes, do not attach
them to a chief complaint, and mark the slot `not_coded` rather than `PLACEHOLDER`. A
kiosk choosing a diagnosis is the one thing this system never does. Read the list before
mapping it.

Also worth taking from the portal while logged in: whether NAMASTE publishes its own
crosswalk to ICD-11 TM2. India has a published dual-coding roadmap, and if the mapping
ships then our TM2 side is already sourced and the two systems emit together.

---

## 2 · ICD-11 TM2 codes — `ontology/codes.yaml`

**Status: SOURCED for the dosha findings, deliberately `not_coded` for complaints.**

Credentials were obtained on 2026-09-04 and TM2 was pulled through the WHO API. The
cache is `ontology/cache/icd11-tm2-2025-01.json`; re-pull with
`python -m tools.fetch_icd11`. Chapter 26 Module II carries 710 entities, 648 of them
coded, across twelve disorder blocks and six pattern blocks.

Sourced: `SR10` Vitiation of vāta, `SR15` Vitiation of pitta, `SR1A` Vitiation of kapha.
These are *pattern* codes attached to the patient's own Vikriti answer and emitted as
preliminary, patient-reported observations.

Not coded, on purpose: every chief complaint. TM2's disorder codes are diagnoses —
"Cough disorder (TM2)", "Enteric fever disorder (TM2)" — and a kiosk choosing one would
be diagnosing. We have the codes and decline to use them there.

Also present and unused: the `ST00`–`ST1Z` "Body constitution and temperament patterns"
block. Those are Unani *mizaj* — hot, cold, moist, dry — not Ayurvedic Prakriti. Our
Prakriti screen has no TM2 code because TM2 codes derangements and a constitution is
not one.

**Superseded notes from 2026-09-02:**

**What we know, and can cite:**
- ICD-11 Chapter 26 is the supplementary traditional-medicine chapter. It separates
  traditional medicine **disorders** (disease entities) from **patterns**
  (functional imbalances identified through traditional diagnostics).
- Module 1 (East-Asian systems) took effect 1 January 2022. **Module 2 — Ayurveda,
  Siddha and Unani — was added in 2025.**
- India has a published roadmap for TM2 implementation:
  <https://journals.lww.com/ijar/fulltext/2025/10000/india_s_roadmap_for_icd_11_tm2_implementation_.18.aspx>

**The trap we avoided, stated plainly:** the freely downloadable Chapter 26 PDF is
**Module 1**. Its codes are real and verifiable — `SA00` Hypochondrium pain disorder,
`SA01` Jaundice disorder, `SA02` Liver distension disorder, and so on through roughly
470 codes — and they were extracted and read during this work. They are **Traditional
Chinese Medicine patterns**. Putting them on an Ayurveda intake would be a factual
error dressed up as diligence, so they are not used.

**What we could not get:** the TM2 linearisation. The WHO ICD-11 browser is
JavaScript-rendered and returns an application shell to a plain HTTP client; the ICD
API requires OAuth client credentials.

**How to close it:** apply for free ICD-11 API credentials at
<https://icd.who.int/icdapi>, then pull the TM2 linearisation.

---

## 3 · ICD-11 MMS biomedical codes — `ontology/codes.yaml`

**Status: SOURCED, 2026-09-04.** Thirteen of the fourteen chief complaints now carry a
real ICD-11 MMS code, pulled from the WHO API and checkable at
<https://icd.who.int/browse/2025-01/mms/en>.

Every one is a **symptom** code, never a disease code — `MD12` Cough, `MG22` Fatigue,
`ME82` Pain in joint, `MD30.Z` Chest pain unspecified. Where the API returned a disease
sharing the word — `8A8Z` Headache disorders, `BA40` Angina pectoris, `CA23` Asthma —
it was rejected. The patient reported a symptom and nobody has examined them; coding it
as a disease would assert something the interview did not establish.

The fourteenth is `other`, marked `not_coded`. "Other" is a bucket on a touchscreen
rather than a clinical concept; what the patient actually has is in `cc.narration` and
is the physician's to code.

---

## 4 · CCRAS Prakriti Assessment Scale — `ontology/questions/04-ayush-dashavidha.yaml`

**Status:** `ayush.prakriti_screen` is an abbreviated 9-item screen, marked
`PLACEHOLDER`, and labelled "Prakriti screen (abbreviated)" wherever it is displayed.

**What we know, and can cite:**
- CCRAS has developed and validated a standardized Prakriti Assessment Scale.
- Its published structure: **91 predictors grouped into 30 domains across four traits**
  — physical, physiological, psychological and behavioural. Of the 91, **31 are
  Vatika, 29 Pittika and 32 Kaphaja**.
- Validated for face, content, construct and criterion validity, with intra- and
  inter-rater reliability tested using the Kappa statistic.
- Administered through the AYUR Prakriti web portal: <http://ccras.res.in/ccras_pas/>
- Paper: *Development of a standardized assessment scale for assessing Prakriti
  (psychosomatic constitution)*, AYU 2022. The publisher returns HTTP 402 to
  non-subscribers.
- A related public dataset, Prakriti200 (arXiv 2510.06262), uses a 24-item
  multiple-choice questionnaire following AYUSH/CCRAS guidelines, but **does not
  reproduce the item text** — only the domains: physical, physiological, psychological.

**What we could not get:** the 91 items, their response options, or the scoring
weights. Neither the paper nor the dataset publication reproduces them.

**What we did instead:** built a 9-item screen from *classical, public-domain*
Dashavidha Pariksha descriptions — three cues each for Vata, Pitta and Kapha across
build, appetite and sleep. It is not the CCRAS instrument and does not claim to be.

**Two rules this places on everyone touching the code:**
1. Nothing may present this as a Prakriti **determination**. It is a screen. The
   doctor screen renders it as "Prakriti screen (abbreviated), patient-reported".
2. When the CCRAS instrument is obtained, `04-ayush-dashavidha.yaml` is **replaced
   wholesale**, not edited. Blending our wording into theirs would produce something
   that is neither, and would be the exact thing this file exists to prevent.

---

## 5 · Sara, Samhanana and Pramana are self-reported

**Status:** `sourced` as a design decision, flagged as a limitation.

In classical practice these three are **clinician-observed**, not patient-reported —
Sara in particular is assessed by examining tissue quality. A kiosk cannot observe.
Each of these nodes carries `self_report_proxy: true`, and the doctor screen marks
them "patient-reported" so they are never mistaken for examination findings. The
practitioner confirms or overrides them in seconds, which is the correct division of
labour anyway.

---

## 6 · Lab reference ranges — `server/aapka/documents.py`

**Status:** a small hand-entered set covering the analytes that appear on common
Indian OPD lab reports.

Reference ranges are **assay- and laboratory-specific**, which is why every real lab
report prints its own ranges next to the values. The correct long-term behaviour is
to read the range off the document being scanned rather than from a table, and the
extractor already captures a printed range when one is present. The table is the
fallback for documents that omit them.

**How to close it:** prefer the document's own printed range; keep the table only as
a fallback, sourced from the demo hospital's lab.

---

## 7 · Drug interactions — `server/aapka/documents.py`

**Status:** a small curated pair list, not a pharmacological database.

The brief asks for "potential drug interactions" to be flagged. A real interaction
database is licensed. What is implemented catches a handful of well-documented,
clinically obvious pairs and is labelled on the doctor screen as
"screening only — not a complete interaction check".

**How to close it:** license a dataset, or narrow the claim to "flag for pharmacist
review", which is arguably the more honest scope for an intake terminal regardless.

---

## Summary for the pitch

Stated as a strength, because it is one:

> Every code slot in our output is present and correctly typed, and none is filled
> with a guess. ICD-11 is sourced — sixteen codes pulled from the WHO API, symptom
> codes for complaints and pattern codes for dosha findings. Three gaps remain and we
> know exactly what closes each: a NAMASTE portal account, the CCRAS manual, and the
> deploying hospital's own lab ranges. None requires a schema change.
>
> One slot is empty on purpose rather than for want of a source. We hold all 648 ICD-11
> TM2 codes and attach none of them to a chief complaint, because TM2 codes disorders
> and a kiosk choosing one would be diagnosing. Having the data and declining to use it
> is a different claim from not having it, and `provenance: not_coded` says which.
