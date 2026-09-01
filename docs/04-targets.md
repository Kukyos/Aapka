# Targets, metrics and the numbers that matter

The brief sets no numbers. We set our own and then prove them. That is the
differentiator — most teams will demo a happy path and quote nothing.

---

## The throughput argument

Nobody else will do this arithmetic. It should be a slide.

```
Tertiary govt hospital OPD load     4,000 – 10,000 patients / day   (from the brief)
Working OPD window                  ~6 hours = 360 minutes
```

| Intake time per patient | Patients per terminal per day | Terminals needed for 5,000 |
|---|---|---|
| 8 min | 45 | ~111 |
| 5 min | 72 | ~70 |
| 4 min | 90 | ~56 |
| 3 min | 120 | ~42 |
| 90 s (returning patient) | 240 | — |

Two conclusions fall straight out:

1. **Interview length is the primary design constraint.** Every question we add has a
   deployment cost measured in terminals. This is the discipline that stops the
   interview sprawling.
2. **A returning-patient fast path is not a feature, it's an economic necessity.**
   Pull the last visit from ABHA, confirm what's unchanged, ask only what's new.
   If 40% of patients are repeat visits, the terminal count drops hard.

---

## Targets to hit and demo

### Speed
| Metric | Target |
|---|---|
| New patient, full intake | ≤ 4 minutes |
| Returning patient (ABHA history exists) | ≤ 90 seconds |
| Time from patient finishing to summary on doctor screen | ≤ 10 seconds |
| Doctor time to read summary | ≤ 15 seconds (measure it with a real reader) |

### Correctness
| Metric | Target |
|---|---|
| History field coverage — % of mandated fields populated | report per-field, aim ≥ 90% |
| Field-level accuracy vs ground truth (see eval harness) | report F1, aim ≥ 0.90 |
| Red-flag recall | ≈ 100% on our defined list |
| Red-flag precision | report honestly, no target — false alarms are acceptable |
| Physician edit rate — % of summary accepted untouched | report; lower is fine if honest |

### Perception (voice and vision)
| Metric | Target |
|---|---|
| ASR word error rate, Indian-accented, **medical vocabulary, with hospital noise mixed in** | report; clean-audio numbers are not acceptable evidence |
| OCR entity-extraction F1 on **handwritten** prescriptions specifically | report separately from printed |
| OCR entity-extraction F1 on printed lab reports | report separately |

### Accessibility
| Metric | Target |
|---|---|
| Task completion by a first-time user with zero instruction | test on real people, report pass rate |
| Completion without reading any text (audio + icons only) | must be possible; test it |
| Abandonment rate in testing | measure |

### The headline number
**Minutes of consultation time saved per patient.** Everything above exists to
support this one claim. Compute it as (time a doctor spends eliciting history
manually) − (time to read our summary). Get the first number from an actual
observation or a cited study, not a guess.

---

## The eval harness — build this early

Correctness here is **invisible**. A beautifully formatted summary can be completely
wrong and nothing on screen will tell you. This is the single biggest technical risk
in the project.

**Build the measuring tool before the features it measures.**

What it is:
1. A set of scripted patient scenarios — say 40 — each with a known ground-truth
   structured history written by hand.
2. For voice: pre-recorded audio of each scenario, in multiple languages/accents,
   with hospital noise mixed in at several SNR levels.
3. A runner that plays each scenario end-to-end through the real pipeline.
4. A scorer that compares output fields against ground truth and prints a table.

What it buys us:
- A number to put on a slide that nobody else will have
- Regression safety while we change prompts and models
- The ability to say "we know where it fails and why"

Include at least: 5 red-flag scenarios, 5 proxy-respondent scenarios,
5 abandonment/partial scenarios, 5 AYUSH-specific scenarios, and a few deliberately
messy ones (patient rambles, contradicts themselves, mixes languages mid-sentence).

---

## Data we need to collect, starting now

| What | Why | Lead time |
|---|---|---|
| Real handwritten prescriptions | OCR is untestable without them. Photos from family, friends, local clinics. | **Start this week** — it's the longest pole |
| Hospital ambient noise recordings | For the noise-mixed ASR eval | An afternoon |
| Regional-language symptom vocabulary | How people actually describe symptoms, not textbook terms | Ongoing |
| An Ayurvedic practitioner to sanity-check the AYUSH module | Credibility. One conversation is worth a week of reading. | Ask around campus |
