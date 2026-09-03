# Novelty candidates — what survives the cull

Four ideas were proposed. Two get built, one gets reduced to the part that was
already required, one gets rejected outright.

The filter is the same one the judges use: `03-requirements.md` gates G1–G5 and the
hard rules in `08-rules-and-conventions.md`. An idea that is impressive and breaks a
gate is worse than no idea, because the gate is what the brief actually asked for.

Last updated: 2026-09-03

---

## Verdict table

| # | Idea | Verdict | Why |
|---|---|---|---|
| 4 | QR handoff to the patient's own phone | **Build** | Explicitly permitted by G1. Nearly free. Fixes the weakest number in the project. |
| 3 | Language detection from first utterance | **Build** | Small, serves the walk-in carrying nothing, seam already exists. |
| 1 | "Call me" — phone/WhatsApp voice intake | **Reduce** | The voice quality half was already required. The telephony half is the alternative section 2.2 rejects. |
| 2 | Patient health dashboard / trackers | **Reject** | Breaks hard rule 6 and gate G1. ABDM already is this record. |

---

## 4 · QR handoff — build this first

**The idea.** A QR on the kiosk (and on the queue token) opens the same intake on the
patient's own phone, as a temporary session. No install, no account.

**Why it is not a G1 violation.** G1 rejects the smartphone as *the main path*. The
gate text permits the opposite of what it forbids, in as many words: "a companion
phone app may exist as a secondary convenience, never as the main path." The kiosk
stays the primary flow and stays complete on its own. Nothing here is enrolment: the
session is temporary, anonymous, and wiped on submission like every other session.

**Why it is nearly free.** `patient/src/App.tsx` holds `stage`, `lang`, the current
question and a progress number. Everything else — the graph walk, filled slots, red
flags, the budget clock — is server state behind `/api/session/{id}`. The phone is
the same React app pointed at the same server. The user's own concern was "how do we
forward all features when most of them run locally"; the answer is that almost nothing
runs locally. The two things that do — Web Speech ASR and TTS — are browser APIs the
patient's Chrome also has, and the camera on a phone is better than the one bolted to
a kiosk.

**Why it is the strongest of the four.** `12-budget-findings.md` opens its own
section with "84 terminals for a 5,000-patient hospital is the weakest number in this
project." A patient who intakes on their own phone consumes no terminal. This idea
does not add a feature; it deletes the objection.

**What has to be true.** The handoff must not become a queue-jump for people with
phones — it is the same queue, filled out in a different place. And the kiosk must
never say "scan this instead," only "or scan this."

## 3 · Language detection from the first utterance

**The idea.** Patient speaks; the system picks the language rather than asking.

**Verdict: build, as a pre-selection, never as a replacement.** The language select
screen stays exactly where it is. Detection moves the highlight onto the likely
choice; the patient confirms with one tap. That way a wrong detection costs a tap,
not a failed intake, and the touch path stays at parity per G2.

**Cost.** Small. `asr.py` already routes to Whisper large-v3, which returns a detected
language alongside the transcript, and `Transcript` already carries a `language`
field. With only English and Hindi shipping (D-12), this is a two-way decision with a
confidence floor and a shrug.

**The fallback that matters.** Below the confidence floor, do nothing and show the
screen unchanged. Silence, noise, and a hall full of other people talking must all
land on "ask normally," never on a confident wrong guess.

## 1 · "Call me" — reduced to its useful half

The proposal bundles two separable things.

**(a) Voice that does not sound like a robot and can be interrupted.** Keep. This was
never a novelty — it is Phase 3 of `07-build-plan.md` and gate G2, and it is required
for the kiosk whether or not a phone is ever involved. Barge-in specifically: today
`speech.ts` has `stopSpeaking()` and the prompt runs to completion. Letting the
patient talk over the prompt is the single highest-value voice improvement, and it
benefits the kiosk directly.

**(b) Telephony: enter a number, get a call, complete the intake by voice.** Defer.

Three reasons, in order of weight:

1. **It is the rejected alternative.** Section 2.2 names "tele-triage chatbots" as a
   thing the brief is dissatisfied with. Leading with an AI voice call invites the
   reading that we did not finish section 2.
2. **It moves no gate.** G1–G5 are unaffected. It is a channel, not a capability, and
   the capability it would carry is the same interview we already run.
3. **The build is a cliff, not a slope.** A telephony provider, streaming ASR instead
   of turn-based, sub-second TTS, echo cancellation, barge-in over a lossy line, and
   an interruption model that works when the audio is 8 kHz narrowband. None of it is
   reusable by the kiosk.

**The reframe worth putting on a slide, though.** A *phone call* is the only channel
that beats the kiosk on reach, because it does not need a smartphone — a feature
phone in a village takes a call. That is a genuinely strong second act, and it is
strong precisely because it is the anti-smartphone argument, not the smartphone one.
State it as the roadmap. Build it after the demo works.

