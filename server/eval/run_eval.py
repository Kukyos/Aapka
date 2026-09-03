"""The eval harness.

`04-targets.md` says correctness here is invisible: a beautifully formatted summary can
be completely wrong and nothing on screen will tell you. So this runs before the
features it measures, and every number quoted anywhere about this system comes from
here.

Run it:
    python -m eval.run_eval              # text table
    python -m eval.run_eval --json       # machine readable
    python -m eval.run_eval --md         # writes docs/13-eval-results.md
    python -m eval.run_eval --llm        # also exercise the model rungs (needs network)

By default it runs **offline** — no network, no model. That is not a limitation, it is
the point: the numbers below are what the kiosk achieves when the hospital wifi is
down, which gate G1 says we must assume.

WHAT THIS DOES NOT MEASURE, and must not be quoted as measuring:
  - ASR word error rate. No hospital noise recordings exist yet (D-02).
  - OCR accuracy. No real handwritten prescriptions exist yet (D-01).
Both rows print as "pending real data" and will keep printing that until the data
exists. See docs/11-deferred.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aapka import engine as eng  # noqa: E402
from aapka import nlu, summary  # noqa: E402
from aapka.ontology import load  # noqa: E402
from aapka.redflags import evaluate_all  # noqa: E402
from eval.scenarios import SCENARIOS  # noqa: E402


class Result:
    def __init__(self, scenario: dict) -> None:
        self.id = scenario["id"]
        self.tags = scenario["tags"]
        self.checks: list[tuple[str, bool, str]] = []
        self.metrics: dict[str, Any] = {}

    def check(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append((name, bool(passed), detail))

    @property
    def passed(self) -> bool:
        return all(c[1] for c in self.checks)

    @property
    def failures(self) -> list[tuple[str, bool, str]]:
        return [c for c in self.checks if not c[1]]


def _run_interview(ont, scenario: dict, *, use_llm: bool) -> tuple[eng.Session, dict]:
    """Drive one scenario through the real engine, exactly as the kiosk does."""
    session = eng.Session(
        id=scenario["id"],
        language="hi",
        mode=scenario.get("mode", "ayush"),
        returning=scenario.get("returning", False),
    )
    # A returning patient arrives with facts already known. Seeding them through the
    # real `prefill` — not by writing into `slots` — is the point: the harness measures
    # the fast path the kiosk actually runs, including that carried answers cost no
    # interview time and that non-carry slots in the store are refused.
    prefilled: list[str] = []
    if scenario.get("prefill"):
        prefilled = eng.prefill(ont, session, scenario["prefill"])

    script = dict(scenario["script"])
    utterances = scenario.get("utterances", {})
    voice_stats = {"attempted": 0, "resolved": 0, "unclear": [], "wrong": []}
    abandon_after = scenario.get("abandon_after")

    steps = 0
    while True:
        action = eng.next_action(ont, session)
        if action["action"] != "ask":
            break
        steps += 1
        if abandon_after and steps >= abandon_after:
            session.status = "abandoned"
            break

        node = ont.node(action["question"]["id"])

        # Voice path where the scenario supplies an utterance. This exercises the same
        # nlu.extract the API calls, so a scenario passing here means the voice path
        # works, not that the test bypassed it.
        if node.slot in utterances:
            voice_stats["attempted"] += 1
            got = nlu.extract(node, utterances[node.slot], use_llm=use_llm)
            expected = script.get(node.slot)
            if got.ok:
                voice_stats["resolved"] += 1
                if expected is not None and got.value != expected:
                    voice_stats["wrong"].append((node.slot, got.value, expected))
                eng.apply_answer(ont, session, eng.Answer(
                    node.id, node.slot, got.value, session.respondent, "voice", node.cost_s,
                    utterances[node.slot]))
                continue
            voice_stats["unclear"].append(node.slot)

        if node.slot in script:
            eng.apply_answer(ont, session, eng.Answer(
                node.id, node.slot, script[node.slot], session.respondent, "touch", node.cost_s))
        elif node.skippable:
            eng.skip(ont, session, node.id)
        else:
            session.slots[node.slot] = None
            session.elapsed_s += node.cost_s
            session.audit.append({"node": node.id, "why": "no scripted answer", "answered": None})

    for slot, value in scenario.get("corrections", []):
        node = next((n for n in ont.nodes if n.slot == slot), None)
        if node:
            session.slots[slot] = value

    return session, voice_stats


def _score(ont, scenario: dict, session: eng.Session, voice: dict, *, use_llm: bool) -> Result:
    result = Result(scenario)
    expect = scenario.get("expect", {})
    cov = eng.coverage(ont, session)
    fired = evaluate_all(ont, session.slots)

    result.metrics = {
        "questions_asked": len(session.asked),
        "elapsed_s": round(session.elapsed_s, 1),
        "budget_s": session.budget_s,
        "socrates": cov["socrates"]["text"],
        "dashavidha": cov["dashavidha"]["text"],
        "escalated": session.status == "escalated",
        "rules_fired": [r.id for r in fired],
        "voice_attempted": voice["attempted"],
        "voice_resolved": voice["resolved"],
    }

    if "escalates" in expect:
        result.check(
            "escalation",
            (session.status == "escalated") == expect["escalates"],
            f"expected escalates={expect['escalates']}, got {session.status}",
        )
    if "rule" in expect:
        result.check(
            "rule",
            expect["rule"] in [r.id for r in fired],
            f"expected {expect['rule']}, fired {[r.id for r in fired]}",
        )
    if "within_questions" in expect:
        result.check(
            "escalated in time",
            len(session.asked) <= expect["within_questions"],
            f"took {len(session.asked)} questions, limit {expect['within_questions']}",
        )
    if expect.get("proxy_marked"):
        built = summary.build(ont, session, None, use_llm=False)
        result.check("proxy marked", built["proxy_note"] is not None, "proxy_note missing")
    if expect.get("abandoned"):
        result.check("abandoned", session.status == "abandoned", session.status)
    if expect.get("forwarded") is False:
        result.check(
            "not forwarded",
            session.status != "complete",
            "an abandoned session must not present as complete",
        )
    if expect.get("alert_survives_abandonment"):
        result.check(
            "alert survives",
            session.red_flag is not None,
            "red flag lost when the patient walked away",
        )
    if "min_socrates" in expect:
        got = len(cov["socrates"]["captured"])
        result.check("socrates", got >= expect["min_socrates"], f"{got} < {expect['min_socrates']}")
    if "min_dashavidha" in expect:
        got = cov["dashavidha"]["captured"]
        result.check("dashavidha", got >= expect["min_dashavidha"],
                     f"{got} < {expect['min_dashavidha']}")
    if "max_dashavidha" in expect:
        got = cov["dashavidha"]["captured"]
        result.check("no ayush in core mode", got <= expect["max_dashavidha"], f"{got} captured")
    if "min_coverage" in expect:
        for section, floor in expect["min_coverage"].items():
            got = cov["sections"].get(section, {}).get("percent", 0)
            result.check(f"coverage {section}", got >= floor, f"{got}% < {floor}%")
    if "slot_equals" in expect:
        for slot, value in expect["slot_equals"].items():
            result.check(f"slot {slot}", session.slots.get(slot) == value,
                         f"got {session.slots.get(slot)!r}, expected {value!r}")
    if "node_not_asked" in expect:
        node_id = expect["node_not_asked"]
        result.check(f"{node_id} not asked", node_id not in session.asked, "it was asked")
    if "node_asked" in expect:
        node_id = expect["node_asked"]
        result.check(f"{node_id} asked", node_id in session.asked, "it was never asked")
    if expect.get("completes"):
        result.check("completes", session.status == "complete", session.status)
    if "max_elapsed_s" in expect:
        result.check("within budget", session.elapsed_s <= expect["max_elapsed_s"],
                     f"{session.elapsed_s:.0f}s > {expect['max_elapsed_s']}s")
    if "prefilled_min" in expect:
        carried = [a for a in session.answers if a.source == "prefilled"]
        result.check("carried from previous visit",
                     len(carried) >= expect["prefilled_min"],
                     f"carried {len(carried)}, wanted at least {expect['prefilled_min']}")
    if "never_carried" in expect:
        carried = {a.slot for a in session.answers if a.source == "prefilled"}
        leaked = [s for s in expect["never_carried"] if s in carried]
        result.check("this visit's facts not carried", not leaked, f"carried {leaked}")
    if expect.get("carried_not_reasked"):
        carried = {a.slot for a in session.answers if a.source == "prefilled"}
        reasked = [n for n in session.asked if ont.node(n).slot in carried]
        result.check("carried facts never asked again", not reasked,
                     f"re-asked {reasked}")
    if expect.get("required_all_asked"):
        enabled = eng.modes_enabled(session)
        required = [n for n in ont.nodes if n.required and n.mode in enabled]
        missed = [
            n.id for n in required
            if n.id not in session.asked
            and n.slot not in session.slots
            and eng._apply_derivations.__name__  # keep reference explicit
            and _guard_ok(ont, n, session)
        ]
        result.check("required never displaced", not missed, f"missed {missed}")
    if "voice_resolved_min" in expect:
        result.check("voice resolved", voice["resolved"] >= expect["voice_resolved_min"],
                     f"{voice['resolved']} of {voice['attempted']} resolved; "
                     f"unclear {voice['unclear']}")
        result.check("voice never wrong", not voice["wrong"],
                     f"mismapped {voice['wrong']}")
    if "voice_unclear" in expect:
        result.check(
            "unclear not guessed",
            all(s in voice["unclear"] for s in expect["voice_unclear"]),
            f"expected unclear for {expect['voice_unclear']}, got {voice['unclear']}",
        )
    if expect.get("audit_covers_asked"):
        audited = {a["node"] for a in session.audit if a.get("node")}
        missing = [n for n in session.asked if n not in audited]
        result.check("audit complete", not missing, f"no reason recorded for {missing}")
    if expect.get("deterministic"):
        again, _ = _run_interview(ont, scenario, use_llm=False)
        result.check("deterministic", again.asked == session.asked,
                     "question order differed between identical runs")
    if "dosha_summary_contains" in expect:
        built = summary.build(ont, session, None, use_llm=False)
        text = json.dumps(built, ensure_ascii=False)
        result.check("dosha in summary", expect["dosha_summary_contains"] in text,
                     "dosha finding missing from the summary")

    # Applies to every scenario, asserted every time: hard rule 1.
    built = summary.build(ont, session, None, use_llm=use_llm)
    banned = ["diagnosis", "likely ", "probably ", "differential", "impression:",
              "suggestive of", "consistent with", "rule out"]
    blob = json.dumps(built["sections"], ensure_ascii=False).lower()
    hits = [w for w in banned if w in blob]
    result.check("no diagnosis language", not hits, f"found {hits}")

    return result


def _guard_ok(ont, node, session) -> bool:
    from aapka.ontology import evaluate_guard

    return evaluate_guard(node.ask_if, session.slots)


def run(use_llm: bool = False) -> dict[str, Any]:
    ont = load()
    results = []
    for scenario in SCENARIOS:
        session, voice = _run_interview(ont, scenario, use_llm=use_llm)
        results.append(_score(ont, scenario, session, voice, use_llm=use_llm))

    by_tag: dict[str, list[Result]] = defaultdict(list)
    for result in results:
        for tag in result.tags:
            by_tag[tag].append(result)

    # Red-flag recall: of the scenarios that should escalate, how many did.
    should = [r for r in results if "red_flag" in r.tags and not r.id.startswith("rf-07")]
    escalated = [r for r in should if r.metrics["escalated"]]
    control = [r for r in results if r.id == "rf-07-known-epileptic-no-escalation"]

    voice_att = sum(r.metrics["voice_attempted"] for r in results)
    voice_res = sum(r.metrics["voice_resolved"] for r in results)

    return {
        "results": results,
        "totals": {
            "scenarios": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
        },
        "by_tag": {
            tag: {"total": len(rs), "passed": sum(1 for r in rs if r.passed)}
            for tag, rs in sorted(by_tag.items())
        },
        "red_flag_recall": {
            "expected": len(should),
            "caught": len(escalated),
            "recall": round(len(escalated) / len(should), 3) if should else None,
            "false_positive_control_passed": all(
                not r.metrics["escalated"] for r in control
            ),
        },
        "voice_offline": {
            "attempted": voice_att,
            "resolved": voice_res,
            "rate": round(voice_res / voice_att, 3) if voice_att else None,
            "note": "keyword rung only, no network, no model" if not use_llm else "with model",
        },
        "interview_length": {
            "mean_s": round(sum(r.metrics["elapsed_s"] for r in results) / len(results), 1),
            "max_s": max(r.metrics["elapsed_s"] for r in results),
            "mean_questions": round(
                sum(r.metrics["questions_asked"] for r in results) / len(results), 1
            ),
        },
        "not_measured": {
            "asr_wer": "pending real data — no hospital noise recordings (D-02)",
            "ocr_f1_handwritten": "pending real data — no handwritten prescriptions (D-01)",
            "ocr_f1_printed": "pending real data (D-01)",
        },
        "used_llm": use_llm,
    }


def print_table(report: dict) -> None:
    print()
    print("=" * 78)
    print("  AAPKA EVAL HARNESS" + ("  (with models)" if report["used_llm"] else "  (offline: no network, no model)"))
    print("=" * 78)
    print(f"{'scenario':38} {'Q':>3} {'time':>6} {'SOC':>5} {'DVP':>6}  result")
    print("-" * 78)
    for r in report["results"]:
        m = r.metrics
        mark = "pass" if r.passed else "FAIL"
        print(f"{r.id:38} {m['questions_asked']:>3} {m['elapsed_s']:>5.0f}s "
              f"{m['socrates']:>5} {m['dashavidha']:>6}  {mark}")
        for name, _, detail in r.failures:
            print(f"{'':38}      -> {name}: {detail}")
    print("-" * 78)

    t = report["totals"]
    print(f"\n  {t['passed']}/{t['scenarios']} scenarios passed"
          + (f"   ({t['failed']} FAILED)" if t["failed"] else ""))

    rf = report["red_flag_recall"]
    print(f"\n  Red-flag recall            {rf['caught']}/{rf['expected']}"
          f"  = {rf['recall']}")
    print(f"  False-positive control     {'pass' if rf['false_positive_control_passed'] else 'FAIL'}"
          "   (known epileptic must not escalate)")

    v = report["voice_offline"]
    print(f"\n  Voice mapped, {v['note']:32} {v['resolved']}/{v['attempted']} = {v['rate']}")

    il = report["interview_length"]
    print(f"\n  Interview length           mean {il['mean_s']}s, max {il['max_s']}s")
    print(f"  Questions asked            mean {il['mean_questions']}")

    print("\n  By category:")
    for tag, s in report["by_tag"].items():
        print(f"    {tag:22} {s['passed']}/{s['total']}")

    print("\n  NOT MEASURED — do not quote these anywhere:")
    for key, why in report["not_measured"].items():
        print(f"    {key:22} {why}")
    print()


def write_markdown(report: dict, path: Path) -> None:
    lines = [
        "# Eval results",
        "",
        "Generated by `python -m eval.run_eval --md`. Do not edit by hand — rerun it.",
        "",
        f"Mode: **{'with models' if report['used_llm'] else 'offline — no network, no model'}**. "
        "The offline run is the headline, because gate G1 says the network is not to be "
        "assumed and these are the numbers the kiosk achieves with the wifi down.",
        "",
        "## Headline",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Scenarios passed | {report['totals']['passed']} / {report['totals']['scenarios']} |",
        f"| Red-flag recall | {report['red_flag_recall']['caught']} / "
        f"{report['red_flag_recall']['expected']} = **{report['red_flag_recall']['recall']}** |",
        f"| False-positive control | "
        f"{'pass' if report['red_flag_recall']['false_positive_control_passed'] else 'FAIL'} |",
        f"| Voice utterances mapped offline | {report['voice_offline']['resolved']} / "
        f"{report['voice_offline']['attempted']} = {report['voice_offline']['rate']} |",
        f"| Mean interview length | {report['interview_length']['mean_s']} s |",
        f"| Mean questions asked | {report['interview_length']['mean_questions']} |",
        "",
        "## Not measured",
        "",
        "Stated explicitly because a missing number is honest and an invented one is not.",
        "",
        "| Metric | Status |",
        "|---|---|",
    ]
    for key, why in report["not_measured"].items():
        lines.append(f"| `{key}` | {why} |")

    lines += ["", "## By category", "", "| Category | Passed |", "|---|---|"]
    for tag, s in report["by_tag"].items():
        lines.append(f"| {tag} | {s['passed']} / {s['total']} |")

    lines += [
        "", "## Every scenario", "",
        "| Scenario | Questions | Time | SOCRATES | Dashavidha | Result |",
        "|---|---|---|---|---|---|",
    ]
    for r in report["results"]:
        m = r.metrics
        mark = "pass" if r.passed else "**FAIL**"
        lines.append(
            f"| `{r.id}` | {m['questions_asked']} | {m['elapsed_s']:.0f} s | "
            f"{m['socrates']} | {m['dashavidha']} | {mark} |"
        )

    failures = [r for r in report["results"] if not r.passed]
    if failures:
        lines += ["", "## Failures", ""]
        for r in failures:
            lines.append(f"**`{r.id}`**")
            for name, _, detail in r.failures:
                lines.append(f"- {name}: {detail}")
            lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--md", action="store_true")
    parser.add_argument("--llm", action="store_true", help="also exercise the model rungs")
    args = parser.parse_args()

    report = run(use_llm=args.llm)

    if args.json:
        print(json.dumps(
            {k: v for k, v in report.items() if k != "results"}
            | {"results": [{"id": r.id, "passed": r.passed, "metrics": r.metrics,
                            "failures": [(n, d) for n, _, d in r.failures]}
                           for r in report["results"]]},
            indent=2, ensure_ascii=False))
    else:
        print_table(report)

    if args.md:
        write_markdown(report, Path(__file__).resolve().parents[2] / "docs" / "13-eval-results.md")

    return 0 if report["totals"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
