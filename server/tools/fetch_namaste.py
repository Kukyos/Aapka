"""Parse the NAMASTE morbidity code exports into a local cache.

    python -m tools.fetch_namaste

Reads the four official workbooks in `ontology/source/` and writes one JSON file per
code system to `ontology/cache/`. Nothing is edited by hand at any point; `codes.yaml`
is filled from the cache and every entry carries the row it came from.

    NAMC   National Ayurveda Morbidity Codes    2,910 terms
    NSMC   National Siddha Morbidity Codes      1,926 terms
    NUMC   National Unani Morbidity Codes       2,522 terms
    ICD-10 the NAMASTE ICD-10 mapping sheet    11,145 rows

## The thing that makes this worth a script

The NAMC export carries the **official NAMASTE to ICD-11 TM2 crosswalk**, and it hides
it in the code column: `AAA-1` is a NAMC code, but `SR11 (AAA-1)` is a NAMC code paired
with the WHO TM2 code it maps to. 807 of the 2,910 rows carry one.

Which token is which is not positional — `SR11 (AAA-1)` and `AAB-39(SP1Y)` put them in
opposite orders. So the WHO cache decides: a token that appears in
`icd11-tm2-2025-01.json` is the TM2 code and the other is the NAMC code. Run
`tools.fetch_icd11` first, or this refuses rather than guessing.

## Exact versus approximate, which the export tells us and we must not lose

Rows whose English name ends in a "rightwards double arrow" are the export's own marker
for an *approximate* mapping; rows without it are exact equivalences. It holds almost
perfectly across the 807:

    no arrow, label identical to WHO's own title    374
    arrow,    label differs                         428
    anomalies                                         5

So a mapped row is emitted with `equivalence: equivalent` or `equivalence: wider`, in
FHIR ConceptMap's vocabulary. Recording an approximate mapping as an exact one would
overstate what the ministry actually published, which is the same failure as inventing
a code, only quieter.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "ontology" / "source"
CACHE = ROOT / "ontology" / "cache"

ARROW = "⇒"
TOKEN = re.compile(r"[A-Za-z0-9.\-]+")

WORKBOOKS = {
    "namc": ("NATIONAL AYURVEDA MORBIDITY CODES.xls", "National Ayurveda Morbidity Codes"),
    "nsmc": ("NATIONAL SIDDHA MORBIDITY CODES.xls", "National Siddha Morbidity Codes"),
    "numc": ("NATIONAL UNANI MORBIDITY CODES.xls", "National Unani Morbidity Codes"),
    "icd10": ("NATIONAL ICD10 MORBIDITY CODES.xls", "NAMASTE ICD-10 mapping"),
}


def load_who_tm2() -> dict[str, str]:
    """The WHO TM2 codes, which are what let us tell the two code systems apart."""
    path = CACHE / "icd11-tm2-2025-01.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r["code"]: r["title"] for r in data["entities"] if r["code"]}


def read_sheet(path: Path) -> list[dict[str, str]]:
    import xlrd  # imported here so the rest of the server never needs it

    book = xlrd.open_workbook(str(path))
    sheet = book.sheet_by_index(0)
    header = [str(sheet.cell_value(0, c)).strip() for c in range(sheet.ncols)]
    return [
        {h: str(sheet.cell_value(r, i)).strip() for i, h in enumerate(header)}
        for r in range(1, sheet.nrows)
    ]


def split_codes(raw: str, who: dict[str, str]) -> tuple[str | None, str | None]:
    """Separate the NAMASTE code from the ICD-11 TM2 code it is paired with.

    Order is not reliable, so membership of the WHO list is the test rather than
    position. A token we cannot find in WHO is treated as the NAMASTE code.
    """
    tokens = TOKEN.findall(raw)
    tm2 = [t for t in tokens if t in who]
    own = [t for t in tokens if t not in who]
    return (own[0] if own else None), (tm2[0] if tm2 else None)


def main() -> int:
    if not SOURCE.exists():
        print(f"No source workbooks at {SOURCE}.")
        return 1
    try:
        import xlrd  # noqa: F401
    except ImportError:
        print("xlrd is needed to read .xls. pip install xlrd")
        return 1

    who = load_who_tm2()
    if not who:
        print("No WHO TM2 cache. Run `python -m tools.fetch_icd11` first — without it")
        print("there is no way to tell a NAMASTE code from an ICD-11 one, and guessing")
        print("would put the wrong system on half the entries.")
        return 1
    print(f"WHO TM2 reference: {len(who)} codes\n")

    CACHE.mkdir(parents=True, exist_ok=True)
    for key, (filename, title) in WORKBOOKS.items():
        path = SOURCE / filename
        if not path.exists():
            print(f"  {key}: missing {filename}, skipped")
            continue
        rows = read_sheet(path)
        code_col = next((c for c in rows[0] if c.upper().endswith("_CODE")), None)
        term_col = next((c for c in rows[0] if c.upper().endswith("_TERM")), None)

        out, mapped, exact, approx, anomalies = [], 0, 0, 0, 0
        for row in rows:
            raw = row.get(code_col, "")
            own, tm2 = split_codes(raw, who)
            english = row.get("Name English") or row.get(term_col) or ""
            approximate = ARROW in english
            english = english.replace(ARROW, "").strip()

            entry = {
                "code": own,
                "term": row.get(term_col) or row.get("NAMC_term") or "",
                "term_diacritical": row.get("NAMC_term_diacritical") or "",
                "devanagari": row.get("NAMC_term_DEVANAGARI") or "",
                "tamil": row.get("Tamil_term") or "",
                "arabic": row.get("Arabic_term") or "",
                "english": english,
                "short_definition": row.get("Short_definition") or "",
                "raw_code_field": raw,
            }
            if tm2:
                mapped += 1
                matches = english.lower() == who[tm2].lower()
                if approximate:
                    approx += 1
                else:
                    exact += 1
                if approximate == matches:
                    anomalies += 1
                entry["icd11_tm2"] = {
                    "code": tm2,
                    "who_title": who[tm2],
                    # FHIR ConceptMap vocabulary. `equivalent` means the two terms are
                    # the same concept; `wider` means NAMASTE's term sits inside a
                    # broader TM2 one. The export marks the second with an arrow.
                    "equivalence": "wider" if approximate else "equivalent",
                }
            out.append(entry)

        payload = {
            "system": key.upper(),
            "title": title,
            "source_file": filename,
            "source": "Ministry of Ayush NAMASTE portal export",
            "terms": len(out),
            "mapped_to_icd11_tm2": mapped,
            "exact_equivalences": exact,
            "approximate_mappings": approx,
            "entries": out,
        }
        dest = CACHE / f"namaste-{key}.json"
        dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        note = f", {anomalies} anomalies" if anomalies else ""
        print(f"  {key.upper():<6} {len(out):>6} terms   "
              f"{mapped:>4} mapped to TM2 ({exact} exact, {approx} approximate){note}")
        print(f"         -> {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
