# Measured: what fits in the interview budget

The first thing the engine was pointed at was not a demo, it was this question. The
answer changed a decision.

Everything below comes from `server/eval/budget_sweep.py`, which runs a full AYUSH
interview through the real engine at a range of budgets and counts what got asked.
Reproduce it with:

```
python -m eval.budget_sweep
```

Measured 2026-09-02 against ontology version 1 (59 nodes, 61 slots).

---

## The finding

**A four-minute AYUSH interview captures 5 of the 10 Dashavidha Pariksha parameters.**

That is not a bug in the engine. It is the graph being honest: the core history —
identity, chief complaint, SOCRATES, danger signs, allergies, comorbidities — costs
about 150 seconds before the Ayurvedic assessment starts, and the Dashavidha block
costs about 130 seconds on its own.

It matters because gate G5 says AYUSH depth *is* the differentiator, and section 1.1
of the brief says the Dashavidha assessment is precisely what gets abbreviated when
there is no time. A kiosk that also abbreviates it has not solved the stated problem.

---

## The curve

| Budget | Questions asked | Actual length | SOCRATES | Dashavidha | Patients / terminal / day | Terminals for 5,000/day |
|---|---|---|---|---|---|---|
| 3 min (180 s) | 17 | 181 s | 3 of 7 | 3 of 10 | 119 | 43 |
| **4 min (240 s)** | 24 | 248 s | 6 of 7 | 5 of 10 | 87 | 58 |
| 5 min (300 s) | 30 | 303 s | **7 of 7** | 7 of 10 | 71 | 71 |
| **6 min (360 s)** | 36 | 357 s | **7 of 7** | **10 of 10** | 60 | 84 |
| 7 min (420 s) | 44 | 425 s | 7 of 7 | 10 of 10 | 50 | 100 |
| 8 min (480 s) | 50 | 486 s | 7 of 7 | 10 of 10 | 44 | 114 |

Throughput assumes the 360-minute OPD window from `04-targets.md`.

Two things fall out of the shape of this curve:

- **Everything clinically load-bearing is in by 360 seconds.** Past 6 minutes the
  interview is buying review-of-systems completeness, not diagnostic depth. The curve
  is flat where it matters and the terminal count keeps climbing, so there is no case
  for a longer interview.
- **The 240 → 360 step buys 5 more Dashavidha parameters for 26 extra terminals.**
  That is the actual trade, stated in the units a hospital administrator buys in.

---

## What we changed

`06-decisions.md` D1 set 240 seconds as the working default and said to override it
freely. We have, on evidence:

| Mode | Budget | What it delivers |
|---|---|---|
| AYUSH (default) | **360 s** | 7 of 7 SOCRATES, 10 of 10 Dashavidha |
| Core / allopathic | **240 s** | 7 of 7 SOCRATES, no Dashavidha block |
| Returning patient | **90 s** | Confirm what is unchanged, ask only what is new |

Set in `server/aapka/engine.py`, overridable per session and per deployment.

## The returning-patient fast path, measured

Built 2026-09-03 and now exercised by three eval scenarios rather than asserted.
Numbers from `13-eval-results.md`, same ontology, same engine:

| Scenario | Facts carried | Questions asked | Time |
|---|---|---|---|
| A new patient, AYUSH mode | — | 28–38 | 240–364 s |
| `rt-07` returning, nothing remembered | 0 | 15 | 136 s |
| `rt-16` returning, 11 facts remembered | 11 | 11 | **101 s** |

Three things fall out, and the second was not what we expected.

**1 · The mechanism works and is worth roughly a 3.5x reduction.** 101 s against 364 s
for the same patient arriving as a stranger. That is the throughput argument, and it is
now measured rather than modelled.

**2 · The budget is spent on depth, not returned as speed.** `rt-16` captured *2 of 10*
Dashavidha parameters against `rt-07`'s 1, on a shorter clock. Because a carried answer
costs zero seconds, the freed time does not shorten the visit proportionally — the
engine spends it on the current complaint instead. The fast path makes a returning
visit shorter **and** deeper, which is the opposite of the usual trade.

**3 · The measured time is 101 s, not the 90 s budget.** `04-targets.md` sets 90 s as
the target and the engine sets it as the ceiling; the overshoot is the required-node
tail described immediately below, and the honest number to quote is **~101 s**. Quote
that one. A target is a thing we aimed at and a measurement is a thing we did, and only
one of them belongs on a slide.

### The budget caps optional questions, not required ones

`engine.py` drops a node when its `cost_s` exceeds the remaining budget **and the node
is not `required`**. Required nodes — drug allergy, danger signs, the identity block —
run regardless. A required node reached near the ceiling therefore carries the interview
a few seconds past it, which is why several rows in `13-eval-results.md` read 363–368 s
against a 360 s budget. This is deliberate: the alternative is dropping a safety
question to save eight seconds. Scenario `rt-13-budget-never-drops-required` asserts it.
The ceiling bounds the *optional* tail; the true worst case is 360 s plus the cost of
one required node.

---

## Why 84 terminals is not the real number

Taken alone, "84 terminals for a 5,000-patient hospital" is the weakest number in this
project. It is also not the number a real deployment sees, for two reasons.

**Returning patients.** `04-targets.md` already calls the returning-patient fast path
an economic necessity rather than a feature. At a 40% repeat rate:

```
mean intake = 0.6 x 360 s  +  0.4 x 90 s  =  252 s
            = 85 patients per terminal per day
            = 59 terminals for 5,000
```

Which lands back at the four-minute terminal count while every new patient still gets
the full ten-parameter assessment. This is the argument for building the fast path
early, and it is currently blocked on ABDM access (`11-deferred.md` D-10).

**Not every OPD is an AYUSH OPD.** A general medicine queue runs in core mode at 240
seconds. The 360-second budget applies to the Ayurveda department, which is a fraction
of a tertiary hospital's load and the department this problem statement is actually about.

---

## Honesty notes

- `cost_s` per node is an **estimate**, not an observation. The ratios between question
  types are reasonable and the totals are the right order of magnitude, but the whole
  table shifts once real users are timed. Tracked as `11-deferred.md` D-09.
- Question **count** is measured exactly; question **duration** is modelled. The
  coverage columns are therefore firmer than the throughput columns.
- The sweep uses a single scripted patient. Branching means a chest-pain interview and
  a skin-complaint interview cost different amounts. The eval harness reports the
  spread across all 47 scenarios; this table is the shape, not the distribution.

---

## A safety bug this exercise found

Worth recording, because it only showed up once the budget was measured rather than
assumed.

Seven of the twenty red-flag rules originally read the detailed review-of-systems
slots — `ros.neuro` for stroke symptoms, `ros.gi` for gastrointestinal bleeding,
`ros.uro` for retention, and so on. Those sweeps sit at the back of the priority queue
and are the **first thing the budget displaces**. In a 240-second interview they were
never reached, which meant those seven rules could not fire at all.

A stroke flag that only works in an interview nobody has time for is not a safety
feature.

The fix was to lift the danger signs out of the sweeps into a single required node,
`ros.danger_signs`, asked early and never displaced in any mode — which is what triage
actually does. The detailed sweeps stayed for completeness, and the seven rules now
read either source.

This is the argument for building the measuring tool before the features it measures.
Nothing on any screen would have looked wrong.
