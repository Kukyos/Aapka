"""Unit tests for the invariants that must never break.

The eval harness covers behaviour across whole interviews. These cover the specific
promises the documentation makes, so that breaking one is a red test rather than a
paragraph that quietly stopped being true.

    pytest server/tests -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aapka import config, documents, engine as eng, fhir, nlu, summary  # noqa: E402
from aapka import session as store  # noqa: E402
from aapka.ontology import OntologyError, evaluate_guard, load  # noqa: E402
from aapka.redflags import evaluate  # noqa: E402


@pytest.fixture(scope="module")
def ont():
    return load()


# --------------------------------------------------------------------- ontology


def test_ontology_loads_and_validates(ont):
    """Validation runs inside load(). Getting here means the graph is coherent."""
    assert ont.nodes and ont.slots and ont.red_flags


def test_every_node_has_both_languages(ont):
    """Gate G2 — every question must be speakable in every supported language."""
    for node in ont.nodes:
        assert node.prompt.get("en"), node.id
        assert node.prompt.get("hi"), node.id
        for option in node.options:
            assert option.label.get("en"), f"{node.id}:{option.value}"
            assert option.label.get("hi"), f"{node.id}:{option.value}"


def test_every_option_has_an_icon(ont):
    """Gate G2 again, from the touch side: a patient who cannot read needs a picture
    on every option, not most of them."""
    missing = [
        f"{n.id}:{o.value}"
        for n in ont.nodes
        for o in n.options
        if not o.icon
    ]
    assert not missing, missing


def test_all_ten_dashavidha_parameters_exist(ont):
    """Gate G5. The brief names all ten; all ten must be capturable."""
    named = {
        "Prakriti", "Vikriti", "Sara", "Samhanana", "Pramana",
        "Satmya", "Sattva", "Ahara Shakti", "Vyayama Shakti", "Vaya",
    }
    present = {s.dashavidha for s in ont.slots.values() if s.dashavidha}
    assert present == named, named - present


def test_socrates_dimensions_all_present(ont):
    """The brief names SOCRATES explicitly."""
    letters = {s.socrates for s in ont.slots.values() if s.socrates}
    assert letters == set("SOCRATES".replace("S", "S")) | {"S", "O", "C", "R", "A", "T", "E"}


def test_guards_reject_unknown_operators():
    with pytest.raises(OntologyError):
        evaluate_guard({"slot": "x", "wat": 1}, {})


def test_guards_are_false_on_unset_slots():
    """A red flag must not fire on an empty session."""
    assert evaluate_guard({"slot": "cc.primary", "eq": "chest_pain"}, {}) is False
    assert evaluate_guard({"slot": "hpi.severity", "gte": 8}, {}) is False


def test_no_eval_anywhere_in_the_loader():
    """Guards are data. If this ever fails, someone has made the ontology executable."""
    source = (Path(__file__).resolve().parents[1] / "aapka" / "ontology.py").read_text(encoding="utf-8")
    assert "eval(" not in source
    assert "exec(" not in source


# --------------------------------------------------------------------- engine


def _answer(ont, session, slot, value):
    node = next(n for n in ont.nodes if n.slot == slot)
    eng.apply_answer(ont, session, eng.Answer(node.id, slot, value, "self", "touch", node.cost_s))


def test_engine_is_deterministic(ont):
    """Same input, same questions, same order — the claim the whole architecture rests on."""
    script = {"identity.respondent": "self", "identity.age_band": "40_59",
              "identity.sex": "male", "cc.primary": "headache", "hpi.onset": "gradual",
              "hpi.severity": 4, "hpi.associated": ["none"], "ros.danger_signs": ["none"],
              "past.conditions": ["none"]}
    runs = []
    for _ in range(3):
        session = eng.Session(id="d", mode="ayush")
        eng.run_scripted(ont, session, script)
        runs.append(tuple(session.asked))
    assert len(set(runs)) == 1


def test_red_flag_stops_the_interview(ont):
    """Gate G4 — escalation is not a note in a summary."""
    session = eng.Session(id="rf", mode="ayush")
    _answer(ont, session, "identity.respondent", "self")
    _answer(ont, session, "identity.age_band", "40_59")
    _answer(ont, session, "identity.sex", "male")
    _answer(ont, session, "cc.primary", "chest_pain")
    _answer(ont, session, "hpi.associated", ["breathlessness"])
    action = eng.next_action(ont, session)
    assert action["action"] == "escalate"
    assert action["question"] is None
    assert session.status == "escalated"


def test_red_flags_are_checked_after_every_answer(ont):
    """Not at the end. An escalation that arrives with the summary is not an escalation."""
    session = eng.Session(id="rf2", mode="ayush")
    _answer(ont, session, "identity.respondent", "self")
    _answer(ont, session, "identity.age_band", "75_plus")
    _answer(ont, session, "identity.sex", "female")
    _answer(ont, session, "cc.primary", "chest_pain")
    assert evaluate(ont, session.slots) is not None
    assert eng.next_action(ont, session)["action"] == "escalate"


def test_red_flags_never_downgrade(ont):
    """No rule anywhere may lower a patient's urgency."""
    for rule in ont.red_flags:
        assert rule.severity in {"immediate", "urgent"}


