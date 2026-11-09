#!/usr/bin/env python3
"""Reassign rows whose (office, district) is wrong for their candidate when
the candidate appears under a different office in other precincts and the
current precinct is missing under that office (OCR page-boundary carries in
the OCR'd 2026 primary sidecars: a race block that loses its closing rows
absorbs the next races' rows under the previous race's title).

Rewrites candidate-carry rows in place:
  for candidate c whose rows under office A sit only in precincts where c is
  absent under the office B (= c's majority office over other precincts), move
  those rows to B.

Also drops whole office keys that were pure carry-overs (empty after moves).

Usage:
  uv run python3 python-parsers/fixup_2026.py FILE.csv [FILE.csv ...]
"""

import csv
import os
import re
import sys
from collections import defaultdict


def name_norm(c):
    c = c.upper().replace('"', "").replace("'", "")
    c = c.replace(".", "").replace(" ", "")
    return c


def norm_name(s):
    import re as _re
    return _re.sub(r"[^A-Za-z0-9]", "", (s or "").upper())


def fix(path, sysmod=None):
    """Two passes, in order:
    1. cross-precinct move: rows sitting under office A whose candidate is
       under exactly one other office B (with more precinct coverage and the
       precinct missing under B) are carry-over rows -> move to B.
    2. baseline authority: for statewide candidates known to the SOS county
       canvass under exactly one office, move every row to that office
       (leaving local offices alone).
    """
    import re
    csv_mod = csv
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from helpers_2026 import load_county_baseline  # noqa: E402
    rows = list(csv_mod.DictReader(open(path)))
    if not rows:
        return 0
    fieldnames = list(rows[0].keys())
    county = rows[0][ "county"].upper()
    by_cand = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        by_cand[norm_name(r["candidate"])][(r["office"], r["district"])][r["precinct"]] = r["votes"]
    moved = 0
    # pass 1
    for r in rows:
        key = (r["office"], r["district"])
        others = {k: v for k, v in by_cand[norm_name(r["candidate"])].items()
                  if k != key}
        if len(others) == 1 and len(norm_name(r["candidate"])) > 3:
            key2, per_pr = list(others.items())[0]
            if r["precinct"] not in per_pr and len(per_pr) >= 2:
                r["office"], r["district"] = key2
                moved += 1
    # pass 2
    base = load_county_baseline()
    per_county = defaultdict(set)
    for (c4, office, dist, party, cand), votes in base.items():
        if c4 == county and votes:
            per_county[(party.upper(), norm_name(cand))].add((office, dist))
    auth = {k: list(v)[0] for k, v in per_county.items() if len(v) == 1}
    for r in rows:
        bo = auth.get((r["party"].upper(), norm_name(r["candidate"])))
        if bo and (r["office"], r["district"]) != bo and r["office"] not in (
                "Constable", "County Chair", "JP"):
            r["office"], r["district"] = bo
            moved += 1
    if moved:
        with open(path, "w", newline="") as fh:
            w = csv_mod.DictWriter(fh, fieldnames, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    return moved


def main():
    for path in sys.argv[1:]:
        n = fix(path)
        print(f"{path}: moved {n} rows")


if __name__ == "__main__":
    main()
