"""Speech to text.

Two paths, and the split matters for gate G1:

  Browser    the kiosk's own Web Speech API. Runs in Chrome, supports hi-IN and
             en-IN, needs no install and no server round trip. This is the default
             path and the reason `git clone` and one command is enough.
  Groq       Whisper large-v3, server side. Used when the browser has no recogniser,
             when the audio was captured rather than streamed, and by the eval
             harness so that WER is measured against one consistent engine.

IndicConformer is the third path and is deliberately absent for now — it is a ~2.5GB
NeMo install that would break the one-command setup. `transcribe()` is the seam it
drops into, and nothing above this module changes when it does. See
docs/11-deferred.md.

NOTE ON NUMBERS: no word error rate may be reported from this module until hospital
ambient noise recordings exist. Clean-audio ASR figures are meaningless for a waiting
hall and 03-requirements.md R4 says so explicitly.
"""

from __future__ import annotations

import json
import mimetypes
import urllib.request
import uuid
from dataclasses import dataclass

from . import config


@dataclass
class Transcript:
    text: str
    language: str
    provider: str  # groq | browser | none
    ok: bool
    error: str | None = None


def _multipart(fields: dict[str, str], filename: str, content: bytes) -> tuple[bytes, str]:
    """Build a multipart/form-data body. urllib has no helper and requests is a
    dependency we do not otherwise need."""
    boundary = f"----aapka{uuid.uuid4().hex}"
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    parts: list[bytes] = []
    for key, value in fields.items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode()
        )
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
        f"filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n".encode()
    )
    parts.append(content)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def transcribe(audio: bytes, filename: str = "clip.webm",
               language: str | None = "hi") -> Transcript:
    """Audio to text. Never raises — a dead network is an expected state, and the
    kiosk falls back to the touch path, which was always the primary path anyway.

    `language=None` lets the model decide rather than pinning it, which is what the
    language screen wants: a patient who has not chosen a language yet cannot be asked
    to transcribe in one. `Transcript.language` reports what the model actually heard,
    not what it was told — a field that echoes its own input is not a detection.
    """
    if not config.GROQ_API_KEY:
        return Transcript(
            "", language or "", "none", False,
            "no GROQ_API_KEY; use the browser recogniser",
        )

    fields = {
        "model": config.GROQ_ASR_MODEL,
        # verbose_json is what carries the detected language back. Same cost.
        "response_format": "verbose_json",
        # Priming the decoder with the vocabulary it is about to hear measurably
        # helps on Indian-accented medical speech, and costs nothing.
        "prompt": (
            "Medical intake at an Indian government hospital. The speaker may mix "
            "Hindi and English. Expect words like bukhar, dard, pet, seena, saans, "
            "chakkar, ulti, kabz, sugar, BP, dama, khansi, kamzori."
        ),
    }
    if language:
        fields["language"] = language
    body, content_type = _multipart(fields, filename, audio)
    req = urllib.request.Request(
        f"{config.GROQ_BASE_URL}/audio/transcriptions",
        data=body,
        headers={
            "Authorization": f"Bearer {config.GROQ_API_KEY}",
            "Content-Type": content_type,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return Transcript(
            payload.get("text", "").strip(),
            payload.get("language") or language or "",
            "groq",
            True,
        )
    except Exception as exc:  # noqa: BLE001
        return Transcript("", language or "", "groq", False, str(exc))