def test_red_flag_instructions_name_no_disease(ont):
    """Hard rule 1. Every instruction tells a human what to DO."""
    banned = ["infarct", "attack", "stroke", "cancer", "embolism", "haemorrhage",
              "appendicitis", "sepsis"]
    for rule in ont.red_flags:
        for text in rule.instruction.values():
            lowered = text.lower()
            assert not any(word in lowered for word in banned), rule.id


def test_required_nodes_survive_the_budget(ont):
    """Hard rule 8's other half: displacement never reaches a required question."""
    session = eng.Session(id="b", mode="ayush", budget_override_s=45)
    script = {"identity.respondent": "self", "identity.age_band": "40_59",
              "identity.sex": "male", "cc.primary": "fever", "hpi.onset": "sudden",
              "hpi.duration": {"n": 1, "unit": "days"}, "hpi.associated": ["none"],
              "hpi.severity": 4, "ros.danger_signs": ["none"], "past.conditions": ["none"],
              "drugs.allergy_known": "none", "drugs.taking_now": False,
              "docs.has_papers": False, "ayush.ahara_shakti": "good_intake_good_digestion"}
    eng.run_scripted(ont, session, script)
    required = [n for n in ont.nodes
                if n.required and n.mode in eng.modes_enabled(session)
                and evaluate_guard(n.ask_if, session.slots)]
    for node in required:
        assert node.slot in session.slots, f"{node.id} was displaced by the budget"


def test_budget_actually_truncates(ont):
    """The other direction: a tiny budget must produce a short interview."""
    short = eng.Session(id="s", mode="ayush", budget_override_s=60)
    long = eng.Session(id="l", mode="ayush", budget_override_s=600)
    script = {s.id: (["none"] if s.type == "multi_choice" else
                     (5 if s.type == "scale" else
                      ({"n": 1, "unit": "days"} if s.type == "duration" else
                       (False if s.type == "boolean" else
                        ("x" if s.type == "text" else (s.values[0] if s.values else None))))))
              for s in ont.slots.values()}
    script.update({"identity.age_band": "40_59", "cc.primary": "fever",
                   "hpi.severity": 3, "ros.danger_signs": ["none"],
                   "past.conditions": ["none"]})
    eng.run_scripted(ont, short, script)
    eng.run_scripted(ont, long, script)
    assert len(short.asked) < len(long.asked)


def test_option_guards_gate_by_sex(ont):
    """A male patient is never offered a menstrual option."""
    node = next(n for n in ont.nodes if n.id == "cc.primary")
    male = eng.visible_options(node, {"identity.sex": "male"})
    female = eng.visible_options(node, {"identity.sex": "female"})
    assert "menstrual_problem" not in [o["value"] for o in male]
    assert "menstrual_problem" in [o["value"] for o in female]