## 2 · Patient health dashboard — rejected

**The idea.** A profile the patient maintains: medicine tracker, weight tracker,
longitudinal health view.

**Rejected, on three counts.**

1. **It breaks hard rule 6.** Session data is wiped on submission. A dashboard is a
   persistent per-patient store — the exact opposite, and the wipe is a thing we
   promise and prove.
2. **It breaks G1.** A profile the patient maintains between visits is patient
   enrolment ahead of the visit, which section 2.2 rejects by name.
3. **It was not asked for.** The brief wants a pre-consultation intake terminal. A
   health tracker is a different product with a different regulatory surface, and
   building it costs us the thing that was asked.

**The legitimate need underneath it, and where it already lives.** "The patient has a
history and we should use it" is correct — and that is ABDM. The longitudinal record
belongs to the patient's ABHA, not to our database. Re-implementing it is not
ambition, it is the failure mode: we would be building a worse copy of the national
health record while the actual integration (D-03) sits unregistered.

The intake-side version of this need is the **returning-patient fast path** — pull the
last visit, confirm what is unchanged, ask only what is new. It is designed, the
engine supports it, and it is blocked on D-03 and nothing else. See D-10 and D-15 in
`11-deferred.md`. That is where this energy should go.

---

## Built — 2026-09-03

All three survivors are in. What is here is what shipped, including what it does not do.

### Barge-in · `patient/src/speech.ts`, `QuestionScreen.tsx`

The patient can answer over the top of the prompt. `armBargeIn()` opens the microphone
only while the prompt is being spoken plus a 2.5 s grace window, measures loudness and
nothing else, and closes itself either way — the microphone is not hot for the rest of
the interview, which is the version of this feature we can defend alongside the wipe.

The problem worth recording: on a kiosk the microphone sits beside the speaker, and
`echoCancellation` does not help because `speechSynthesis` output never enters the
browser's audio graph. So the noise floor is calibrated **during the first 700 ms of the
prompt** rather than during silence. The machine's own voice becomes the baseline and
only a person over the top of it clears the margin. Four named constants, tuned on a
quiet desk — D-17.

Both failure directions are safe: a missed barge-in means the prompt finishes and the
patient presses the microphone as before; a false one stops the prompt and shows
"Listening…", which can be ignored in favour of tapping. Nothing about the touch path
changes either way.

### Language pre-selection · `speech.ts`, `App.tsx`

The language screen listens while it asks and moves the highlight onto what it hears.
Detection is by *script*, not vocabulary: Chrome's `hi-IN` recogniser returns Devanagari
for Hindi and Latin for English, which is more robust than any word list, costs nothing,
and needs no network — the only kind of detection G1 permits. Below four script-bearing
characters it declines to decide and the screen is untouched.

It pre-selects and never replaces. Both tiles stay where they were, the patient still
confirms with a tap, and the confirmation is spoken in the detected language, which is
itself the check — someone who does not understand it knows instantly the guess was
wrong. Ten cases in `patient/check.mjs`, run by `.un.ps1 -Test`.

`asr.py` also stopped lying: `Transcript.language` used to echo whatever language it was
handed. It now reports what Whisper actually detected, and `language=None` lets the model
decide. A field that echoes its own input is not a detection.

### Phone handoff · `Handoff.tsx`, `GET /api/handoff`

A QR in the corner of the attract screen opens the intake on the patient's own phone.
No tokens, no session transfer, no account, no install — it is the same anonymous
temporary session, started on a different screen, wiped on submission like any other.

The design question was whether to build a session-transfer token so a patient could
start at the kiosk and continue on their phone. Cut: the throughput argument does not
need it, and the scenario it serves — someone abandoning a terminal mid-interview to
switch devices — is contrived. What is real is the patient on the bench who never
occupies a terminal at all, and that needs nothing but a URL.

One thing the server has to supply: the kiosk's browser thinks it lives on `localhost`,
and a QR encoding `localhost` works on exactly the one device that does not need it. So
`config.lan_ip()` asks the OS which interface it would route from, and the route returns
that or an explicit null — the kiosk shows no QR rather than an unscannable one.

**The limit, stated on the kiosk itself:** over plain HTTP a phone gives the page no
microphone and no camera. The phone path is therefore touch-only and cannot run the
document step, so the QR panel tells the patient to bring their papers to the counter.
`PUBLIC_BASE_URL` is the one-line fix and any real deployment terminates TLS anyway.
D-16. Do not describe this on a slide as "the full intake on your phone".

### Not built

The telephony half of "call me", and the patient dashboard. Reasons above; neither
changed on contact with the code.
