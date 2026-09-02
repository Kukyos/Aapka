"""Red-flag evaluation. Gate G4.

Deterministic rules over slot values. No model is consulted, because a rule that
fires has to be a rule you can point at — in a demo, in an audit, and to a ministry.

Tuned for recall by construction: rules are ORed, the first match wins, and there is
no rule anywhere that lowers a patient's urgency. The system can only move someone
up the queue.
"""

from __future__ import annotations

from typing import Any

from .ontology import Ontology, RedFlagRule, evaluate_guard

# Evaluation order. `immediate` is checked before `urgent` so that when a patient
# trips both, the alert the staff see is the more serious one.
SEVERITY_ORDER = ("immediate", "urgent")


def evaluate(ont: Ontology, slots: dict[str, Any]) -> RedFlagRule | None:
    """Return the highest-severity rule that fires, or None.

    Called after every single answer — see engine.next_action.
    """
    for severity in SEVERITY_ORDER:
        for rule in ont.red_flags:
            if rule.severity != severity:
                continue
            if evaluate_guard(rule.when, slots):
                return rule
    return None


def evaluate_all(ont: Ontology, slots: dict[str, Any]) -> list[RedFlagRule]:
    """Every rule that fires, most severe first.

    The interview stops on the first one, but the staff alert is more useful when it
    lists everything that tripped. Also what the eval harness scores recall against.
    """
    out = []
    for severity in SEVERITY_ORDER:
        for rule in ont.red_flags:
            if rule.severity == severity and evaluate_guard(rule.when, slots):
                out.append(rule)
    return out