def test_derivation_respects_mode(ont):
    """A core-mode interview must not quietly acquire AYUSH slots."""
    session = eng.Session(id="c", mode="core")
    _answer(ont, session, "identity.age_band", "75_plus")
    assert "ayush.vaya" not in session.slots
    session2 = eng.Session(id="a", mode="ayush")
    _answer(ont, session2, "identity.age_band", "75_plus")
    assert session2.slots["ayush.vaya"] == "vriddha"


def test_derivation_avoids_asking_twice(ont):
    """Koshtha comes from the bowel question. Nobody is asked about their bowels twice."""
    session = eng.Session(id="k", mode="ayush")
    _answer(ont, session, "personal.bowel", "constipated")
    assert session.slots["ayush.koshtha"] == "krura"
    assert "ayush.koshtha" not in [n.id for n in eng.candidates(ont, session)]


def test_audit_records_a_reason_for_every_question(ont):
    session = eng.Session(id="au", mode="ayush")
    eng.run_scripted(ont, session, {"identity.respondent": "self",
                                    "identity.age_band": "40_59",
                                    "identity.sex": "male", "cc.primary": "cough"})
    audited = {a["node"] for a in session.audit if a.get("node")}
    for node_id in session.asked:
        assert node_id in audited, node_id


# --------------------------------------------------------------------- NLU


def test_nlu_never_returns_an_undeclared_value(ont):
    """The anti-hallucination invariant, asserted directly."""
    node = ont.node("cc.primary")
    legal = {str(o.value) for o in node.options}
    for utterance in ["pet mein dard", "chest pain", "asdfgh qwerty",
                      "मुझे सिर दर्द है", "", "banana spaceship"]:
        result = nlu.extract(node, utterance, use_llm=False)
        if result.ok:
            assert str(result.value) in legal, (utterance, result.value)


def test_nlu_says_unclear_rather_than_guessing(ont):
    node = ont.node("cc.primary")
    result = nlu.extract(node, "hmm woh kya kehte hain", use_llm=False)
    assert not result.ok


def test_nlu_handles_devanagari_and_romanised(ont):
    node = ont.node("cc.primary")
    assert nlu.extract(node, "मुझे सिर दर्द है", use_llm=False).value == "headache"
    assert nlu.extract(node, "sar dard ho raha hai", use_llm=False).value == "headache"


def test_nlu_number_words_are_not_articles(ont):
    """'maybe a seven' is seven, not one."""
    node = ont.node("hpi.severity")
    assert nlu.extract(node, "maybe a seven", use_llm=False).value == 7


# --------------------------------------------------------------------- documents


def test_document_reference_range_beats_the_table():
    text = "Haemoglobin 9.8 g/dL (11.0 - 16.0)"
    lab = documents.extract_labs(text)[0]
    assert lab.ref_source == "document"
    assert (lab.ref_low, lab.ref_high) == (11.0, 16.0)


def test_abnormal_values_are_flagged():
    labs = documents.extract_labs("Fasting Blood Sugar 142 mg/dL (70 - 100)")
    assert labs[0].abnormal == "high"


def test_future_dates_are_rejected():
    """A misread year would sort to the top of the timeline."""
    assert documents.extract_date("Date: 12/05/2099") is None


def test_ayush_allopathic_interaction_is_screened():
    hits = documents.check_interactions(["Tab Metformin 500", "Giloy ghanvati"])
    assert hits and "screening only" in hits[0]["scope"]


def test_undated_documents_are_kept_not_dropped():
    docs = [documents.Document("a", "prescription", None, "x"),
            documents.Document("b", "prescription", "2026-01-01", "y")]
    timeline = documents.build_timeline(docs)
    assert len(timeline["documents"]) == 2
    assert timeline["undated_count"] == 1


# --------------------------------------------------------------------- summary


