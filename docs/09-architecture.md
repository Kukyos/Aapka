# Architecture and contracts

Two contracts matter more than any code in this repo: the **ontology node schema**
and the **engine response shape**. The patient screen, the doctor screen and the eval
harness all consume the second one; everything the interview does is defined by the
first. Both are frozen here before anything else is written.

The rule from `05-domain-reference.md` holds throughout: **the graph decides, the
model assists.** Nothing below lets a language model choose a question or end an
interview.

---

## Layout

```
ontology/          the question graph, as data. No code. Editable without a rebuild.
  slots.yaml       the output schema — every field the interview can fill
  questions/*.yaml the question nodes, grouped by history section
  redflags.yaml    deterministic escalation rules
  codes.yaml       complaint -> NAMASTE / ICD-11, each entry provenance-tagged

server/aapka/      Python. FastAPI at the edge, pure modules underneath.
  ontology.py      loader, validator, guard evaluator
  engine.py        the deterministic dialogue engine — pure, no I/O, no framework
  redflags.py      rule evaluation
  session.py       session state + SQLite + wipe-on-submit
  llm.py           provider adapter: Groq -> Ollama -> keyword
  nlu.py           utterance -> slot value
  asr.py           audio -> text
  ocr.py           image -> text
  documents.py     entity extraction, timeline, abnormal values, interactions
  summary.py       Module C — the physician-ready history
  fhir.py          Module D — FHIR R4 bundle
  abdm.py          ABDM transport (mock until credentials exist)
  api.py           HTTP surface

server/eval/       scenarios + runner + scorer
patient/           React kiosk
doctor/            React consultation view
```

**`engine.py` imports nothing from FastAPI and touches no database.** It is a pure
function of (ontology, session state) to next action. That is what makes 40 eval
scenarios cheap to run and the whole interview testable without a server.

---

## Contract 1 — the ontology node

Every question in the system is one of these. Gate G2 in `03-requirements.md` says
touch cannot be retrofitted onto a voice-first flow, so the spoken form and the
tappable form live in the **same node** and fill the **same slot**.

```yaml
- id: hpi.onset                  # unique, dotted, stable — appears in audit logs
  slot: hpi.onset                # which field in slots.yaml this fills
  section: hpi                   # summary section it belongs to
  mode: core                     # core | ayush  — ayush nodes only in AYUSH mode
  priority: 20                   # lower is asked earlier
  required: false                # true = asked even when over time budget
  cost_s: 8                      # estimated seconds; drives the budget
  ask_if:                        # optional guard; absent means always eligible
    all:
      - {slot: cc.primary, in: [abdominal_pain, chest_pain]}
  prompt:
    en: "When did this start?"
    hi: "यह कब शुरू हुआ?"
  help:                          # optional, spoken when the patient hesitates
    en: "Roughly is fine."
    hi: "अंदाज़ा भी चलेगा।"
  answer:
    type: single_choice          # see answer types below
    options:
      - value: today
        icon: onset-today        # icon key, resolved by the patient app
        label: {en: "Today", hi: "आज"}
```

### Answer types

| Type | Voice path | Touch path |
|---|---|---|
| `single_choice` | utterance mapped to one `value` | one tap on an option tile |
| `multi_choice` | utterance mapped to a list | tap several, then Done |
| `boolean` | yes / no in either language | two large tiles |
| `scale` | spoken number 0-10 | a row of tappable faces |
| `duration` | "three weeks" becomes `{n: 3, unit: weeks}` | number pad + unit tiles |
| `text` | free narration, stored verbatim | **a Skip tile — see below** |

Every type in this table has a renderer in `patient/src/QuestionScreen.tsx`. A type
with no renderer is a blank screen in a waiting hall, so the list is deliberately
short and adding to it is a load-time error until the kiosk can draw it.

`text` is deliberately rare, and **every `text` node must be `skippable`** — asserted
by `test_no_free_text_question_is_a_dead_end`. A kiosk has no keyboard, so the only
touch path for free text is a Skip tile; without it a patient whose speech recognition
fails cannot get past the question at all. Free text is an addition to a coded slot,
never the only place a fact lives.

### Guard grammar

Guards are **data, not code** — there is no `eval()` anywhere in the loader. A guard
is a condition or a combinator:

```
condition   {slot: <id>, <op>: <value>}
  ops       eq | ne | in | not_in | is_set | not_set | gte | lte |
            contains | not_contains
combinator  {all: [...]} | {any: [...]} | {not: {...}}
```

Anything else is a load-time validation error, not a runtime surprise.

---

## Contract 2 — the engine response

One shape, returned by `engine.next_action()` and by `POST /session/{id}/answer`. The
kiosk, the doctor screen and the eval runner all read this and nothing else.

```json
{
  "session_id": "b1f3...",
  "action": "ask",
  "question": { "...the node above, with options resolved..." },
  "progress": {
    "answered": 11, "asked": 12,
    "elapsed_s": 96, "budget_s": 240, "percent": 40
  },
  "red_flag": null,
  "audit": [
    {"node": "cc.primary", "why": "root", "answered": "abdominal_pain"},
    {"node": "hpi.onset",  "why": "guard cc.primary in [abdominal_pain,...]"}
  ]
}
```

