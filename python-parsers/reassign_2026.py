#!/usr/bin/env python3
"""Fix mis-assigned candidate columns in 2026 primary precinct CSVs.

For each (county, office, district, party) race: if the multiset of
per-candidate precinct sums equals the baseline (SOS canvass) multiset but the
individual values differ, the names were shifted between columns (a common
artifact of 'box x box' reports). Rename columns 1:1 by vote total; ties
(equal vote totals) are left alone and reported.
"""

import csv
import sys
import os
import re
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers_2026 import load_county_baseline, key_norm  # noqa: E402


def main():
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        return
    baseline = load_county_baseline()
    for path in paths:
        with open(path) as fh:
            rows = list(csv.DictReader(fh))
            fieldnames = list(rows[0].keys()) if rows else []
        county = None
        for r in rows:
            if not county:
                county = r["county"].upper()
        base = {}
        for (c, office, district, party, cand), v in baseline.items():
            if c != county:
                continue
            base[(office, district, party, cand)] = v

        sums = defaultdict(int)
        for r in rows:
            sums[key_norm(r["office"], r["district"], r["party"], r["candidate"])] += \
                int(float(str(r["votes"]).replace(",", "") or 0))
        # races where sums' multiset matches but values differ
        our = defaultdict(dict)   # (office,dist,party) -> {cand: sum}
        bas = defaultdict(dict)
        for k, v in sums.items():
            our[k[:3]][k[3]] = v
        for (office, district, party, cand), v in base.items():
            bas[(office.upper(), district.upper(), party.upper())][cand.upper()] = v
        renames = {}
        for k, cands in our.items():
            b = bas.get(k)
            if not b:
                continue
            ours = sorted(cands.values(), key=lambda x: (x, -1))
            bas_l = sorted(b.values())
            if sorted(ours) != bas_l:
                continue
            # build value -> name mapping; ambiguous (repeated) values skipped
            v_by_sum = {}
            dup = set()
            for cand, s in cands.items():
                if s in v_by_sum:
                    dup.add(s)
                v_by_sum[s] = cand
            fixed = {}
            ok = True
            for cand, s in b.items():
                if s in dup:
                    ok = False
                    break
                if s in v_by_sum:
                    fixed[v_by_sum[s]] = cand
                else:
                    ok = False
                    break
            if ok:
                for c_old, c_new in fixed.items():
                    if c_old != c_new:
                        renames[(k, c_old)] = c_new
        # apply
        n = 0
        out = []
        for r in rows:
            k = key_norm(r["office"], r["district"], r["party"], r["candidate"])
            new = renames.get((k[:3], k[3]))
            if new:
                r = dict(r)
                r["candidate"] = new.title()
                n += 1
            out.append(r)
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
            w.writeheader()
            w.writerows(out)
        print(f"{os.path.basename(path)}: renamed {len(renames)} candidates "
              f"({n} rows)")


if __name__ == "__main__":
    main()
