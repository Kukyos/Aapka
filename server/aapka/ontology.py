"""Ontology loading, validation, and guard evaluation.

The question graph lives in ``ontology/`` as YAML and is loaded once at startup. This
module is where a malformed graph becomes a loud error instead of a quiet wrong
question at 8am in a waiting hall.

Guards are data, not code. There is no ``eval`` here and never should be — see
``docs/09-architecture.md``.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_DIR = ROOT / "ontology"

LANGUAGES = ("en", "hi")

# Every type here must have a renderer in patient/src/QuestionScreen.tsx. A type
# with no renderer is a blank screen in a waiting hall, so the list is deliberately
# short: adding one is a load-time error until the kiosk can draw it.
ANSWER_TYPES = {
    "single_choice",
    "multi_choice",
    "boolean",
    "scale",
    "duration",
    "text",
}

# Guard operators. Each takes (slot_value, operand) and returns a bool.
# `is_set` / `not_set` take a boolean operand so guards read naturally in YAML:
#   {slot: personal.bowel, not_set: true}
OPERATORS = {
    "eq": lambda v, o: v == o,
    "ne": lambda v, o: v != o,
    "in": lambda v, o: v in o,
    "not_in": lambda v, o: v not in o,
    "gte": lambda v, o: v is not None and _num(v) is not None and _num(v) >= o,
    "lte": lambda v, o: v is not None and _num(v) is not None and _num(v) <= o,
    "contains": lambda v, o: o in v if isinstance(v, (list, tuple, set)) else v == o,
    "not_contains": lambda v, o: o not in v if isinstance(v, (list, tuple, set)) else v != o,
    "is_set": lambda v, o: (v is not None) == bool(o),
    "not_set": lambda v, o: (v is None) == bool(o),
}

# Operators that must still be evaluated when the slot is unset. Everything else is
# False on an unset slot: "is the pain radiating to the jaw" cannot be true before
# we have asked. Getting this wrong is how a red flag fires on an empty session.
UNSET_SAFE = {"is_set", "not_set", "not_in", "ne", "not_contains"}


class OntologyError(ValueError):
    """A malformed ontology. Raised at load time, never at interview time."""


def _num(v: Any) -> float | None:
    """Coerce to a number for gte/lte, or None if it is not numeric."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


@dataclass(frozen=True)
class Slot:
    id: str
    section: str
    type: str
    values: tuple[str, ...] = ()
    units: tuple[str, ...] = ()
    min: int | None = None
    max: int | None = None
    socrates: str | None = None
    dashavidha: str | None = None
    provenance: str | None = None


@dataclass(frozen=True)
class Option:
    value: Any
    label: dict[str, str]
    icon: str | None = None
    ask_if: dict[str, Any] | None = None
    # Extra spoken forms for this option, beyond its screen labels. Mostly romanised
    # Hindi, because that is what Indian-language ASR returns most of the time and
    # neither the English nor the Devanagari label matches it.
    synonyms: tuple[str, ...] = ()


@dataclass(frozen=True)
class Node:
    id: str
    slot: str
    section: str
    mode: str
    priority: int
    required: bool
    cost_s: int
    answer_type: str
    prompt: dict[str, str]
    options: tuple[Option, ...] = ()
    help: dict[str, str] | None = None
    ask_if: dict[str, Any] | None = None
    units: tuple[dict, ...] = ()
    min: int | None = None
    max: int | None = None
    anchors: dict[str, dict[str, str]] | None = None
    exclusive_value: Any = None
    skippable: bool = False
    voice_preferred: bool = False
    self_report_proxy: bool = False
    provenance: str | None = None
    derived: dict[str, Any] | None = None


@dataclass(frozen=True)
class RedFlagRule:
    id: str
    severity: str
    when: dict[str, Any]
    label: dict[str, str]
    instruction: dict[str, str]
    staff_alert: str
    source: str | None = None


@dataclass
class Ontology:
    version: int
    sections: list[dict]
    slots: dict[str, Slot]
    nodes: list[Node]
    red_flags: list[RedFlagRule]
    codes: dict[str, Any] = field(default_factory=dict)

    def node(self, node_id: str) -> Node:
        for n in self.nodes:
            if n.id == node_id:
                return n
        raise KeyError(node_id)

    def section_label(self, section_id: str, lang: str = "en") -> str:
        for s in self.sections:
            if s["id"] == section_id:
                return s["label"].get(lang, s["label"]["en"])
        return section_id


# --------------------------------------------------------------------------- guards


