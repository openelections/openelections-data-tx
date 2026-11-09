#!/usr/bin/env python3
"""Aggregate one county's precinct-level CSV and compare it to the county-level
baseline (2026/20260303__tx__primary__county.csv, from the SOS canvass).

Reports, per (office, district, party, candidate): precinct sum vs baseline,
and the difference. Local offices that don't exist in the baseline are listed
as 'baseline absent' (informational). Also validates each row's own breakdown
columns (absentee+early_voting+election_day+provisional+limited <= votes).

Usage:
  uv run python3 python-parsers/verify_2026.py <precinct.csv> [more.csv ...]
        [--json-report report.json]
"""

import argparse
import csv
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers_2026 import load_county_baseline, key_norm  # noqa: E402

BREAKDOWN_COLS = ["absentee", "early_voting", "election_day", "provisional",
                  "mail", "limited"]


def name_key(s):
    s = s.upper().replace('"', "").replace("'", "").replace("&", "AND")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def verify(precinct_paths, baseline, json_out=None):
    per_file = {}
    diffs = []
    for path in precinct_paths:
        sums = defaultdict(int)
        rows_bad = 0
        n_rows = 0
        precincts = set()
        offices = set()
        with open(path) as fh:
            reader = csv.DictReader(fh)
            headers = reader.fieldnames
            for r in reader:
                n_rows += 1
                precincts.add(r["precinct"])
                offices.add((r["office"], r["district"]))
                k = (
                    key_norm(r["office"], r["district"], r["party"], r["candidate"])
                )
                try:
                    v = int(float(str(r["votes"]).replace(",", "")))
                except ValueError:
                    print(f"  !! non-numeric votes: {r}")
                    continue
                sums[k] += v

                # row-level breakdown check
                comps = 0
                has = False
                for c in BREAKDOWN_COLS:
                    if c in headers:
                        try:
                            comps += int(float(r[c]))
                            has = True
                        except ValueError:
                            pass
                if has and comps > v:
                    rows_bad += 1

        county = None
        with open(path) as fh:
            first = next(csv.DictReader(fh))
            county = first["county"].upper()
        per_file[path] = {
            "rows": n_rows, "precincts": sorted(precincts), "offices": sorted(offices),
            "rows_breakdown_exceed_total": rows_bad,
        }

        # compare to baseline keys for this county
        base_keys = {k for k in baseline if k[0] == county}
        for k, v in sums.items():
            office, district, party, cand = k
            matched = None
            for bk in base_keys:
                if key_norm(bk[1], bk[2], bk[3], bk[4]) == k:
                    matched = baseline[bk]
                    break
            if matched is None:
                diffs.append((county, office, district, party, cand, v, None, "not in baseline"))
                continue
            if matched != v:
                diffs.append((county, office, district, party, cand, v, matched,
                              "match" if v == matched else "mismatch"))
        # baseline rows with no precinct coverage at all
        covered = set()
        for (c, office, district, party, cand) in base_keys:
            kk = key_norm(office, district, party, cand)
            covered.add(kk)
        for k in sums:
            covered.discard(k)
        for (c, office, district, party, cand) in sorted(base_keys):
            kk = key_norm(office, district, party, cand)
            if kk in covered:
                diffs.append((county, office, district, party, cand, None, baseline[
                    (c, office, district, party, cand)], "no precinct coverage"))

    return per_file, diffs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("precinct_csvs", nargs="+")
    ap.add_argument("--json-report")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args()
    baseline = load_county_baseline()
    per_file, diffs = verify(args.precinct_csvs, baseline)
    for path, info in per_file.items():
        if not args.quiet:
            print(f"== {os.path.basename(path)}: {info['rows']} rows, "
                  f"{len(info['precincts'])} precincts, {len(info['offices'])} offices, "
                  f"breakdown-exceeds rows={info['rows_breakdown_exceed_total']}")
            print(f"   precincts: {info['precincts']}")
    n_bad = sum(1 for d in diffs if d[7] == "not in baseline")
    n_mm = sum(1 for d in diffs if d[7] == "mismatch")
    print(f"\nBaseline candidates with no precinct coverage: {n_bad}")
    print(f"Value mismatches: {n_mm}")
    if not args.quiet:
        print("\nValue mismatches (office, district, party, candidate, precinct_sum, baseline):")
        for county, office, district, party, cand, v, m, tag in diffs:
            if tag == "mismatch":
                print(f"  [{county}] {office} | {district} | {party} | {cand}: "
                      f"precinct={v} county={m}")
        print("\nBaseline rows with no precinct coverage:")
        for county, office, district, party, cand, v, m, tag in diffs:
            if tag == "no precinct coverage":
                print(f"  [{county}] {office} | {district} | {party} | {cand}: county={m}")
    if args.json_report:
        import json
        with open(args.json_report, "w") as fh:
            json.dump({"files": per_file,
                       "diffs": [list(d) for d in diffs]}, fh, indent=1)
        print(f"\nWrote {args.json_report}")


if __name__ == "__main__":
    main()