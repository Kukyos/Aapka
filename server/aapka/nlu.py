"""Utterance to slot value.

This module is where the architectural rule from `05-domain-reference.md` is actually
enforced, so it is worth being precise about what it may and may not do.

It is called with **one node that the engine has already chosen**. Its only job is to
decide which of that node's declared options the patient just said. It cannot pick the
next question, cannot invent a value, and cannot return anything outside the option
set. The return is always one of the node's own values, or ``unclear``.

That constraint is what makes hallucinated history structurally impossible rather than
merely unlikely. A model that returns junk produces ``unclear``, and ``unclear`` makes
the kiosk re-ask or fall back to touch — which is a worse interview, never a wrong one.

Three rungs, tried in order:

    1. keyword    deterministic, offline, instant. Handles the direct answers, which
                  in testing is most of them: people say "three weeks" and "burning".
    2. LLM        Groq, then Ollama. For the indirect ones — "it's been since Diwali",
                  "like someone is sitting on my chest".
    3. unclear    admit failure and let the kiosk re-ask or wait for a tap.

The keyword rung runs FIRST, not last. It is faster, free, works with no network, and
on a direct answer it is more reliable than a model. The LLM is the fallback here, not
the primary — which is the inverse of how these systems are usually built and is the
reason this one keeps working when the wifi drops.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from . import llm
from .ontology import Node

UNCLEAR = "unclear"


@dataclass
class NLUResult:
    value: Any
    confidence: float
    method: str  # keyword | groq | ollama | none
    matched_text: str | None = None

    @property
    def ok(self) -> bool:
        return self.value is not None and self.value != UNCLEAR


# --------------------------------------------------------------------- normalising

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").strip().lower()
    text = text.translate(_DEVANAGARI_DIGITS)
    return re.sub(r"\s+", " ", text)


# --------------------------------------------------------------------- yes / no
# Both scripts and both transliterations, because ASR output for Hindi comes back in
# Devanagari from some engines and in Latin from others, and a kiosk cannot care.
YES_WORDS = {
    "yes", "yeah", "yep", "yup", "correct", "right", "true", "ok", "okay", "sure",
    "haan", "han", "haa", "ha", "ji", "ji haan", "jee", "bilkul", "sahi",
    "हाँ", "हां", "जी", "जी हाँ", "बिल्कुल", "सही", "ठीक",
}
NO_WORDS = {
    "no", "nope", "nah", "not", "never", "false", "negative",
    "nahi", "nahin", "na", "kabhi nahi", "bilkul nahi",
    "नहीं", "ना", "नही", "कभी नहीं", "बिल्कुल नहीं",
}
UNSURE_WORDS = {
    "dont know", "don't know", "not sure", "no idea", "cant say", "can't say", "maybe",
    "pata nahi", "pata nahin", "maalum nahi", "malum nahi", "yaad nahi",
    "पता नहीं", "मालूम नहीं", "याद नहीं", "बता नहीं सकता", "शायद",
    "samajh nahi", "samajh nahin", "nahi pata", "nahin pata", "kya pata",
    "समझ नहीं", "नहीं पता", "क्या पता", "कह नहीं सकता",
}

# Number words, for durations and scales spoken rather than tapped.
NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "couple": 2, "few": 3, "several": 3,
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5,
    "chhe": 6, "che": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पाँच": 5, "पांच": 5, "छह": 6,
    "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
}

DURATION_UNITS = {
    "hours": ["hour", "hours", "hrs", "ghanta", "ghante", "घंटा", "घंटे"],
    "days": ["day", "days", "din", "दिन", "roz"],
    "weeks": ["week", "weeks", "hafta", "hafte", "haftey", "हफ़्ता", "हफ्ता", "हफ़्ते", "हफ्ते", "saptah", "सप्ताह"],
    "months": ["month", "months", "mahina", "mahine", "महीना", "महीने", "maheena"],
    "years": ["year", "years", "saal", "sal", "साल", "बरस", "varsh", "वर्ष"],
}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\wऀ-ॿ']+", text)


def _phrase_hit(text: str, words: set[str]) -> str | None:
    """Longest phrase first, so 'bilkul nahi' beats 'bilkul'."""
    for word in sorted(words, key=len, reverse=True):
        if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text):
            return word
    return None


# --------------------------------------------------------------------- keyword rung


def _label_synonyms(node: Node, value: Any) -> list[str]:
    """Match against the option's own labels in both languages.

    Nothing hand-maintained: the ontology already carries what each option is called
    in English and Hindi, so those *are* the synonyms. Adding a language adds its
    synonyms for free, which is why adding Tamil later is a data change only.
    """
    out = []
    for opt in node.options:
        if opt.value != value:
            continue
        for text in list(opt.label.values()) + list(opt.synonyms):
            cleaned = normalise(re.sub(r"\(.*?\)", "", text))
            out.append(cleaned)
            # Labels are written as sentences for the screen ("Yes, from a medicine").
            # The distinctive part is usually after the comma or before the dash.
            for piece in re.split(r"[,—-]", cleaned):
                piece = piece.strip()
                if len(piece) >= 3:
                    out.append(piece)
    return [o for o in dict.fromkeys(out) if o]


def _syn_pattern(syn: str) -> str:
    """Regex for a synonym, tolerating filler words inside a phrase.

    People do not say "pet mein dard", they say "mere pet mein BAHUT dard ho raha hai".
    Strict adjacency misses that, and it is the single commonest shape of a real spoken
    complaint. Up to two filler words are allowed between the parts of a multi-word
    synonym; single words still have to match exactly, so "do" cannot match "doctor".
    """
    parts = [re.escape(p) for p in syn.split() if p]
    if not parts:
        return r"(?!)"
    if len(parts) == 1:
        return rf"(?<!\w){parts[0]}(?!\w)"
    gap = r"(?:\W+\w+){0,2}\W+"
    return r"(?<!\w)" + gap.join(parts) + r"(?!\w)"


def _match_choice(node: Node, text: str) -> NLUResult | None:
    best: tuple[int, Any, str] | None = None
    for opt in node.options:
        for syn in _label_synonyms(node, opt.value):
            if re.search(_syn_pattern(syn), text):
                if best is None or len(syn) > best[0]:
                    best = (len(syn), opt.value, syn)
    if best:
        # Longer match means more of the utterance was accounted for.
        return NLUResult(best[1], min(0.95, 0.6 + best[0] / 40), "keyword", best[2])
    return None


def _match_number(text: str) -> int | None:
    digits = re.search(r"\d+", text)
    if digits:
        return int(digits.group())
    found = [NUMBER_WORDS[t] for t in _tokens(text) if t in NUMBER_WORDS]
    return found[-1] if found else None


def _match_duration(text: str) -> dict | None:
    unit = None
    for canonical, words in DURATION_UNITS.items():
        if any(re.search(rf"(?<!\w){re.escape(w)}", text) for w in words):
            unit = canonical
            break
    if unit is None:
        return None
    n = _match_number(text)
    if n is None:
        # "since a week", "kuch dino se" — a unit with no number still means one.
        n = 1
    return {"n": n, "unit": unit}


def keyword_extract(node: Node, text: str) -> NLUResult:
    """The deterministic rung. Also the offline rung, and the fast rung."""
    text = normalise(text)
    if not text:
        return NLUResult(None, 0.0, "keyword")

    if node.answer_type == "boolean":
        if _phrase_hit(text, NO_WORDS):
            return NLUResult(False, 0.9, "keyword")
        if _phrase_hit(text, YES_WORDS):
            return NLUResult(True, 0.9, "keyword")
        return NLUResult(None, 0.0, "keyword")

    if node.answer_type == "scale":
        n = _match_number(text)
        if n is not None:
            lo = node.min if node.min is not None else 0
            hi = node.max if node.max is not None else 10
            return NLUResult(max(lo, min(hi, n)), 0.85, "keyword")
        return NLUResult(None, 0.0, "keyword")

    if node.answer_type == "duration":
        got = _match_duration(text)
        if got:
            return NLUResult(got, 0.85, "keyword")
        return NLUResult(None, 0.0, "keyword")

    if node.answer_type == "number":
        n = _match_number(text)
        return NLUResult(n, 0.85, "keyword") if n is not None else NLUResult(None, 0.0, "keyword")

    if node.answer_type == "text":
        # Free narration is stored verbatim. There is nothing to extract, and
        # "improving" what the patient said is exactly what we must not do.
        return NLUResult(text, 1.0, "keyword")

    if node.answer_type == "multi_choice":
        hits = []
        for opt in node.options:
            for syn in _label_synonyms(node, opt.value):
                if re.search(_syn_pattern(syn), text):
                    hits.append(opt.value)
                    break
        if hits:
            if node.exclusive_value is not None and node.exclusive_value in hits and len(hits) > 1:
                # "nothing else, just some nausea" — the specific beats the blanket.
                hits = [h for h in hits if h != node.exclusive_value]
            return NLUResult(list(dict.fromkeys(hits)), 0.8, "keyword")
        if _phrase_hit(text, NO_WORDS) and node.exclusive_value is not None:
            return NLUResult([node.exclusive_value], 0.75, "keyword")
        return NLUResult(None, 0.0, "keyword")

    # single_choice
    hit = _match_choice(node, text)
    if hit:
        return hit
    if _phrase_hit(text, UNSURE_WORDS):
        for candidate in ("unsure", "unassessed", "unclear"):
            if any(o.value == candidate for o in node.options):
                return NLUResult(candidate, 0.8, "keyword")
    return NLUResult(None, 0.0, "keyword")


# --------------------------------------------------------------------- LLM rung

_SYSTEM = (
    "You map a patient's spoken reply onto ONE field of a medical intake form.\n"
    "You are given the question and the ONLY permitted answers.\n"
    "Rules you must follow exactly:\n"
    "1. Reply with JSON only: {\"value\": <answer>, \"confidence\": <0.0-1.0>}\n"
    "2. `value` MUST be copied exactly from the permitted list. Never invent one.\n"
    "3. If the reply does not clearly match a permitted answer, use "
    '{"value": "unclear", "confidence": 0.0}.\n'
    "4. Never infer a symptom the patient did not mention. Under-reporting is correct; "
    "guessing is not.\n"
    "5. The reply may be in English, Hindi, or a mix of both."
)


def _llm_extract(node: Node, text: str) -> NLUResult:
    permitted = [str(o.value) for o in node.options] or {
        "scale": ["a whole number from 0 to 10"],
        "number": ["a whole number"],
        "duration": ['{"n": <number>, "unit": "hours|days|weeks|months|years"}'],
        "text": ["the reply, copied word for word"],
    }.get(node.answer_type, [])

    user = (
        f"Question (English): {node.prompt.get('en')}\n"
        f"Question (Hindi): {node.prompt.get('hi')}\n"
        f"Answer type: {node.answer_type}\n"
        f"Permitted answers: {permitted}\n"
        f"{'This field accepts a LIST of permitted answers.' if node.answer_type == 'multi_choice' else ''}\n"
        f"Patient said: {text!r}"
    )

    parsed, provider = llm.chat_json(
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]
    )
    if not parsed or "value" not in parsed:
        return NLUResult(None, 0.0, provider)

    value = parsed["value"]
    confidence = float(parsed.get("confidence") or 0.0)

    if value == UNCLEAR:
        return NLUResult(None, 0.0, provider)

    # THE GUARDRAIL. Anything the model returns that is not a declared option is
    # discarded, not stored. This is the line that makes invented history impossible.
    legal = {str(o.value) for o in node.options}
    if legal:
        if node.answer_type == "multi_choice":
            values = value if isinstance(value, list) else [value]
            kept = [v for v in values if str(v) in legal]
            if not kept:
                return NLUResult(None, 0.0, provider)
            return NLUResult(kept, confidence, provider)
        if str(value) not in legal:
            return NLUResult(None, 0.0, provider)
        if node.answer_type == "boolean":
            value = str(value).lower() in {"true", "yes", "1"}
        return NLUResult(value, confidence, provider)

    if node.answer_type == "scale":
        try:
            lo = node.min if node.min is not None else 0
            hi = node.max if node.max is not None else 10
            return NLUResult(max(lo, min(hi, int(value))), confidence, provider)
        except (TypeError, ValueError):
            return NLUResult(None, 0.0, provider)

    if node.answer_type == "duration":
        if isinstance(value, dict) and "n" in value and value.get("unit") in DURATION_UNITS:
            return NLUResult({"n": int(value["n"]), "unit": value["unit"]}, confidence, provider)
        return NLUResult(None, 0.0, provider)

    return NLUResult(value, confidence, provider)


# --------------------------------------------------------------------- public


CONFIDENCE_FLOOR = 0.5


def extract(node: Node, text: str, *, use_llm: bool = True) -> NLUResult:
    """Map an utterance onto this node's slot. Never raises, never invents."""
    hit = keyword_extract(node, text)
    if hit.ok and hit.confidence >= CONFIDENCE_FLOOR:
        return hit

    if use_llm and node.answer_type != "text":
        llm_hit = _llm_extract(node, text)
        if llm_hit.ok and llm_hit.confidence >= CONFIDENCE_FLOOR:
            return llm_hit

    return hit if hit.ok else NLUResult(None, 0.0, "none")