def test_summary_contains_no_diagnosis_language(ont):
    """Hard rule 1, asserted on the actual output."""
    session = eng.Session(id="s", mode="ayush")
    eng.run_scripted(ont, session, {
        "identity.respondent": "self", "identity.age_band": "60_74",
        "identity.sex": "female", "cc.primary": "abdominal_pain",
        "hpi.character": "burning", "hpi.onset": "gradual", "hpi.severity": 6,
        "hpi.associated": ["nausea"], "ros.danger_signs": ["none"],
        "past.conditions": ["diabetes"], "drugs.allergy_known": "none"})
    built = summary.build(ont, session, None, use_llm=False)
    blob = json.dumps(built["sections"], ensure_ascii=False).lower()
    for word in ["diagnosis", "differential", "suggestive of", "rule out",
                 "consistent with", "impression:"]:
        assert word not in blob, word


def test_summary_sections_follow_the_briefs_order(ont):
    session = eng.Session(id="o", mode="ayush")
    eng.run_scripted(ont, session, {"identity.respondent": "self",
                                    "identity.age_band": "40_59",
                                    "identity.sex": "male", "cc.primary": "fever"})
    keys = [s["key"] for s in summary.build(ont, session, None, use_llm=False)["sections"]]
    expected = ["cc", "hpi", "past", "drugs", "family", "personal", "ros"]
    assert keys[: len(expected)] == expected


def test_proxy_history_is_marked(ont):
    """Requirement R1."""
    session = eng.Session(id="p", mode="ayush")
    eng.run_scripted(ont, session, {"identity.respondent": "relative",
                                    "identity.age_band": "75_plus",
                                    "identity.sex": "female", "cc.primary": "fever"})
    assert summary.build(ont, session, None, use_llm=False)["proxy_note"]


def test_prakriti_is_never_called_a_determination(ont):
    """docs/10-unsourced.md item 4 — it is a screen, and must say so."""
    session = eng.Session(id="pk", mode="ayush")
    eng.run_scripted(ont, session, {
        "identity.respondent": "self", "identity.age_band": "40_59",
        "identity.sex": "male", "cc.primary": "fever",
        "ayush.prakriti_screen": ["vata_light_sleep"]})
    built = summary.build(ont, session, None, use_llm=False)
    ayush = next(s for s in built["sections"] if s["key"] == "ayush")
    assert "abbreviated" in (ayush["note"] or "").lower()
    assert "not the CCRAS" in (ayush["note"] or "") or "not the ccras" in (ayush["note"] or "").lower()


def test_hpi_rewrite_rejects_invented_content():
    """The guard on the one place a model touches the summary."""
    assert summary._no_new_symptoms("Burning epigastric pain for three weeks.", "burning pain")
    assert not summary._no_new_symptoms(
        "Burning pain radiating to the left arm.", "burning pain")


# --------------------------------------------------------------------- FHIR


def _built_session(ont):
    session = eng.Session(id="fh", mode="ayush")
    eng.run_scripted(ont, session, {
        "identity.respondent": "self", "identity.age_band": "60_74",
        "identity.sex": "female", "cc.primary": "abdominal_pain",
        "hpi.onset": "gradual", "hpi.severity": 5, "hpi.associated": ["nausea"],
        "ros.danger_signs": ["none"], "past.conditions": ["diabetes"],
        "drugs.allergy_known": "drug_allergy", "drugs.allergy_detail": "penicillin rash"})
    return session


def test_fhir_bundle_is_structurally_valid(ont):
    session = _built_session(ont)
    built = summary.build(ont, session, None, use_llm=False)
    bundle = fhir.build_bundle(ont, session, built, None, "12-3456-7890-1234")
    assert fhir.validate(bundle) == []


def test_fhir_first_entry_is_a_composition(ont):
    session = _built_session(ont)
    built = summary.build(ont, session, None, use_llm=False)
    bundle = fhir.build_bundle(ont, session, built, None)
    assert bundle["entry"][0]["resource"]["resourceType"] == "Composition"
    assert bundle["type"] == "document"


