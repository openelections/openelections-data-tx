#!/usr/bin/env python3
"""Repair 2014 primary county precinct CSVs where a county's report truncated
the court-of-appeals / Supreme Court / Court of Criminal Appeals race titles,
losing the place number (e.g. San Jacinto's 'Judge, Court of Criminal Appeals,
Plac', Hidalgo's 'Justice, Supreme Court,').

Strategy: build a global candidate -> (office, place) map from the county
baseline across ALL counties (each candidate ran for exactly one statewide
place). For county rows whose office is one of the target families and whose
district is missing, look the candidate up and fill in the place.

Usage:
  uv run python3 python-parsers/repair_2014.py FILE.csv...
"""
import csv
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_2014 import name_key, load_baseline  # noqa: E402

BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir,
                        "2014", "20140304__tx__primary__county.csv")

TARGET_RE = re.compile(
    r"COURT OF CRIMINAL APPEALS|COURT OF APPEALS DISTRICT|SUPREME COURT|"
    r"STATE BOARD OF EDUCATION|STATE REPRESENTATIVE|STATE HOUSE|STATE SENATE\b|"
    r"U\.?\s?S\.? HOUSE|U\.?\s?S\.? SENATE|U\.?\s?S\.? REPRESENTATIVE|"
    r"U S REPRESENTATIVE|US REPRESENTATIVE", re.I)


def collapse(s):
    return re.sub(r"[^A-Z]", "", name_key(s))


def build_map(baseline_path=None):
    """{(party, collapsed_candidate): {(office_title, district): county_count}}"""
    path = BASELINE
    mp = defaultdict(lambda: defaultdict(int))
    with open(path) as fh:
        for r in csv.DictReader(fh):
            off = r["office"] or ""
            d = (r["district"] or "").strip()
            c = (r["candidate"] or "").strip()
            if not c or c == "Total" or not c:
                continue
            if not TARGET_RE.search(off.upper()):
                continue
            # keep every (office, district) pair for the candidate; rows whose
            # district is empty (e.g. 'Chief Justice, Supreme Court') are the
            # pair themselves
            mp[(r["party"], collapse(c))][f"{off}|{(d or '').strip()}"] += 1
    return mp


def repair_file(path, mp):
    with open(path) as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames
        rows = list(reader)
    changed = 0
    ambiguous = []
    for r in rows:
        off = r["office"] or ""
        if not TARGET_RE.search(off.upper()):
            continue
        if (r["district"] or "").strip():
            continue
        look = mp.get((r["party"], collapse(r["candidate"])))
        if not look:
            continue
        if len(look) > 1:
            ambiguous.append((r["precinct"], r["candidate"], dict(look)))
            continue
        office, district = next(iter(look)).split("|", 1)
        # office title from the baseline: 'Judge Court of Criminal Appeals'
        # etc. — use the baseline's exact (office, district) strings for join
        r["office"] = office
        r["district"] = district
        changed += 1
    if changed or ambiguous:
        tmp = path + ".tmp"
        with open(tmp, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, path)
    print(f"== {os.path.basename(path)}: {changed} rows repaired, {len(ambiguous)} ambiguous")
    for a in ambiguous[:5]:
        print("   ambiguous:", a)


def main():
    mp = build_map()
    for path in sys.argv[1:]:
        repair_file(path, mp)


if __name__ == "__main__":
    main()