`action` is one of three, and only three:

| `action` | Meaning | Screen behaviour |
|---|---|---|
| `ask` | `question` holds the next node | render it, speak it |
| `complete` | graph exhausted or budget spent | thank-you, wipe, submit |
| `escalate` | a red-flag rule fired | stop everything, alert staff |

`audit` is why this is defensible to a ministry: for every question asked, the exact
guard that caused it. Nothing was asked because a model felt like it.

---

## How the engine picks the next question

Deterministic, and short enough to read in full:

1. Apply the incoming answer to its slot.
2. Evaluate **red flags**. If one fires, return `escalate` and the interview is over.
3. Build the candidate set: nodes that are unanswered, whose `mode` is enabled, and
   whose `ask_if` guard passes against current slots.
4. Sort by `(priority, id)`. `id` breaks ties so runs are reproducible.
5. If the first candidate's `cost_s` would exceed the remaining budget **and** it is
   not `required`, return `complete`. Otherwise `ask` it.
6. Empty candidate set means `complete`.

Two consequences worth stating plainly, because they are the answer to "why not just
use an LLM":

- **Interview length is bounded by construction.** Step 5 is hard rule 8 from
  `08-rules-and-conventions.md` — a new question displaces an old one rather than
  extending the session. The terminal-count arithmetic in `04-targets.md` survives.
- **Coverage is provable.** Asked-and-answered is countable per section, so
  "9 of 9 SOCRATES dimensions captured" is a measurement, not a claim.

Red flags are checked **after every answer**, never at the end. Escalation that
arrives with the summary is not escalation.

---

## Where the models are allowed to touch anything

| Layer | Model | Constraint |
|---|---|---|
| ASR | Browser Web Speech API, or Groq Whisper large-v3 | Produces text. Never a slot value. |
| NLU | Groq, then Ollama, then keyword matcher | Maps an utterance onto **one already-chosen slot**, and may only return a value from that slot's declared option set, or `unclear`. It cannot invent a value and cannot pick the next question. |
| NLG | Same chain | May rephrase a prompt that already exists in the ontology. May not introduce a new question. |
| OCR | Groq vision, then Tesseract | Produces text and candidate entities from an image. Everything it extracts is marked `source: document` in the summary, never merged silently into what the patient said. |
| Summary | Templated assembly, model only for prose smoothing | The section order is fixed by `03-requirements.md`. No model chooses what goes in. |

The NLU constraint is the important one. A slot declares its legal values; the NLU
returns one of them or admits failure. That single rule is what makes hallucinated
history structurally impossible rather than merely unlikely.

### Fallback chain

Every model call walks the same ladder and reports which rung answered:

```
Groq  ->  Ollama (local)  ->  deterministic keyword matcher  ->  touch-only
```

The last rung is the point. Gate G1 says the network is not to be assumed; with every
model unavailable the kiosk still completes a full intake by touch, because the touch
path was never a fallback — it was always the primary path with a voice option
beside it.

---

## Session lifecycle

```
create -> consent -> identify -> interview -> documents -> read-back -> submit -> WIPE
                        |                                      |
             ABHA card or "I have none"        FHIR bundle -> HIS / ABHA
             (both paths equal, G1)            (mock until credentials)
```

**identify** is brief 3.4 Step 1. The card is read with the same OCR ladder the
document pipeline uses and matched against the 14-digit ABHA pattern; "I do not have
one" is a recorded answer, not a skipped step, because gate G1 says the primary flow
must work for a walk-in carrying nothing.

**read-back** is Module C's "patient-facing audio confirmation in local language". The
terminal speaks back the chief complaint, HPI, past history and drug/allergy sections
before anything is sent. It is the only point in the whole flow where the patient can
correct the machine — everything before it is the machine asking, and everything after
it is a doctor reading.

- Inactivity timeout returns the terminal to the attract loop and discards state (R3).
- Abandoned sessions are marked `abandoned`, never forwarded to a doctor (R2).
- On submit, the FHIR bundle is written, then the session row and all audio, images
  and transcripts for it are deleted. `test_session_wipe` asserts the row is gone —
  the brief requires this and DPDP 2023 backs it.
- Every field carries `respondent: self | relative | attendant` (R1). Proxy-sourced
  fields are visibly marked on the doctor screen, because "my mother has chest pain"
  is a different clinical fact from the patient saying it.

---

## What is mocked, and how you can tell

`abdm.py` builds a **real FHIR R4 bundle** and posts it to a local endpoint that
logs and returns a sandbox-shaped response. The payload is the real shape; the
transport is not. `ABDM_MODE=sandbox` plus credentials switches it, and nothing else
changes.

Anywhere the system would otherwise need a value we cannot source — NAMASTE codes,
ICD-11 TM2 codes, the full 91-item CCRAS Prakriti scale — the field is structurally
present and marked `PLACEHOLDER`, and listed in `docs/10-unsourced.md` with where the
real value comes from. Nothing plausible-looking is invented, because every one of
those is checkable by the people judging this.
