"""The deterministic dialogue engine.

This is the product. Everything else in the repo is a way of getting data into it or
getting a summary out of it.

It imports no web framework and touches no database. Given an ontology and a session
state, it returns the next action. That purity is what makes the eval harness cheap
and the behaviour reproducible: the same session state always yields the same next
question, in the same order, for the same reason.

The algorithm is in ``docs/09-architecture.md`` and is short enough to read in full.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .ontology import Node, Ontology, evaluate_guard, guard_description
from .redflags import evaluate as evaluate_red_flags

# Interview time budgets, in seconds.
#
# A hard budget, not a target: when it is spent, remaining non-required questions are
# dropped rather than the session running long. Every question added to the ontology
# therefore displaces another one, which is the discipline that keeps the
# terminal-count arithmetic in 04-targets.md honest.
#
# 06-decisions.md D1 set 240s as the working default for all patients. Measuring the
# graph showed that does not hold for an AYUSH interview: at 240s the Dashavidha block
# lands 5 of 10 parameters, which undercuts gate G5. The budgets below are the measured
# answer, and the full curve is in docs/12-budget-findings.md.
#
#   240s  core/allopathic mode — 7 of 7 SOCRATES
#   360s  AYUSH mode           — 7 of 7 SOCRATES and 10 of 10 Dashavidha
#    90s  returning patient    — confirm what is unchanged, ask only what is new
#
# Override per deployment via config; a hospital trading depth for throughput is a
# legitimate choice and the curve is published so they can make it with numbers.
BUDGET_CORE_S = 240
BUDGET_AYUSH_S = 360
BUDGET_RETURNING_S = 90

# Kept as an alias because the eval harness sweeps it.
BUDGET_NEW_PATIENT_S = BUDGET_CORE_S


@dataclass
class Answer:
    """One recorded answer. `respondent` travels with it, per requirement R1."""

    node_id: str
    slot: str
    value: Any
    respondent: str = "self"
    source: str = "touch"  # touch | voice | derived | document | prefilled
    elapsed_s: float = 0.0
    raw_utterance: str | None = None


@dataclass
class Session:
    """Everything the engine needs to know. Serialisable, no behaviour of its own."""

    id: str
    language: str = "en"
    mode: str = "ayush"  # ayush | core  — which question modes are enabled
    returning: bool = False
    slots: dict[str, Any] = field(default_factory=dict)
    answers: list[Answer] = field(default_factory=list)
    asked: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    red_flag: dict[str, Any] | None = None
    audit: list[dict[str, Any]] = field(default_factory=list)
    status: str = "active"  # active | complete | escalated | abandoned

    budget_override_s: int | None = None

    @property
    def budget_s(self) -> int:
        if self.budget_override_s is not None:
            return self.budget_override_s
        if self.returning:
            return BUDGET_RETURNING_S
        return BUDGET_AYUSH_S if self.mode == "ayush" else BUDGET_CORE_S

    @property
    def respondent(self) -> str:
        return self.slots.get("identity.respondent", "self")


def modes_enabled(session: Session) -> set[str]:
    """Which node modes this session asks.

    AYUSH mode is additive: an AYUSH interview asks the core history *and* the
    Dashavidha block. Gate G5 — AYUSH is the depth, not a replacement.
    """
    return {"core", "ayush"} if session.mode == "ayush" else {"core"}


def apply_answer(ont: Ontology, session: Session, answer: Answer) -> None:
    """Record an answer, then fill anything it makes derivable.

    Derivation is why nobody gets asked about their bowels twice, and why Vaya costs
    the patient zero seconds.
    """
    node = ont.node(answer.node_id)
    answer.respondent = answer.respondent or session.respondent

    session.slots[answer.slot] = answer.value
    session.answers.append(answer)
    session.elapsed_s += answer.elapsed_s or node.cost_s
    if answer.node_id not in session.asked:
        session.asked.append(answer.node_id)

    _apply_derivations(ont, session)


def skip(ont: Ontology, session: Session, node_id: str) -> None:
    """Patient declined a skippable question. Recorded, not silently dropped."""
    node = ont.node(node_id)
    if not node.skippable:
        raise ValueError(f"{node_id} is not skippable")
    session.skipped.append(node_id)
    session.elapsed_s += 2
    session.audit.append({"node": node_id, "why": "skipped by patient", "answered": None})


def _apply_derivations(ont: Ontology, session: Session) -> None:
    """Fill every node whose value follows from an answer already given.

    Runs to a fixed point, because one derivation can enable another.
    """
    enabled = modes_enabled(session)
    changed = True
    while changed:
        changed = False
        for node in ont.nodes:
            if not node.derived or node.slot in session.slots:
                continue
            # Mode gate. Without this a core-mode interview quietly picks up AYUSH
            # slots that no core question would ever have asked.
            if node.mode not in enabled:
                continue
            src_value = session.slots.get(node.derived["from"])
            if src_value is None:
                continue
            mapped = (node.derived.get("map") or {}).get(src_value)
            if mapped is None:
                continue  # no clean mapping for this value: ask the question instead
            session.slots[node.slot] = mapped
            session.answers.append(
                Answer(
                    node_id=node.id,
                    slot=node.slot,
                    value=mapped,
                    respondent=session.respondent,
                    source="derived",
                    elapsed_s=0.0,
                )
            )
            session.audit.append(
                {
                    "node": node.id,
                    "why": f"derived from {node.derived['from']}={src_value}",
                    "answered": mapped,
                }
            )
            changed = True


def visible_options(node: Node, slots: dict[str, Any]) -> list[dict[str, Any]]:
    """Options whose own guard passes.

    Option-level guards are why a man is never offered "periods problem" and why a
    headache patient sees head locations rather than every site in the ontology.
    """
    out = []
    for opt in node.options:
        if not evaluate_guard(opt.ask_if, slots):
            continue
        out.append({"value": opt.value, "label": opt.label, "icon": opt.icon})
    return out


def candidates(ont: Ontology, session: Session) -> list[Node]:
    """Unanswered, in-mode, guard-passing nodes, in ask order."""
    enabled = modes_enabled(session)
    out = []
    for node in ont.nodes:
        if node.slot in session.slots:
            continue
        if node.id in session.skipped:
            continue
        if node.mode not in enabled:
            continue
        if not evaluate_guard(node.ask_if, session.slots):
            continue
        out.append(node)
    return sorted(out, key=lambda n: (n.priority, n.id))


def coverage(ont: Ontology, session: Session) -> dict[str, Any]:
    """Per-section and SOCRATES coverage.

    This is the number that goes on the slide. It is a count of slots filled against
    slots that were *askable* for this patient — asking how far a cough radiates
    would not have been reachable, so it does not count against coverage.
    """
    enabled = modes_enabled(session)
    reachable: dict[str, set[str]] = {}
    filled: dict[str, set[str]] = {}

    for node in ont.nodes:
        if node.mode not in enabled:
            continue
        # A node is counted as reachable if its guard passes now, or if it was
        # actually asked. Guards that depend on unanswered slots are excluded, which
        # is the honest denominator.
        if not (evaluate_guard(node.ask_if, session.slots) or node.id in session.asked):
            continue
        reachable.setdefault(node.section, set()).add(node.slot)
        if session.slots.get(node.slot) is not None:
            filled.setdefault(node.section, set()).add(node.slot)

    sections = {}
    for section, slots in reachable.items():
        got = len(filled.get(section, set()))
        sections[section] = {
            "filled": got,
            "reachable": len(slots),
            "percent": round(100 * got / len(slots)) if slots else 0,
        }

    socrates_slots = {s.socrates: s.id for s in ont.slots.values() if s.socrates}
    socrates_reachable = {
        letter: slot
        for letter, slot in socrates_slots.items()
        if slot in {n.slot for n in ont.nodes if evaluate_guard(n.ask_if, session.slots)}
        or slot in session.slots
    }
    socrates_got = [
        letter
        for letter, slot in socrates_reachable.items()
        if session.slots.get(slot) is not None
    ]

    dashavidha_slots = [s.id for s in ont.slots.values() if s.dashavidha]
    dashavidha_got = [s for s in dashavidha_slots if session.slots.get(s) is not None]

    return {
        "sections": sections,
        "socrates": {
            "captured": sorted(socrates_got),
            "reachable": sorted(socrates_reachable),
            "text": f"{len(socrates_got)} of {len(socrates_reachable)}",
        },
        "dashavidha": {
            "captured": len(dashavidha_got),
            "total": len(dashavidha_slots),
            "text": f"{len(dashavidha_got)} of {len(dashavidha_slots)}",
        },
    }


def progress(session: Session) -> dict[str, Any]:
    budget = session.budget_s
    return {
        "answered": sum(1 for v in session.slots.values() if v is not None),
        "asked": len(session.asked),
        "elapsed_s": round(session.elapsed_s, 1),
        "budget_s": budget,
        "percent": min(100, round(100 * session.elapsed_s / budget)) if budget else 0,
    }


def next_action(ont: Ontology, session: Session) -> dict[str, Any]:
    """The engine's whole public surface.

    Returns exactly one of three actions — ask, complete, escalate — in the shape
    frozen in docs/09-architecture.md.
    """
    lang = session.language

    # 1. Red flags first, after every answer, never at the end. An escalation that
    #    arrives with the summary is not an escalation.
    fired = evaluate_red_flags(ont, session.slots)
    if fired:
        session.red_flag = {
            "id": fired.id,
            "severity": fired.severity,
            "label": fired.label.get(lang, fired.label["en"]),
            "instruction": fired.instruction.get(lang, fired.instruction["en"]),
            "staff_alert": fired.staff_alert,
            "source": fired.source,
        }
        session.status = "escalated"
        session.audit.append(
            {
                "node": None,
                "why": f"red flag {fired.id}: {guard_description(fired.when)}",
                "answered": None,
            }
        )
        return {
            "session_id": session.id,
            "action": "escalate",
            "question": None,
            "progress": progress(session),
            "red_flag": session.red_flag,
            "coverage": coverage(ont, session),
            "audit": session.audit,
        }

    pool = candidates(ont, session)

    if not pool:
        session.status = "complete"
        return _complete(ont, session, why="all reachable questions answered")

    node = pool[0]

    # 2. Budget. Required nodes are never displaced — a drug allergy is not dropped
    #    because the clock ran out. Everything else yields.
    remaining = session.budget_s - session.elapsed_s
    if node.cost_s > remaining and not node.required:
        forced = [n for n in pool if n.required]
        if not forced:
            session.status = "complete"
            return _complete(
                ont,
                session,
                why=f"time budget spent ({session.elapsed_s:.0f}s of {session.budget_s}s)",
            )
        node = forced[0]

    if node.id not in session.asked:
        session.asked.append(node.id)
    session.audit.append(
        {
            "node": node.id,
            "why": guard_description(node.ask_if),
            "answered": None,
        }
    )

    return {
        "session_id": session.id,
        "action": "ask",
        "question": render(node, session),
        "progress": progress(session),
        "red_flag": None,
        "coverage": coverage(ont, session),
        "audit": session.audit,
    }


def _complete(ont: Ontology, session: Session, why: str) -> dict[str, Any]:
    session.audit.append({"node": None, "why": f"complete: {why}", "answered": None})
    return {
        "session_id": session.id,
        "action": "complete",
        "question": None,
        "progress": progress(session),
        "red_flag": None,
        "coverage": coverage(ont, session),
        "audit": session.audit,
    }


def render(node: Node, session: Session) -> dict[str, Any]:
    """A node as the kiosk needs it: both languages, options already filtered."""
    return {
        "id": node.id,
        "slot": node.slot,
        "section": node.section,
        "type": node.answer_type,
        "prompt": node.prompt,
        "help": node.help,
        "options": visible_options(node, session.slots),
        "units": list(node.units),
        "min": node.min,
        "max": node.max,
        "anchors": node.anchors,
        "exclusive_value": node.exclusive_value,
        "skippable": node.skippable,
        "voice_preferred": node.voice_preferred,
        "self_report_proxy": node.self_report_proxy,
        "provenance": node.provenance,
        "cost_s": node.cost_s,
        "required": node.required,
    }


def run_scripted(ont: Ontology, session: Session, script: dict[str, Any]) -> Session:
    """Drive a whole interview from a dict of slot -> value.

    The eval harness runs on this. It is deliberately the same code path the kiosk
    uses — a scenario that passes here passes because the engine works, not because
    the test bypassed it.
    """
    while True:
        action = next_action(ont, session)
        if action["action"] != "ask":
            return session
        node_id = action["question"]["id"]
        node = ont.node(node_id)
        if node.slot in script:
            apply_answer(
                ont,
                session,
                Answer(
                    node_id=node_id,
                    slot=node.slot,
                    value=script[node.slot],
                    respondent=session.respondent,
                    source="touch",
                    elapsed_s=node.cost_s,
                ),
            )
        elif node.skippable:
            skip(ont, session, node_id)
        else:
            # The scenario has nothing to say here. Record it as unanswered and move
            # on rather than looping forever — a scenario with gaps is a legitimate
            # test case (patient goes quiet, proxy does not know).
            session.slots[node.slot] = None
            session.elapsed_s += node.cost_s
            session.audit.append(
                {"node": node_id, "why": "no scripted answer", "answered": None}
            )
