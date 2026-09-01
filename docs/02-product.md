# What we are actually building

Plain language. No jargon. If a doc contradicts this one about *what the thing is*,
this one wins — except `01-problem-statement.md`, which always wins.

## The one-line version

A self-service terminal that takes a patient's medical history **before** they see
the doctor, so the doctor walks into the room already knowing everything.

It is **not** a records app, not a patient portal, not a chatbot, not a doctor's tool.
It is an intake machine that a stranger uses once, alone, standing up.

## The three pieces

**1. Patient screen** — a big touchscreen on a stand in the hospital waiting hall,
already switched on. Like an airport self check-in or an ATM. It speaks out loud,
listens, and has a camera so the patient can hold up their old prescriptions.

**2. Doctor screen** — a normal web page the doctor opens on their consulting-room
computer. Shows a one-page summary of what the patient told the machine outside.

**3. Server** — holds the question flowchart, converts speech to text, reads the
scanned papers, writes the summary, talks to the government health network.

That is the whole product. Two screens and a server.

## Who is who

| Role | Who | What they care about |
|---|---|---|
| Buyer | The hospital | Throughput. Doctors get 2 minutes per patient and it isn't enough. |
| Primary user | The patient | Often 60+, often can't read well, no smartphone, never used a machine like this, nobody helping them. |
| Secondary user | The doctor | Has 2 minutes. Wants to skip to the diagnosis. Will not tolerate reading a wall of text. |
| Sponsor | Ministry of Ayush | This is an **Ayurveda** hospital problem statement. That is not decoration — see `05-domain-reference.md`. |

## How a patient first accesses it

**They don't.** They walk up to a screen that is already running and start using it.

- No app download
- No sign-up
- No phone required
- No prior enrolment
- No training, no instructions from staff
- First time and probably only time they will ever use it

This single constraint drives most of the design. The problem statement explicitly
rejects mobile apps and chatbots *because* they need a phone, connectivity, and
prior enrolment. If our main flow needs any of those, we've built the thing they
already said doesn't work.

The doctor accesses their screen by opening a URL and logging in. Normal internal tool.

## End to end — the scene

Kamala, 62. Stomach pain for three weeks. Government Ayurveda hospital, 8am,
400 people ahead of her.

1. **Registration** — she gets her token at the counter as usual. We change nothing here.

2. **Attract** — while waiting she's pointed to a screen on a stand. It's looping an
   animation of a hand tapping, and speaking: *"Namaste. Touch anywhere to begin."*

3. **Language** — she touches it. Big buttons, each language shown in its own script
   **and spoken aloud**. She taps Hindi.

4. **Identify** — it asks her to hold her health ID card to the camera, or tap
   "I don't have one." Both paths work. She holds up the card.

5. **Interview** — one question at a time, big text, spoken aloud.
   *"What is troubling you today?"* — with six large picture buttons underneath
   (stomach, chest, head, joints, breathing, something else). She can **say it or tap it**.
   She taps the stomach. It follows up: how long, burning or dull, worse after eating,
   any vomiting. Each answerable by voice or touch.

6. **Ayurveda block** — because this is an Ayurveda hospital, it also asks what an
   Ayurvedic doctor needs: appetite, digestion, sleep, bowel habits, does she feel hot
   or cold, build, energy levels. This set has a name — *Dashavidha Pariksha*, the
   ten-point examination. It's much longer than a standard intake, and it is
   **exactly what gets skipped when there's no time**. That gap is the whole opportunity.

7. **Documents** — it asks if she has old papers. She holds a crumpled prescription and
   a blood test report up to the camera. The machine reads them, pulls out medicine
   names and test values, puts them in date order.

8. **Done** — about four minutes total. *"Thank you, please wait for your token."*
   The screen wipes itself clean for the next person.

9. **Consult** — an hour later her number is called. She walks in and **the doctor's
   screen already has her full history**: complaint, duration, the Ayurvedic assessment,
   her old medicines, her blood test with the abnormal value in red. The doctor reads it
   in fifteen seconds, corrects one line, and spends the rest of the time actually
   examining her.

## The safety branch

If at step 5 she had said *"chest pain and I can't breathe"*, the interview stops
immediately, the screen tells her to go to staff, and triage gets an alert. She skips
the queue. This branch must exist and must be demoed.

## What it must never do

Diagnose. Not once, not anywhere on any screen. The output is a **history** — what the
patient said — not an impression, not a differential, not a suggestion. The doctor
diagnoses. The problem statement is explicit: *"a draft to accept, amend, or reject,
never an autonomous diagnosis."*