def test_fhir_emits_no_unsourced_codes(ont):
    """docs/10-unsourced.md, enforced: a code we did not verify never leaves here."""
    session = _built_session(ont)
    built = summary.build(ont, session, None, use_llm=False)
    bundle = fhir.build_bundle(ont, session, built, None)
    blob = json.dumps(bundle)
    for system in (fhir.SYS_NAMASTE, fhir.SYS_ICD11_MMS, fhir.SYS_ICD11_TM2):
        for coding in fhir._all_codings(bundle):
            if coding.get("system") == system:
                assert coding.get("code"), "unsourced code emitted"
    assert "PLACEHOLDER" not in blob


def test_fhir_marks_patient_reported_conditions_unconfirmed(ont):
    """A kiosk cannot confirm a diagnosis, and FHIR has a field that says so."""
    session = _built_session(ont)
    built = summary.build(ont, session, None, use_llm=False)
    bundle = fhir.build_bundle(ont, session, built, None)
    conditions = [e["resource"] for e in bundle["entry"]
                  if e["resource"]["resourceType"] == "Condition"]
    assert conditions
    for condition in conditions:
        assert condition["verificationStatus"]["coding"][0]["code"] == "unconfirmed"


def test_codes_file_invariant_holds(ont):
    """Anything marked `sourced` must have a value, and vice versa. You cannot
    quietly promote a guess."""
    for group in ("complaints", "dosha_findings"):
        for name, entry in (ont.codes.get(group) or {}).items():
            for key in ("namaste", "icd11_tm2", "icd11_mms"):
                spec = entry.get(key)
                if not spec:
                    continue
                sourced = spec.get("provenance") == "sourced"
                has_code = bool(spec.get("code"))
                assert sourced == has_code, f"{group}.{name}.{key}"


# --------------------------------------------------------------------- privacy


def test_session_wipe_destroys_everything(tmp_path, monkeypatch, ont):
    """The brief requires it and DPDP 2023 backs it. This test failing is a
    compliance failure, not a unit-test failure."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    store.init_db()

    session = store.create("hi", "ayush")
    eng.run_scripted(ont, session, {
        "identity.respondent": "self", "identity.age_band": "40_59",
        "identity.sex": "male", "cc.primary": "fever",
        "cc.narration": "bahut bukhar hai teen din se"})
    store.save(session)
    store.add_document(session.id, "doc1", b"\x89PNG-fake-image-bytes",
                       "Tab Paracetamol 500", {"id": "doc1", "kind": "prescription",
                                               "doc_date": None, "medications": []})

    assert store.exists(session.id)
    assert store.documents_for(session.id)

    store.submit(session, "bundles/x.json", {"sections": {}})

    assert not store.exists(session.id), "session row survived submission"
    assert not store.documents_for(session.id), "scanned document survived submission"

    with store.connect() as conn:
        row = conn.execute("SELECT * FROM audit_log WHERE id=?", (session.id,)).fetchone()
        assert row is not None, "audit line should survive"
        blob = json.dumps(dict(row))
        # The audit line must carry nothing personal.
        assert "bukhar" not in blob
        assert "Paracetamol" not in blob
        assert "fever" not in blob


def test_abandoned_session_leaves_no_audit_line(tmp_path, monkeypatch):
    """Requirement R2 — a half-finished history is worse than none."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t2.db")
    store.init_db()
    session = store.create("hi", "ayush")
    store.wipe(session.id)
    assert not store.exists(session.id)
    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(*) c FROM audit_log").fetchone()["c"] == 0


def test_stale_sessions_are_reaped(tmp_path, monkeypatch):
    """Requirement R3 — the terminal must never show the previous stranger's answers."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t3.db")
    store.init_db()
    session = store.create("hi", "ayush")
    with store.connect() as conn:
        conn.execute("UPDATE sessions SET updated_at = 0 WHERE id = ?", (session.id,))
    assert store.expire_stale(90) == 1
    assert not store.exists(session.id)
