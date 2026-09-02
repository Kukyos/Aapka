"""Budget sweep — what fits in the interview, at each budget.

Produces the table in `docs/12-budget-findings.md`. Rerun it after any change to the
ontology, because adding a question changes what gets displaced and therefore changes
the terminal count a hospital has to buy.

    python -m eval.budget_sweep
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aapka import engine as eng  # noqa: E402
from aapka.ontology import load  # noqa: E402

# 04-targets.md: a ~6 hour OPD window.
OPD_MINUTES = 360
HOSPITAL_LOAD = 5000


def full_script(ont) -> dict:
    """A patient who answers everything. The upper bound on what the graph can ask."""
    script = {}
    for slot in ont.slots.values():
        if slot.type == "multi_choice":
            script[slot.id] = [slot.values[0]] if slot.values else ["none"]
        elif slot.type == "scale":
            script[slot.id] = 5
        elif slot.type == "duration":
            script[slot.id] = {"n": 3, "unit": "weeks"}
        elif slot.type == "boolean":
            script[slot.id] = False
        elif slot.type == "text":
            script[slot.id] = "x"
        elif slot.values:
            script[slot.id] = slot.values[0]
    script.update({
        "identity.respondent": "self", "identity.age_band": "60_74",
        "identity.sex": "female", "cc.primary": "abdominal_pain",
        "hpi.severity": 5, "ros.danger_signs": ["none"], "past.conditions": ["none"],
        "personal.bowel": "constipated", "drugs.taking_now": False,
        "drugs.allergy_known": "none",
    })
    return script


def main() -> int:
    ont = load()
    script = full_script(ont)

    total = sum(n.cost_s for n in ont.nodes)
    print(f"\nOntology: {len(ont.nodes)} nodes, {len(ont.slots)} slots, "
          f"{len(ont.red_flags)} red-flag rules")
    print(f"Cost if every node were asked: {total} s ({total/60:.1f} min)\n")

    header = (f"{'budget':>8} {'asked':>6} {'actual':>8} {'SOCRATES':>9} "
              f"{'Dashavidha':>11} {'per day':>8} {'terminals':>10}")
    print(header)
    print("-" * len(header))

    for budget in (180, 240, 300, 360, 420, 480, 560):
        session = eng.Session(id="sweep", mode="ayush", budget_override_s=budget)
        eng.run_scripted(ont, session, script)
        cov = eng.coverage(ont, session)
        per_day = int(OPD_MINUTES * 60 / max(session.elapsed_s, 1))
        terminals = -(-HOSPITAL_LOAD // per_day)
        print(f"{budget:>7}s {len(session.asked):>6} {session.elapsed_s:>7.0f}s "
              f"{cov['socrates']['text']:>9} {cov['dashavidha']['text']:>11} "
              f"{per_day:>8} {terminals:>10}")

    print("\nReturning-patient offset (04-targets.md calls this an economic necessity):")
    for repeat_rate in (0.0, 0.2, 0.4, 0.6):
        mean = (1 - repeat_rate) * 360 + repeat_rate * eng.BUDGET_RETURNING_S
        per_day = int(OPD_MINUTES * 60 / mean)
        print(f"  {int(repeat_rate*100):>3}% returning -> mean {mean:>5.0f}s, "
              f"{per_day:>3}/terminal/day, {-(-HOSPITAL_LOAD//per_day):>3} terminals")

    print("\nNote: question COUNT is measured exactly; question DURATION is modelled "
          "from cost_s estimates (docs/11-deferred.md D-09).\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
