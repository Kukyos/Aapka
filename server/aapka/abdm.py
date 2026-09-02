"""Module D, second half — the ABDM transport.

Read this before demoing anything, because being straight about it is the whole point.

**The payload is real. The transport is not, yet.** `fhir.py` builds a genuine FHIR R4
document Bundle in the shape ABDM's Health Information Exchange carries. This module
sends it. In `mock` mode it writes the bundle to disk and returns a sandbox-shaped
response; in `sandbox` mode it posts to the real ABDM sandbox.

`03-requirements.md` lists "fake the ABDM integration" as a lose condition, and it is
right to: the sandbox is real, has a documented M1/M2/M3 milestone path, and a judge
can check. So nothing here pretends. Every mock response carries `"mock": true` and a
`notice` string that the doctor screen renders in the footer, so it is impossible to
stand in front of a demo and believe the integration is live.

To go live: obtain sandbox credentials, set ABDM_MODE=sandbox with ABDM_BASE_URL,
ABDM_CLIENT_ID and ABDM_CLIENT_SECRET. Nothing above this module changes.
Tracked as docs/11-deferred.md D-03.
"""

from __future__ import annotations

import json
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

from . import config

MOCK_NOTICE = (
    "ABDM transport is MOCKED. The FHIR bundle is real and structurally validated; "
    "it was written to disk, not transmitted. Sandbox credentials not yet obtained."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_bundle(bundle: dict[str, Any], session_id: str) -> str:
    config.BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    path = config.BUNDLE_DIR / f"{session_id}.json"
    path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def push(bundle: dict[str, Any], session_id: str, abha_id: str | None = None) -> dict[str, Any]:
    """Send the bundle onward. Returns a transport receipt, never raises."""
    if config.ABDM_MODE == "sandbox" and config.ABDM_BASE_URL and config.ABDM_CLIENT_ID:
        return _push_sandbox(bundle, session_id, abha_id)
    return _push_mock(bundle, session_id, abha_id)


def _push_mock(bundle: dict[str, Any], session_id: str, abha_id: str | None) -> dict[str, Any]:
    path = _write_bundle(bundle, session_id)
    return {
        "ok": True,
        "mock": True,
        "notice": MOCK_NOTICE,
        "transaction_id": str(uuid.uuid4()),
        "timestamp": _now(),
        "bundle_path": path,
        "bundle_id": bundle.get("id"),
        "entry_count": len(bundle.get("entry", [])),
        "abha_linked": bool(abha_id),
        "endpoint": "local://mock",
    }


def _push_sandbox(bundle: dict[str, Any], session_id: str, abha_id: str | None) -> dict[str, Any]:
    """Post to the real ABDM sandbox.

    Untested against the live sandbox, because we have no credentials yet. Written
    from the documented shape so that the first real attempt is a configuration
    change and a debugging session, not a rewrite.
    """
    path = _write_bundle(bundle, session_id)
    url = f"{config.ABDM_BASE_URL.rstrip('/')}/health-information/transfer"
    payload = {
        "requestId": str(uuid.uuid4()),
        "timestamp": _now(),
        "entries": [{"content": json.dumps(bundle), "media": "application/fhir+json"}],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-CM-ID": "sbx",
            "Authorization": f"Bearer {_sandbox_token()}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
        return {
            "ok": True,
            "mock": False,
            "notice": None,
            "transaction_id": payload["requestId"],
            "timestamp": payload["timestamp"],
            "bundle_path": path,
            "bundle_id": bundle.get("id"),
            "entry_count": len(bundle.get("entry", [])),
            "abha_linked": bool(abha_id),
            "endpoint": url,
            "response": body[:2000],
        }
    except Exception as exc:  # noqa: BLE001
        # Gate G1: the network is not to be assumed. A failed push must not lose the
        # intake — the bundle is already on disk and is queued for a later retry.
        return {
            "ok": False,
            "mock": False,
            "queued": True,
            "notice": "ABDM push failed. Bundle saved locally and queued for retry.",
            "error": str(exc),
            "bundle_path": path,
            "endpoint": url,
        }


def _sandbox_token() -> str:
    """Session token from ABDM gateway credentials. Cached per process would be an
    optimisation; correctness first, and this runs once per patient."""
    url = f"{config.ABDM_BASE_URL.rstrip('/')}/v0.5/sessions"
    request = urllib.request.Request(
        url,
        data=json.dumps(
            {"clientId": config.ABDM_CLIENT_ID, "clientSecret": config.ABDM_CLIENT_SECRET}
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))["accessToken"]


def status() -> dict[str, Any]:
    """Rendered in the doctor screen footer so a mock can never be mistaken for live."""
    live = (
        config.ABDM_MODE == "sandbox"
        and bool(config.ABDM_BASE_URL)
        and bool(config.ABDM_CLIENT_ID)
    )
    return {
        "mode": config.ABDM_MODE,
        "live": live,
        "notice": None if live else MOCK_NOTICE,
    }
