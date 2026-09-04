"""Pull ICD-11 codes from the WHO API into a local cache.

    python -m tools.fetch_icd11              # TM2 traditional medicine, the default
    python -m tools.fetch_icd11 --tm1        # TM1, for comparison only — see below
    python -m tools.fetch_icd11 --search "abdominal pain"   # MMS biomedical lookup

Why this exists rather than a downloaded file: `docs/10-unsourced.md` records that the
freely downloadable Chapter 26 PDF is **TM1 — East Asian medicine**. Its codes are real
and verifiable and they are the wrong ones: putting a TCM pattern code on an Ayurveda
intake would be a factual error dressed up as diligence. TM2 — Ayurveda, Siddha and
Unani — is only reachable through the authenticated API, which is what this fetches.

Needs ICD11_CLIENT_ID and ICD11_CLIENT_SECRET in `.env`. Free, application-based, at
https://icd.who.int/icdapi. Note the two hosts: tokens come from
icdaccessmanagement.who.int, the classification itself is id.who.int.

Output is written to `ontology/cache/icd11-<linearization>-<release>.json` and is the
source `ontology/codes.yaml` is filled from — never edited by hand, and re-runnable when
WHO publishes a new release.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aapka import config  # noqa: E402
from aapka.llm import USER_AGENT  # noqa: E402

RELEASE = "2025-01"
CHAPTER_26 = "718687701"          # Supplementary Chapter Traditional Medicine Conditions
MODULE_I = "353229912"            # TM1 — East Asian medicine. Not ours.
MODULE_II = "562274788"           # TM2 — Ayurveda, Siddha, Unani. Ours.

OUT_DIR = Path(__file__).resolve().parents[2] / "ontology" / "cache"


def token() -> str:
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": config.ICD11_CLIENT_ID,
        "client_secret": config.ICD11_CLIENT_SECRET,
        "scope": "icdapi_access",
    }).encode()
    req = urllib.request.Request(
        config.ICD11_TOKEN_URL, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["access_token"]


class Api:
    """Thin GET wrapper with a memo, because the tree revisits nodes."""

    def __init__(self, bearer: str) -> None:
        self.bearer = bearer
        self.seen: dict[str, dict] = {}
        self.calls = 0

    def get(self, url: str) -> dict:
        if url in self.seen:
            return self.seen[url]
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self.bearer}",
            "Accept": "application/json",
            "Accept-Language": "en",
            "API-Version": "v2",
            "User-Agent": USER_AGENT,
        })
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.load(resp)
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 503) and attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise
        self.seen[url] = data
        self.calls += 1
        return data


def walk(api: Api, url: str, depth: int = 0, parent: str | None = None) -> list[dict]:
    """Flatten an ICD-11 subtree into rows.

    Every row carries the URI it came from. That is the provenance: a code in
    `codes.yaml` marked `sourced` can be traced back to the exact WHO entity that
    produced it, which is the whole point of not typing these in by hand.
    """
    node = api.get(url)
    title = (node.get("title") or {}).get("@value", "")
    rows = [{
        "uri": url,
        "code": node.get("code"),
        "title": title,
        "definition": (node.get("definition") or {}).get("@value"),
        "class_kind": node.get("classKind"),
        "depth": depth,
        "parent": parent,
        "index_terms": [t.get("label", {}).get("@value") for t in node.get("indexTerm", [])],
    }]
    for child in node.get("child", []):
        rows.extend(walk(api, child, depth + 1, title))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tm1", action="store_true",
                        help="fetch TM1 (East Asian) instead — for comparison, not for use")
    parser.add_argument("--search", metavar="TERM",
                        help="search the MMS biomedical linearization instead")
    args = parser.parse_args()

    if not (config.ICD11_CLIENT_ID and config.ICD11_CLIENT_SECRET):
        print("No ICD-11 credentials. Put ICD11_CLIENT_ID and ICD11_CLIENT_SECRET in .env.")
        print("Free, application-based, at https://icd.who.int/icdapi")
        return 1

    api = Api(token())
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.search:
        url = (f"{config.ICD11_BASE_URL}/icd/release/11/{RELEASE}/mms/search?"
               + urllib.parse.urlencode({"q": args.search, "flatResults": "true"}))
        found = api.get(url)
        for entity in (found.get("destinationEntities") or [])[:12]:
            code = entity.get("theCode") or "—"
            label = entity.get("title", "").replace("<em class='found'>", "").replace("</em>", "")
            print(f"  {code:>10}  {label}")
        return 0

    module = MODULE_I if args.tm1 else MODULE_II
    name = "tm1" if args.tm1 else "tm2"
    base = f"{config.ICD11_BASE_URL}/icd/release/11/{RELEASE}/mms"
    rows = walk(api, f"{base}/{module}")

    out = OUT_DIR / f"icd11-{name}-{RELEASE}.json"
    out.write_text(json.dumps({
        "linearization": "mms",
        "module": name.upper(),
        "release": RELEASE,
        "chapter": CHAPTER_26,
        "fetched_at": time.strftime("%Y-%m-%d"),
        "source": "WHO ICD-11 API, https://icd.who.int/icdapi",
        "entities": rows,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    coded = [r for r in rows if r["code"]]
    print(f"{name.upper()}  {len(rows)} entities, {len(coded)} with codes, "
          f"{api.calls} API calls")
    print(f"written to {out.relative_to(OUT_DIR.parents[1])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