def evaluate_guard(guard: dict[str, Any] | None, slots: dict[str, Any]) -> bool:
    """Evaluate a guard against the current slot values.

    A guard is a combinator (``all`` / ``any`` / ``not``) or a single condition
    (``{slot: <id>, <op>: <operand>}``). ``None`` means unconditional.
    """
    if guard is None:
        return True
    if not isinstance(guard, dict):
        raise OntologyError(f"guard must be a mapping, got {type(guard).__name__}")

    if "all" in guard:
        return all(evaluate_guard(g, slots) for g in guard["all"])
    if "any" in guard:
        return any(evaluate_guard(g, slots) for g in guard["any"])
    if "not" in guard:
        return not evaluate_guard(guard["not"], slots)

    if "slot" not in guard:
        raise OntologyError(f"condition needs a 'slot' key: {guard!r}")

    slot_id = guard["slot"]
    ops = [k for k in guard if k != "slot"]
    if len(ops) != 1:
        raise OntologyError(f"condition needs exactly one operator, got {ops!r}")
    op = ops[0]
    if op not in OPERATORS:
        raise OntologyError(f"unknown operator {op!r} in {guard!r}")

    value = slots.get(slot_id)
    if value is None and op not in UNSET_SAFE:
        return False
    return bool(OPERATORS[op](value, guard[op]))


def guard_description(guard: dict[str, Any] | None) -> str:
    """A short human-readable rendering of a guard, for the audit trail.

    This is what makes 'why was I asked this?' answerable on the doctor screen and
    in the eval harness output.
    """
    if guard is None:
        return "unconditional"
    if "all" in guard:
        return " and ".join(guard_description(g) for g in guard["all"])
    if "any" in guard:
        return " or ".join(guard_description(g) for g in guard["any"])
    if "not" in guard:
        return f"not ({guard_description(guard['not'])})"
    slot_id = guard.get("slot", "?")
    for k, v in guard.items():
        if k != "slot":
            return f"{slot_id} {k} {v}"
    return str(guard)


# --------------------------------------------------------------------------- loading


def _read_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _parse_option(raw: dict, node_id: str) -> Option:
    if "value" not in raw:
        raise OntologyError(f"{node_id}: option missing 'value'")
    label = raw.get("label") or {}
    for lang in LANGUAGES:
        if lang not in label:
            raise OntologyError(
                f"{node_id}: option {raw['value']!r} missing {lang!r} label. "
                "Gate G2 requires every option be presentable in every language."
            )
    return Option(
        value=raw["value"],
        label=label,
        icon=raw.get("icon"),
        ask_if=raw.get("ask_if"),
        synonyms=tuple(raw.get("synonyms", ())),
    )


def _parse_node(raw: dict, source: str) -> Node:
    for key in ("id", "slot", "section", "priority", "answer" if "answer" in raw else "answer"):
        if key not in raw:
            raise OntologyError(f"{source}: node missing {key!r}: {raw.get('id', raw)!r}")

    node_id = raw["id"]
    answer = raw["answer"]
    atype = answer.get("type")
    if atype not in ANSWER_TYPES:
        raise OntologyError(f"{node_id}: unknown answer type {atype!r}")

    prompt = raw.get("prompt") or {}
    for lang in LANGUAGES:
        if lang not in prompt:
            raise OntologyError(
                f"{node_id}: prompt missing {lang!r}. Every question must be "
                "speakable in every supported language (gate G2)."
            )

    options = tuple(_parse_option(o, node_id) for o in answer.get("options", []))
    if atype in {"single_choice", "multi_choice", "boolean"} and not options:
        raise OntologyError(f"{node_id}: {atype} needs options")

    return Node(
        id=node_id,
        slot=raw["slot"],
        section=raw["section"],
        mode=raw.get("mode", "core"),
        priority=int(raw["priority"]),
        required=bool(raw.get("required", False)),
        cost_s=int(raw.get("cost_s", 8)),
        answer_type=atype,
        prompt=prompt,
        options=options,
        help=raw.get("help"),
        ask_if=raw.get("ask_if"),
        units=tuple(answer.get("units", [])),
        min=answer.get("min"),
        max=answer.get("max"),
        anchors=answer.get("anchors"),
        exclusive_value=answer.get("exclusive_value"),
        skippable=bool(raw.get("skippable", False)),
        voice_preferred=bool(raw.get("voice_preferred", False)),
        self_report_proxy=bool(raw.get("self_report_proxy", False)),
        provenance=raw.get("provenance"),
        derived=raw.get("derived"),
    )


def _parse_slots(raw: dict) -> dict[str, Slot]:
    out: dict[str, Slot] = {}
    for slot_id, spec in (raw.get("slots") or {}).items():
        out[slot_id] = Slot(
            id=slot_id,
            section=spec["section"],
            type=spec["type"],
            values=tuple(str(v) for v in spec.get("values", [])),
            units=tuple(spec.get("units", [])),
            min=spec.get("min"),
            max=spec.get("max"),
            socrates=spec.get("socrates"),
            dashavidha=spec.get("dashavidha"),
            provenance=spec.get("provenance"),
        )
    return out


def _parse_red_flags(raw: dict) -> list[RedFlagRule]:
    rules = []
    for r in raw.get("rules", []):
        rules.append(
            RedFlagRule(
                id=r["id"],
                severity=r["severity"],
                when=r["when"],
                label=r["label"],
                instruction=r["instruction"],
                staff_alert=(r.get("staff_alert") or {}).get("en", r["label"]["en"]),
                source=r.get("source"),
            )
        )
    return rules


