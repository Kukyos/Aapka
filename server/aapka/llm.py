"""Model access, behind one adapter with a fallback ladder.

    Groq  ->  Ollama (local)  ->  caller's deterministic fallback

Every call reports which rung answered. That matters more than it looks: gate G1 says
the network is not to be assumed, so "which rung answered" is the difference between a
demo that proves offline operation and one that quietly needed wifi.

No SDK. Both providers speak HTTP and JSON, and `urllib` is in the standard library —
one less dependency to pin, one less thing to install on a teammate's laptop.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from . import config


@dataclass
class LLMResult:
    text: str
    provider: str  # groq | ollama | none
    ok: bool
    error: str | None = None


# urllib sends "Python-urllib/3.x" by default, and the CDN in front of the inference
# APIs refuses it outright — an HTTP 403 carrying Cloudflare's "error code: 1010",
# which looks exactly like a rejected API key and is not one. Naming ourselves fixes it.
USER_AGENT = "aapka-intake/1.0 (+https://github.com/kukyos/SIH2026)"


def _post_json(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"User-Agent": USER_AGENT, **headers}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _groq_chat(messages: list[dict], model: str, temperature: float) -> str:
    body = _post_json(
        f"{config.GROQ_BASE_URL}/chat/completions",
        {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 512,
        },
        {
            "Authorization": f"Bearer {config.GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        config.LLM_TIMEOUT_S,
    )
    return body["choices"][0]["message"]["content"]


def _ollama_chat(messages: list[dict], model: str, temperature: float) -> str:
    body = _post_json(
        f"{config.OLLAMA_BASE_URL}/api/chat",
        {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        },
        {"Content-Type": "application/json"},
        config.LLM_TIMEOUT_S,
    )
    return body["message"]["content"]


def chat(
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.0,
    vision: bool = False,
) -> LLMResult:
    """Try each provider in order. Never raises — a dead network is an expected state
    here, not an exception."""
    errors = []

    if config.GROQ_API_KEY:
        model = config.GROQ_VISION_MODEL if vision else config.GROQ_TEXT_MODEL
        try:
            return LLMResult(_groq_chat(messages, model, temperature), "groq", True)
        except Exception as exc:  # noqa: BLE001 - any failure means try the next rung
            errors.append(f"groq: {exc}")

    model = config.OLLAMA_VISION_MODEL if vision else config.OLLAMA_TEXT_MODEL
    try:
        return LLMResult(_ollama_chat(messages, model, temperature), "ollama", True)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"ollama: {exc}")

    return LLMResult("", "none", False, "; ".join(errors))


def chat_json(messages: list[dict[str, Any]], *, vision: bool = False) -> tuple[dict | None, str]:
    """Chat, then parse the reply as JSON.

    Models wrap JSON in prose and fences no matter how firmly you ask them not to, so
    the first balanced ``{...}`` is extracted rather than trusting the whole reply.
    Returns (parsed_or_None, provider).
    """
    result = chat(messages, temperature=0.0, vision=vision)
    if not result.ok:
        return None, result.provider
    text = result.text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None, result.provider
    try:
        return json.loads(text[start : end + 1]), result.provider
    except json.JSONDecodeError:
        return None, result.provider


def image_message(prompt: str, image_bytes: bytes, mime: str = "image/jpeg") -> list[dict]:
    """A vision message in the OpenAI-compatible shape Groq accepts."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }
    ]


def available() -> dict[str, bool]:
    """Which rungs answer right now. Shown in the health endpoint."""
    out = {"groq": False, "ollama": False}
    if config.GROQ_API_KEY:
        try:
            _groq_chat([{"role": "user", "content": "ping"}], config.GROQ_TEXT_MODEL, 0.0)
            out["groq"] = True
        except Exception:  # noqa: BLE001
            pass
    try:
        req = urllib.request.Request(f"{config.OLLAMA_BASE_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=2):
            out["ollama"] = True
    except Exception:  # noqa: BLE001
        pass
    return out
