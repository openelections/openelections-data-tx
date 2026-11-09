#!/usr/bin/env python3
"""Aggregate duplicate (precinct, office, district, party, candidate) rows in a
2026 primary county CSV by summing their numeric components. Vote-center
counties (Brazos) report each voting location separately; the repository's data
tests require one row per (precinct, race, candidate)."""

import csv
import sys
import os
from collections import defaultdict

COMPONENTS = ("absentee", "early_voting", "election_day", "provisional", "limited")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    for path in sys.argv[1:]:
        with open(path) as fh:
            rows = list(csv.DictReader(fh))
            fieldnames = list(rows[0].keys()) if rows else []
        if not rows:
            continue

        def num(s):
            try:
                return int(float(str(s).replace(",", "") or 0))
            except ValueError:
                return 0
        groups = {}
        order = []
        for r in rows:
            k = (r["county"], r["precinct"], r["office"], r["district"],
                 (r["party"] or "").upper(), r["candidate"])
            g = groups.get(k)
            if g is None:
                groups[k] = {"votes": num(r["votes"]), **{c: num(r.get(c)) for c in COMPONENTS},
                             "proto": dict(r)}
                order.append(k)
            else:
                g["votes"] += num(r["votes"])
                for c in COMPONENTS:
                    g[c] += num(r.get(c))
        out = []
        for k in order:
            g = groups[k]
            proto = g["proto"]
            for c in COMPONENTS:
                if c in fieldnames:
                    proto[c] = str(g[c])
            proto["votes"] = str(g["votes"])
            out.append(proto)
        removed = len(rows) - len(out)
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
            w.writeheader()
            w.writerows(out)
        if removed:
            print(f"{os.path.basename(path)}: merged {removed} duplicate rows")


if __name__ == "__main__":
    main()