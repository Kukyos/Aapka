"""End-to-end tests through the real HTTP API.

These drive the FastAPI app exactly as the kiosk does — create a session, consent,
answer questions until the engine says stop, submit — and then assert the two things
that matter most at the boundary: the escalation actually escalates, and the wipe
actually wipes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aapka import config  # noqa: E402
from aapka import session as store  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "api.db")
    monkeypatch.setattr(config, "BUNDLE_DIR", tmp_path / "bundles")
    # No network in tests. Everything below therefore exercises the deterministic
    # paths, which is also what the kiosk falls back to when the hospital wifi drops.
    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    monkeypatch.setattr(config, "OLLAMA_BASE_URL", "http://127.0.0.1:1")
    from aapka.api import app, _PENDING

    _PENDING.clear()
    store.init_db()
    with TestClient(app) as test_client:
        yield test_client


ROUTINE = {
    "identity.respondent": "self",
    "identity.age_band": "40_59",
    "identity.sex": "male",
    "cc.primary": "abdominal_pain",
    "hpi.onset": "gradual",
    "hpi.duration": {"n": 3, "unit": "weeks"},
    "hpi.associated": ["nausea"],
    "hpi.severity": 5,
    "ros.danger_signs": ["none"],
    "past.conditions": ["none"],
    "drugs.allergy_known": "none",
    "drugs.taking_now": False,
    "docs.has_papers": False,
}


def _drive(client, session_id: str, script: dict, limit: int = 80) -> dict:
    action = client.get(f"/api/session/{session_id}/next").json()
    for _ in range(limit):
        if action["action"] != "ask":
            return action
        question = action["question"]
        if question["slot"] in script:
            action = client.post(
                f"/api/session/{session_id}/answer",
                json={"node_id": question["id"], "value": script[question["slot"]], "source": "touch"},
            ).json()
        elif question["skippable"]:
            action = client.post(
                f"/api/session/{session_id}/skip", json={"node_id": question["id"]}
            ).json()
        else:
            action = client.post(
                f"/api/session/{session_id}/answer",
                json={"node_id": question["id"], "value": _fallback(question), "source": "touch"},
            ).json()
    raise AssertionError("interview did not terminate")


def _fallback(question: dict):
    if question["type"] == "multi_choice":
        return [question["options"][-1]["value"]]
    if question["type"] == "boolean":
        return False
    if question["type"] == "scale":
        return 3
    if question["type"] == "duration":
        return {"n": 1, "unit": "days"}
    if question["type"] == "text":
        return "not stated"
    return question["options"][0]["value"]


def test_health_reports_what_is_actually_wired(client):
    body = client.get("/api/health").json()
    assert body["ok"]
    assert body["ontology"]["nodes"] > 40
    # The point of this endpoint: nobody should demo a mock believing it is live.
    assert body["abdm"]["live"] is False
    assert body["abdm"]["notice"]


def test_full_intake_end_to_end(client):
    created = client.post("/api/session", json={"language": "hi", "mode": "ayush"}).json()
    session_id = created["session_id"]
    client.post(f"/api/session/{session_id}/consent",
                json={"capture": True, "share_with_hospital": True})

    action = _drive(client, session_id, ROUTINE)
    assert action["action"] == "complete"

    submitted = client.post(f"/api/session/{session_id}/submit", json={"abha_id": None}).json()
    assert submitted["ok"]
    assert submitted["fhir"]["valid"], submitted["fhir"]["validation_problems"]
    assert submitted["privacy"]["wiped"]
    # The bundle is real even though the transport is not.
    assert submitted["abdm"]["mock"] is True
    assert submitted["fhir"]["entries"] > 5


def test_submitted_session_is_gone_from_the_api(client):
    created = client.post("/api/session", json={"language": "en", "mode": "core"}).json()
    session_id = created["session_id"]
    client.post(f"/api/session/{session_id}/consent", json={"capture": True, "share_with_hospital": True})
    _drive(client, session_id, ROUTINE)
    client.post(f"/api/session/{session_id}/submit", json={"abha_id": None})

    # The brief: "temporary session data is cleared immediately after submission."
    assert client.get(f"/api/session/{session_id}/next").status_code == 404
    assert client.get(f"/api/session/{session_id}/summary").status_code == 404


def test_red_flag_escalates_and_raises_a_staff_alert(client):
    created = client.post("/api/session", json={"language": "hi", "mode": "ayush"}).json()
    session_id = created["session_id"]
    client.post(f"/api/session/{session_id}/consent", json={"capture": True, "share_with_hospital": True})

    action = _drive(client, session_id, {
        **ROUTINE,
        "cc.primary": "chest_pain",
        "hpi.onset": "sudden",
        "hpi.associated": ["breathlessness", "sweating"],
        "hpi.severity": 9,
    })
    assert action["action"] == "escalate"
    assert action["question"] is None
    assert action["red_flag"]["severity"] == "immediate"

    alerts = client.get("/api/triage/alerts").json()["alerts"]
    assert alerts and alerts[0]["session_id"] == session_id
    # Hard rule 1: the alert tells a human what to do, and names no disease.
    assert "infarct" not in alerts[0]["message"].lower()


def test_declining_consent_wipes_immediately(client):
    created = client.post("/api/session", json={"language": "hi"}).json()
    session_id = created["session_id"]
    body = client.post(f"/api/session/{session_id}/consent",
                       json={"capture": False, "share_with_hospital": False}).json()
    assert body["wiped"]
    assert client.get(f"/api/session/{session_id}/next").status_code == 404


def test_abandoned_session_never_reaches_the_doctor(client):
    created = client.post("/api/session", json={"language": "hi"}).json()
    session_id = created["session_id"]
    client.post(f"/api/session/{session_id}/consent", json={"capture": True, "share_with_hospital": True})
    client.get(f"/api/session/{session_id}/next")
    client.post(f"/api/session/{session_id}/abandon")

    queue = client.get("/api/doctor/queue",
                       headers={"Authorization": f"Bearer {config.DOCTOR_TOKEN}"}).json()
    assert all(row["session_id"] != session_id for row in queue["waiting"])


def test_api_rejects_an_undeclared_option(client):
    """A trust boundary. The kiosk is not the only thing that can POST here."""
    created = client.post("/api/session", json={"language": "en"}).json()
    session_id = created["session_id"]
    client.post(f"/api/session/{session_id}/consent", json={"capture": True, "share_with_hospital": True})
    action = client.get(f"/api/session/{session_id}/next").json()
    response = client.post(
        f"/api/session/{session_id}/answer",
        json={"node_id": action["question"]["id"], "value": "not_a_real_option", "source": "touch"},
    )
    assert response.status_code == 400


def test_unclear_utterance_is_not_guessed(client):
    """The anti-hallucination boundary, through HTTP."""
    created = client.post("/api/session", json={"language": "hi"}).json()
    session_id = created["session_id"]
    client.post(f"/api/session/{session_id}/consent", json={"capture": True, "share_with_hospital": True})
    action = client.get(f"/api/session/{session_id}/next").json()
    body = client.post(
        f"/api/session/{session_id}/answer",
        json={"node_id": action["question"]["id"], "utterance": "qwerty nonsense", "source": "voice"},
    ).json()
    assert body["accepted"] is False
    assert body["reason"] == "unclear"


def test_doctor_queue_requires_a_token(client):
    assert client.get("/api/doctor/queue").status_code == 401


def test_doctor_can_accept_amend_or_reject(client):
    """Gate G3 — nothing is permanent until the physician says so."""
    created = client.post("/api/session", json={"language": "en", "mode": "core"}).json()
    session_id = created["session_id"]
    client.post(f"/api/session/{session_id}/consent", json={"capture": True, "share_with_hospital": True})
    _drive(client, session_id, ROUTINE)
    client.post(f"/api/session/{session_id}/submit", json={"abha_id": None})

    headers = {"Authorization": f"Bearer {config.DOCTOR_TOKEN}"}
    queue = client.get("/api/doctor/queue", headers=headers).json()
    assert any(row["session_id"] == session_id for row in queue["waiting"])

    summary = client.get(f"/api/doctor/summary/{session_id}", headers=headers).json()
    assert summary["summary"]["sections"]
    assert summary["reviewed"] is False

    decided = client.post(
        f"/api/doctor/summary/{session_id}/decision",
        headers=headers,
        json={"decision": "accept", "amendments": None},
    ).json()
    assert decided["decision"] == "accept"
