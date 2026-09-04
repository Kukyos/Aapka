# Setup guides — Tesseract and the NAMASTE portal

Step-by-step for the two things still blocked on a manual action. Written 2026-09-04.

Everything else needed to run the project is one command (`.\run.ps1 -Setup`); these two
are here because they involve an external installer and a government portal, and both
have a step that is easy to get wrong.

---

# 1 · Tesseract OCR

## Why this matters more than it looks

`documents.py` and `ocr.py` implement Module B of the brief — scanning prior
prescriptions, extracting diagnoses, medications with dosages, and lab values. They are
written, typed and unit-tested against fixtures. **No image has ever been through
them.**

The OCR ladder has two rungs: a vision model first, Tesseract underneath. The Groq
account we have carries no vision model, so with Tesseract missing there is no rung at
all. Until this is installed, the entire document pipeline is untested code, and no OCR
number in this project can ever be reported.

Five minutes. Nobody's approval needed.

## Install

The cleanest route on Windows:

```powershell
winget install UB-Mannheim.TesseractOCR
```

If `winget` is unavailable, download the installer from
<https://github.com/UB-Mannheim/tesseract/wiki> — that is the maintained Windows build,
and the one the `pytesseract` docs point at. Take the 64-bit `.exe`.

**During the installer, on the "Choose Components" screen, expand *Additional language
data* and tick Hindi (`hin`).** The default install is English only. Prescriptions in a
government OPD are not English only, and section 2.3 of the brief asks for multilingual
OCR by name. Devanagari support is a checkbox at install time and a reinstall later.

## The step that catches people

The installer does **not** add Tesseract to `PATH` by default. After installing, close
and reopen the terminal, then:

```powershell
tesseract --version
```

If that says the command is not recognised, add it manually — the default location is:

```
C:\Program Files\Tesseract-OCR
```

To add it for your user account without touching system settings:

```powershell
[Environment]::SetEnvironmentVariable(
    "Path",
    $env:Path + ";C:\Program Files\Tesseract-OCR",
    "User"
)
```

Then open a **new** terminal — the change does not reach shells that are already
running.

## Confirm the project can see it

```powershell
cd server
python -c "from aapka import ocr; print(ocr.tesseract_available())"
```

`True` means the rung is live. The same value appears in the health endpoint at
<http://localhost:8000/api/health> under `tesseract`, so a demo machine can be checked
at a glance.

## Then do the thing that actually matters

Installing it proves nothing. Photograph one real prescription — crumpled, handwritten,
whatever is nearest — and put it through:

```powershell
cd server
python -c "from aapka import ocr; d=open(r'C:\path\to\photo.jpg','rb').read(); r=ocr.read(d,'image/jpeg'); print(r.ok, r.provider); print(r.text[:600])"
```

Whatever comes out, that is the first real signal this project has ever had about
Module B. If it is garbage, that is a finding worth having now rather than in September.

Languages installed can be listed with `tesseract --list-langs`; expect at least `eng`
and, if the box was ticked, `hin`.

---

# 2 · The NAMASTE portal

## What we need from it

The National Ayush Morbidity Codes — NAMC for Ayurveda, NSMC for Siddha, NUMC for
Unani. The published figure is **7,340 Ayush morbidity codes**. We need the Ayurveda
list, to map our fourteen chief complaints onto it.

This is the last unsourced code system in the project. ICD-11 closed on 2026-09-04;
`ontology/codes.yaml` now carries sixteen sourced ICD-11 codes and fourteen empty
NAMASTE slots, every one marked `PLACEHOLDER`.

It matters more than an ordinary citation. The Ministry of Ayush owns this portal and
sponsors this problem statement. NAMASTE codes in the output are the part of the
submission the sponsoring ministry can check against its own database — and a
fabricated one is the specific failure they would catch.

## Register

<https://namaste.ayush.gov.in>

The portal publishes an *about* page, a user manual, dashboards and training material.
The code list itself is behind an account. There is no public API that we could find on
2026-09-02 or since.

Expect a government portal: registration will likely ask for an organisation or
institution, and approval may not be instant. Register as a student of your college if
there is no better option — the account is for reading a published classification, not
for submitting data.

## What to look for once you are in

Any of these, in order of usefulness:

1. **A downloadable NAMC export** — CSV, Excel, or a terminology file. Best outcome.
2. **A browsable code list** for Ayurveda morbidity. Workable; the fourteen complaints
   can be looked up by hand in an evening.
3. **An API or FHIR CodeSystem endpoint.** If one exists, say so — `tools/fetch_icd11.py`
   is the template and a NAMASTE fetcher beside it is a short job.

Also worth grabbing while logged in: whether NAMASTE publishes its own **mapping to
ICD-11 TM2**. India has a published roadmap for dual coding, and if the portal ships the
crosswalk then our TM2 side is already done and the two systems can be emitted together
with a citation.

## What to do with what you get

Nothing by hand. Send the file or the export and it goes into `ontology/codes.yaml` the
same way ICD-11 did — through a script, with a `source` field on every entry, and the
`sourced` provenance flipped only for codes that actually came back from the portal.
`test_codes_file_invariant_holds` will reject any entry marked `sourced` without a code.

**One rule this must not break.** Our fourteen complaints are patient-reported
*symptoms*. If the NAMC list turns out to be a list of Ayurvedic *diagnoses* — the way
ICD-11 TM2 turned out to be — then the same refusal applies: we hold the codes and do
not attach them to a chief complaint, because a kiosk choosing a diagnosis is the one
thing this system never does. Read the list before mapping it. See the note above
`complaints` in `ontology/codes.yaml` for how that was handled for TM2.

---

## Status after both of these

| | Closes | Leaves |
|---|---|---|
| Tesseract | Module B testable for the first time | D-01 — still need real prescriptions to photograph |
| NAMASTE | D-04, the last unsourced code system | nothing in the code; it is data-only |

Neither depends on the other, and neither depends on ABDM or Bhashini, both of which are
sitting in approval queues.
