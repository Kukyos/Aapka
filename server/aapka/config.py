"""Configuration. Environment first, sensible defaults second, no secrets in the repo.

Everything here has a default that lets the whole system run with no `.env` at all.
That is not laziness — gate G1 says the network is not to be assumed, so "works with
nothing configured" is a requirement, not a convenience.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    """Minimal .env reader. Not python-dotenv — this is nine lines and one less pin."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_dotenv()


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


# --------------------------------------------------------------------- inference
GROQ_API_KEY = _env("GROQ_API_KEY")
GROQ_BASE_URL = _env("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_TEXT_MODEL = _env("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile")
GROQ_VISION_MODEL = _env("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
GROQ_ASR_MODEL = _env("GROQ_ASR_MODEL", "whisper-large-v3")

OLLAMA_BASE_URL = _env("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TEXT_MODEL = _env("OLLAMA_TEXT_MODEL", "llama3.1:8b")
OLLAMA_VISION_MODEL = _env("OLLAMA_VISION_MODEL", "llama3.2-vision:11b")

# Seconds. Deliberately short: a patient standing at a kiosk will not wait, and the
# keyword fallback below is always available. Slow is the same as broken here.
LLM_TIMEOUT_S = float(_env("LLM_TIMEOUT_S", "6"))

# --------------------------------------------------------------------- ABDM
# mock  — build the real FHIR bundle, post it to a local endpoint that logs it
# sandbox — post to the real ABDM sandbox (needs credentials)
ABDM_MODE = _env("ABDM_MODE", "mock")
ABDM_BASE_URL = _env("ABDM_BASE_URL", "")
ABDM_CLIENT_ID = _env("ABDM_CLIENT_ID")
ABDM_CLIENT_SECRET = _env("ABDM_CLIENT_SECRET")

# --------------------------------------------------------------------- storage
DB_PATH = Path(_env("DB_PATH", str(ROOT / "server" / "aapka.db")))
BUNDLE_DIR = Path(_env("BUNDLE_DIR", str(ROOT / "server" / "bundles")))

# --------------------------------------------------------------------- behaviour
# R3 in 03-requirements.md — a public terminal used by strangers back to back.
INACTIVITY_TIMEOUT_S = int(_env("INACTIVITY_TIMEOUT_S", "90"))
DEFAULT_MODE = _env("DEFAULT_MODE", "ayush")
DEFAULT_LANGUAGE = _env("DEFAULT_LANGUAGE", "hi")

# Doctor screen auth. A single shared token is enough for a demo and for a single
# consulting room; a real deployment authenticates against the hospital's own
# directory. Deliberately not pretending to be more than it is.
DOCTOR_TOKEN = _env("DOCTOR_TOKEN", "demo-doctor-token")

CORS_ORIGINS = [o for o in _env("CORS_ORIGINS", "*").split(",") if o]

# --------------------------------------------------------------------- phone handoff
# The kiosk cannot work out its own scannable address: its browser is on localhost, and
# a QR encoding "localhost" is a QR that works on exactly one device — the one that does
# not need it. So the server, which can see the machine's real interfaces, supplies it.
#
# Set PUBLIC_BASE_URL in a real deployment. It is also how the handoff gets HTTPS, which
# is what a phone needs before it will give the page a microphone or a camera — see
# D-16 in docs/11-deferred.md.
PUBLIC_BASE_URL = _env("PUBLIC_BASE_URL")
PATIENT_APP_PORT = _env("PATIENT_APP_PORT", "5173")


def lan_ip() -> str | None:
    """This machine's address on the hospital network.

    Opening a UDP socket to an unroutable address asks the OS which interface it would
    use, without sending a packet or needing anything to answer. `gethostname()` does
    not work here — on Windows it frequently resolves to loopback or a stale entry.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("10.255.255.255", 1))
        address = probe.getsockname()[0]
        return None if address.startswith("127.") else address
    except OSError:
        return None
    finally:
        probe.close()


def handoff_url() -> tuple[str | None, str]:
    """Where to point a patient's phone, and how honestly we know it.

    Returns (url, source). A null url means the kiosk shows no QR at all rather than a
    broken one — an unscannable code in a waiting hall is worse than no offer.
    """
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL.rstrip("/"), "configured"
    address = lan_ip()
    if not address:
        return None, "unavailable"
    return f"http://{address}:{PATIENT_APP_PORT}", "detected"


def status() -> dict[str, object]:
    """What is actually wired up right now. Rendered on the doctor screen footer and
    printed at startup, so nobody demos a mock believing it is live."""
    return {
        "groq": bool(GROQ_API_KEY),
        "groq_text_model": GROQ_TEXT_MODEL if GROQ_API_KEY else None,
        "ollama_url": OLLAMA_BASE_URL,
        "abdm_mode": ABDM_MODE,
        "abdm_credentials": bool(ABDM_CLIENT_ID and ABDM_CLIENT_SECRET),
        "db": str(DB_PATH),
    }