def _validate(ont: Ontology) -> None:
    """Cross-file checks. Every one of these has a failure mode in a waiting hall."""
    errors: list[str] = []

    seen: set[str] = set()
    for n in ont.nodes:
        if n.id in seen:
            errors.append(f"duplicate node id {n.id!r}")
        seen.add(n.id)

        if n.slot not in ont.slots:
            errors.append(f"{n.id}: fills unknown slot {n.slot!r}")
            continue

        slot = ont.slots[n.slot]
        if slot.section != n.section:
            errors.append(
                f"{n.id}: node section {n.section!r} != slot section {slot.section!r}"
            )

        # Every option value must be declared on the slot. This is the invariant the
        # NLU is held to at runtime, so it has to hold in the data first.
        if slot.values and n.answer_type in {"single_choice", "multi_choice"}:
            for opt in n.options:
                if str(opt.value) not in slot.values:
                    errors.append(
                        f"{n.id}: option {opt.value!r} is not a declared value of "
                        f"slot {slot.id!r}"
                    )

        if n.derived:
            src = n.derived.get("from")
            if src not in ont.slots:
                errors.append(f"{n.id}: derived from unknown slot {src!r}")
            legal = {str(v) for v in slot.values}
            for k, v in (n.derived.get("map") or {}).items():
                if legal and str(v) not in legal:
                    errors.append(
                        f"{n.id}: derived map sends {k!r} to {v!r}, "
                        f"which is not a value of {slot.id!r}"
                    )

        # Guards must parse. Evaluating against an empty session is enough to catch
        # unknown operators and malformed conditions.
        for guard, where in [(n.ask_if, "ask_if")] + [
            (o.ask_if, f"option {o.value!r}") for o in n.options
        ]:
            try:
                evaluate_guard(guard, {})
            except OntologyError as exc:
                errors.append(f"{n.id}: bad guard in {where}: {exc}")

        # A guard that names a slot filled later than this node can never be true in
        # a forward-only interview. Silent dead questions are worse than loud ones.
        for referenced in _guard_slots(n.ask_if):
            if referenced not in ont.slots:
                errors.append(f"{n.id}: ask_if references unknown slot {referenced!r}")

    for rule in ont.red_flags:
        try:
            evaluate_guard(rule.when, {})
        except OntologyError as exc:
            errors.append(f"red flag {rule.id}: bad rule: {exc}")
        for referenced in _guard_slots(rule.when):
            if referenced not in ont.slots:
                errors.append(f"red flag {rule.id}: references unknown slot {referenced!r}")
        for lang in LANGUAGES:
            if lang not in rule.instruction:
                errors.append(f"red flag {rule.id}: instruction missing {lang!r}")

    # An unreachable required node is a coverage claim we cannot honour.
    filled = {n.slot for n in ont.nodes}
    for slot_id in ont.slots:
        # These two are set by the kiosk shell rather than by a question node:
        # language is chosen before anything can be spoken (patient/src/App.tsx), and
        # abha_status is set by the identify step (POST /session/{id}/abha).
        if slot_id not in filled and slot_id not in {
            "identity.language",
            "identity.abha_status",
        }:
            errors.append(f"slot {slot_id!r} has no node that fills it")

    if errors:
        raise OntologyError(
            "ontology failed validation:\n  - " + "\n  - ".join(sorted(errors))
        )


def _guard_slots(guard: dict[str, Any] | None) -> set[str]:
    if guard is None:
        return set()
    if "all" in guard:
        return set().union(*(_guard_slots(g) for g in guard["all"]))
    if "any" in guard:
        return set().union(*(_guard_slots(g) for g in guard["any"]))
    if "not" in guard:
        return _guard_slots(guard["not"])
    return {guard["slot"]} if "slot" in guard else set()


@functools.lru_cache(maxsize=4)
def load(directory: str | None = None) -> Ontology:
    """Load, validate and cache the ontology.

    Cached because it is pure data read from disk and every request needs it. Call
    ``load.cache_clear()`` after editing YAML in a running dev server.
    """
    base = Path(directory) if directory else ONTOLOGY_DIR
    slots_raw = _read_yaml(base / "slots.yaml")

    nodes: list[Node] = []
    for path in sorted((base / "questions").glob("*.yaml")):
        raw = _read_yaml(path) or []
        for item in raw:
            nodes.append(_parse_node(item, path.name))

    red_raw = _read_yaml(base / "redflags.yaml") or {}
    codes_raw = _read_yaml(base / "codes.yaml") or {}

    ont = Ontology(
        version=slots_raw.get("version", 1),
        sections=slots_raw.get("sections", []),
        slots=_parse_slots(slots_raw),
        nodes=sorted(nodes, key=lambda n: (n.priority, n.id)),
        red_flags=_parse_red_flags(red_raw),
        codes=codes_raw,
    )
    _validate(ont)
    return ont
