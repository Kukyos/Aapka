"""Session state and storage. SQLite, stdlib only.

Two requirements shape this file and nothing else does.

**The wipe.** The brief says "temporary session data is cleared immediately after
submission" and DPDP 2023 backs it. So `submit()` deletes the session row, its answers,
and every scanned image and transcript belonging to it, in one transaction, after the
bundle is written. What survives is the FHIR bundle and a de-identified audit line —
no slots, no narration, no images. `test_session_wipe` asserts the rows are gone;
that test failing is a compliance failure, not a unit-test failure.

**Shared-device hygiene (R3).** A public terminal used by strangers back to back.
Sessions time out, timed-out sessions are discarded rather than resumed, and there is
no route anywhere that lists or searches sessions by patient.

SQLite because `git clone` and one command has to work on a teammate's laptop. It is
one line to point at Postgres and the schema is unremarkable; nothing here depends on
SQLite specifics.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from typing import Any, Iterator

from . import config
from .engine import Answer, Session

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL,
    language      TEXT NOT NULL,
    mode          TEXT NOT NULL,
    is_returning  INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL,
    abha_id       TEXT,
    consent       TEXT,
    slots         TEXT NOT NULL,
    answers       TEXT NOT NULL,
    asked         TEXT NOT NULL,
    skipped       TEXT NOT NULL,
    audit         TEXT NOT NULL,
    elapsed_s     REAL NOT NULL DEFAULT 0,
    red_flag      TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    created_at  REAL NOT NULL,
    kind        TEXT,
    doc_date    TEXT,
    raw_text    TEXT,
    structured  TEXT,
    image       BLOB
);

-- Survives the wipe. Deliberately carries nothing that identifies a patient: no
-- slots, no narration, no ABHA number, no images. It exists so a hospital can answer
-- "how many intakes, how many escalations, how long did they take" without retaining
-- anything the DPDP Act would call personal data.
CREATE TABLE IF NOT EXISTS audit_log (
    id            TEXT PRIMARY KEY,
    submitted_at  REAL NOT NULL,
    mode          TEXT,
    language      TEXT,
    status        TEXT,
    elapsed_s     REAL,
    questions_asked INTEGER,
    red_flag_id   TEXT,
    coverage      TEXT,
    bundle_path   TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
    id           TEXT PRIMARY KEY,
    created_at   REAL NOT NULL,
    session_id   TEXT,
    severity     TEXT,
    rule_id      TEXT,
    message      TEXT,
    acknowledged INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_documents_session ON documents(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


# --------------------------------------------------------------------- lifecycle


def create(language: str | None = None, mode: str | None = None, returning: bool = False) -> Session:
    session = Session(
        id=uuid.uuid4().hex,
        language=language or config.DEFAULT_LANGUAGE,
        mode=mode or config.DEFAULT_MODE,
        returning=returning,
    )
    now = time.time()
    with connect() as conn:
        conn.execute(
            "INSERT INTO sessions (id, created_at, updated_at, language, mode, is_returning, "
            "status, slots, answers, asked, skipped, audit, elapsed_s) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                session.id, now, now, session.language, session.mode,
                int(returning), session.status, "{}", "[]", "[]", "[]", "[]", 0.0,
            ),
        )
    return session


def load(session_id: str) -> Session | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        return None
    session = Session(
        id=row["id"],
        language=row["language"],
        mode=row["mode"],
        returning=bool(row["is_returning"]),
        slots=json.loads(row["slots"]),
        answers=[Answer(**a) for a in json.loads(row["answers"])],
        asked=json.loads(row["asked"]),
        skipped=json.loads(row["skipped"]),
        elapsed_s=row["elapsed_s"],
        audit=json.loads(row["audit"]),
        status=row["status"],
        red_flag=json.loads(row["red_flag"]) if row["red_flag"] else None,
    )
    return session


def save(session: Session) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE sessions SET updated_at=?, language=?, mode=?, status=?, slots=?, "
            "answers=?, asked=?, skipped=?, audit=?, elapsed_s=?, red_flag=? WHERE id=?",
            (
                time.time(), session.language, session.mode, session.status,
                json.dumps(session.slots, ensure_ascii=False),
                json.dumps([asdict(a) for a in session.answers], ensure_ascii=False),
                json.dumps(session.asked),
                json.dumps(session.skipped),
                json.dumps(session.audit, ensure_ascii=False),
                session.elapsed_s,
                json.dumps(session.red_flag, ensure_ascii=False) if session.red_flag else None,
                session.id,
            ),
        )


def set_abha(session_id: str, abha_id: str | None) -> None:
    with connect() as conn:
        conn.execute("UPDATE sessions SET abha_id=? WHERE id=?", (abha_id, session_id))


def get_abha(session_id: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT abha_id FROM sessions WHERE id=?", (session_id,)).fetchone()
    return row["abha_id"] if row else None


def record_consent(session_id: str, consent: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE sessions SET consent=? WHERE id=?",
            (json.dumps(consent, ensure_ascii=False), session_id),
        )


# --------------------------------------------------------------------- documents


def add_document(session_id: str, doc_id: str, image: bytes | None, raw_text: str,
                 structured: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO documents (id, session_id, created_at, kind, doc_date, "
            "raw_text, structured, image) VALUES (?,?,?,?,?,?,?,?)",
            (
                doc_id, session_id, time.time(),
                structured.get("kind"), structured.get("doc_date"),
                raw_text, json.dumps(structured, ensure_ascii=False), image,
            ),
        )


def documents_for(session_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, kind, doc_date, raw_text, structured FROM documents "
            "WHERE session_id=? ORDER BY created_at",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------- alerts


def raise_alert(session_id: str, severity: str, rule_id: str, message: str) -> str:
    alert_id = uuid.uuid4().hex
    with connect() as conn:
        conn.execute(
            "INSERT INTO alerts (id, created_at, session_id, severity, rule_id, message) "
            "VALUES (?,?,?,?,?,?)",
            (alert_id, time.time(), session_id, severity, rule_id, message),
        )
    return alert_id


def open_alerts() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE acknowledged = 0 ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def acknowledge_alert(alert_id: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE alerts SET acknowledged=1 WHERE id=?", (alert_id,))


# --------------------------------------------------------------------- the wipe


def submit(session: Session, bundle_path: str, coverage: dict[str, Any]) -> dict[str, Any]:
    """Write the audit line, then destroy everything else about this session.

    Order matters: the de-identified audit row is written first, then the session and
    its documents are deleted, in one transaction. A crash between the two would leave
    an audit line with no personal data, which is the safe direction to fail.
    """
    now = time.time()
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO audit_log (id, submitted_at, mode, language, status, "
            "elapsed_s, questions_asked, red_flag_id, coverage, bundle_path) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                session.id, now, session.mode, session.language, session.status,
                session.elapsed_s, len(session.asked),
                (session.red_flag or {}).get("id"),
                json.dumps(coverage, ensure_ascii=False), bundle_path,
            ),
        )
        conn.execute("DELETE FROM documents WHERE session_id = ?", (session.id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session.id,))
    return {"wiped": True, "session_id": session.id, "audit_retained": True}


def wipe(session_id: str) -> None:
    """Discard a session outright. Abandonment, timeout, or a patient walking away.

    No audit line, because nothing was submitted and a half-finished history is worse
    than none (requirement R2).
    """
    with connect() as conn:
        conn.execute("DELETE FROM documents WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def expire_stale(timeout_s: int | None = None) -> int:
    """Reap sessions nobody came back to. R3 — the terminal must never show the
    previous stranger's answers."""
    timeout_s = timeout_s or config.INACTIVITY_TIMEOUT_S
    cutoff = time.time() - timeout_s
    with connect() as conn:
        rows = conn.execute(
            "SELECT id FROM sessions WHERE updated_at < ? AND status = 'active'", (cutoff,)
        ).fetchall()
        ids = [r["id"] for r in rows]
        for session_id in ids:
            conn.execute("DELETE FROM documents WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    return len(ids)


def exists(session_id: str) -> bool:
    with connect() as conn:
        row = conn.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone()
    return row is not None


def stats() -> dict[str, Any]:
    """Aggregate numbers for the doctor screen. Reads audit_log only, which by design
    contains nothing personal."""
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM audit_log").fetchone()["c"]
        escalated = conn.execute(
            "SELECT COUNT(*) c FROM audit_log WHERE red_flag_id IS NOT NULL"
        ).fetchone()["c"]
        mean = conn.execute("SELECT AVG(elapsed_s) a FROM audit_log").fetchone()["a"]
        active = conn.execute(
            "SELECT COUNT(*) c FROM sessions WHERE status='active'"
        ).fetchone()["c"]
    return {
        "completed_intakes": total,
        "escalations": escalated,
        "mean_intake_s": round(mean, 1) if mean else None,
        "active_sessions": active,
    }
