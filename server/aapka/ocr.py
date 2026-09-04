"""Document image to text. Module B, first half.

Two rungs:

  Vision LLM   Groq's Llama 4 vision model, then a local Ollama vision model. This is
               the rung that reads handwriting. Classical OCR does not — a doctor's
               handwritten prescription is the specific case Tesseract fails on, and
               it is the specific case judges will test.
  Tesseract    local, offline, and genuinely good on *printed* lab reports. Used when
               no model is reachable, and preferred for clean printed documents where
               it is faster and free.

Tesseract is optional. If it is not installed the vision rung still works, and if
neither works the patient simply does not scan documents — which is a smaller
interview, never a wrong one. Document extraction never blocks an intake.

NOTE ON NUMBERS: no OCR accuracy figure may be reported until real handwritten
prescriptions exist to measure against, and printed and handwritten must be reported
separately. See docs/11-deferred.md D-01.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import config, llm

_READ_PROMPT = (
    "This is a photograph of an Indian medical document — a prescription, a laboratory "
    "report, or a discharge summary. It may be handwritten, crumpled, or poorly lit, "
    "and it may mix English with Hindi.\n\n"
    "Transcribe everything you can read, exactly as written. Preserve the layout: keep "
    "each line on its own line, and keep values next to their labels.\n\n"
    "Rules:\n"
    "- Do not correct spellings, expand abbreviations, or tidy anything up.\n"
    "- Where you genuinely cannot read something, write [illegible]. Never guess a drug "
    "name or a number — a wrong dose is worse than a missing one.\n"
    "- Output the transcription only, with no commentary."
)


@dataclass
class OCRResult:
    text: str
    provider: str  # groq | ollama | tesseract | none
    ok: bool
    error: str | None = None


# Where the Windows installer puts it. It does not add itself to PATH, and a demo
# machine failing because of that would be an absurd way to lose Module B — "git clone
# and one command" has to survive an installer's defaults. Set TESSERACT_CMD to
# override; PATH still wins when tesseract is on it.
_TESSERACT_FALLBACKS = (
    "C:/Program Files/Tesseract-OCR/tesseract.exe",
    "C:/Program Files (x86)/Tesseract-OCR/tesseract.exe",
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
    "/opt/homebrew/bin/tesseract",
)


def tesseract_path() -> str | None:
    """The tesseract binary, or None. PATH first, then the usual install locations."""
    configured = config.TESSERACT_CMD
    if configured:
        return configured if Path(configured).exists() else None
    found = shutil.which("tesseract")
    if found:
        return found
    return next((p for p in _TESSERACT_FALLBACKS if Path(p).exists()), None)


def tesseract_available() -> bool:
    return tesseract_path() is not None


def _tesseract(image: bytes) -> OCRResult:
    binary = tesseract_path()
    if binary is None:
        return OCRResult("", "tesseract", False, "tesseract is not installed")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "page.png"
        src.write_bytes(image)
        try:
            # eng+hin: Indian prescriptions routinely mix scripts. If the Hindi
            # traineddata is missing tesseract errors, so fall back to eng alone.
            for langs in ("eng+hin", "eng"):
                proc = subprocess.run(
                    [binary, str(src), "stdout", "-l", langs],
                    capture_output=True,
                    timeout=60,
                )
                if proc.returncode == 0:
                    return OCRResult(proc.stdout.decode("utf-8", "replace").strip(), "tesseract", True)
            return OCRResult("", "tesseract", False, proc.stderr.decode("utf-8", "replace")[:200])
        except Exception as exc:  # noqa: BLE001
            return OCRResult("", "tesseract", False, str(exc))


def read(image: bytes, mime: str = "image/jpeg", *, prefer_local: bool = False) -> OCRResult:
    """Image to raw text.

    `prefer_local` puts Tesseract first, which is the right call for a clean printed
    lab report: it is faster, free, and offline.
    """
    if prefer_local:
        local = _tesseract(image)
        if local.ok and len(local.text) > 40:
            return local

    result = llm.chat(llm.image_message(_READ_PROMPT, image, mime), vision=True)
    if result.ok and result.text.strip():
        return OCRResult(result.text.strip(), result.provider, True)

    local = _tesseract(image)
    if local.ok:
        return local

    return OCRResult("", "none", False, result.error or local.error)
