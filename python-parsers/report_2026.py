#!/usr/bin/env python3
"""Summarize verification of every county precinct CSV in 2026/counties against
the SOS county-level baseline, writing a markdown report with per-county status
and every mismatch listed.

Usage: uv run python3 python-parsers/report_2026.py [--out 2026/20260303-precinct-verification.md]
"""

import argparse
import glob
import re
import os
import sys
import json
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_2026 import verify  # noqa: E402
from helpers_2026 import load_county_baseline  # noqa: E402

GENERAL_NOTES = {
    "atascosa": "The SOS canvass row for Governor 'Charles Andrew Crouch' (8) "
                "contradicts the county's own precinct report (33): the SOS "
                "overflow-section pages for 11-candidate races mis-position some "
                "counties' rows. Lt Gov Timothy Mabry differs by 3 votes (335 vs 338).",
    "montgomery": "Same overflow artifact: Mike Holley (DA 9th unexpired) matches "
                  "in total (61,352) but the SOS lists the race as 'District "
                  "Attorney 9th Judicial District - Unexpired Term' while the "
                  "county's report labels it '268th Judicial District'.",
    "mclennan": "Same: Pete Rusek (District Judge 74th, unexpired) matches in "
                "total; the county's report omits '- Unexpired Term'.",
    "houston": "Same: Michael Davis (12th Court of Appeals Place 3 unexpired) "
               "matches in total; the SOS appends '- Unexpired Term' where the "
               "county report doesn't. Also State BoE and Land Office rows "
               "parsed under abbreviated county report titles.",
    "jasper": "State Board of Education rows parsed under the county report's "
              "'Member, State BoE, Dist N' labels; totals verified.",
    "navarro": "State Board of Education rows parsed under abbreviated titles; "
               "totals verified.",
    "cherokee": "Michael Davis (12th Court of Appeals, unexpired) matches in "
                "total; the county report's title lacks '- Unexpired Term'.",
    "rains": "Michael Davis and Kason Huddleston (State Board of Education) "
             "match in total; race labels use the county report's forms.",
    "van_zandt": "Michael Davis matches in total; label difference only.",
    "cooke": "Land Commissioner rows: the county report labels the race 'Comm "
             "General Land Office'; totals verified.",
    "sutton": "Land Commissioner: race labeled 'Comm General Land Office' in the "
              "county report; totals verified.",
    "fayette": "Land Commissioner labeled 'Comm General Land Office' in the "
               "county report; totals verified.",
    "collin": "96 races' precinct sums run 1-13 votes below the county's own "
              "total row (and the SOS canvass) — ~0.6% of votes sits in no "
              "precinct column of the source export.",
    "randall": "Two candidates (Villescaz, Hopkins) don't appear in the county "
               "canvass reports at all; every other candidate's precinct sums "
               "match the SOS canvass exactly.",
    "tarrant": "One mismatch (DAVID COOK, State Senate 22) is attributable to "
               "the SOS canvass value (12,351) vs the county's own reports "
               "(129,746); the county precinct reports self-verify per race.",
    "bell": "Two cells in the SOS canvass disagree with the county's own report "
            "(whose per-precinct rows are internally consistent).",
    "terrell": "The xlsx TOTAL column for two court races includes 2 more votes "
               "(limited/provisional) than the SOS totals.",
    "limestone": "County-local offices (JOP, commissioner, props) carry garbled "
                 "race labels in the source scans; the statewide rows all "
                 "verify exactly.",
    "brazos": "Vote-center county: rows are aggregated across the 35 voting-"
              "location reports; mail ballots carry combined multi-precinct "
              "labels; ~3% of Republican statewide votes are missing from the "
              "source set vs the SOS canvass.",
    "gillespie": "Republican source is county-level only (no precinct "
                 "dimension).",
    "liberty": "The county's official report counts limited-ballot and "
               "provisional votes; the SOS canvass excludes them.",
    "brooks": "One cell in the SOS canvass lists Supreme Court Place 2 DEM "
              "Chari Kelly as 0 while the county's own report gives her "
              "777 votes (internally consistent per precinct, like Bell).",
    "willacy": "The source is the county's election-night report (run 03/03 "
               "7:04 PM) whose absentee/mail column is empty; the SOS canvass "
               "counts mail/provisional votes the county report does not "
               "allocate, so every statewide race runs ~41% short of the "
               "county-level file. No official per-precinct source exists in "
               "the source set.",
    "orange": "Source is a county-cumulative summary (no precinct dimension) "
              "in the source set.",
    "cass": "Source is a county-cumulative summary (no precinct dimension) "
            "in the source set.",
    "parker": "One US House race's candidate name parsed from wrapped report "
              "text ('Angela ... Prilliman'); totals verified.",
}
NOTES = {
    "bell": ("REP US Senate Ken Paxton (precinct sum 8,811 vs SOS 4,211) and "
             "Ct of Criminal Appeals Place 3 Lesli Fitzpatrick (4,382 vs 4,112): "
             "Bell County's own precinct report is internally consistent per "
             "precinct (each row's election-day/early/absentee counts add to its "
             "total) while the SOS canvass under-reports these two cells."),
    "liberty": ("Both parties' totals include the Limited-Ballot (and provisional) "
                "votes counted in Liberty's official report; the SOS canvass "
                "excludes them. Per-row breakdown columns add exactly."),
    "collin": ("The county's own Excel export under-allocates a few votes to the "
               "precinct matrix (96 races are 1-13 votes short of the county "
               "total row and the SOS canvass; ~0.6% of votes)."),
    "randall": ("Villescaz (Dem governor) and Hopkins (Rep lieutenant governor) "
                "do not appear in the county's canvass reports at all, so their "
                "precinct rows cannot be emitted (509/806 votes)."),
    "gillespie": ("The Democratic canvass is precinct-level; the Republican "
                  "source reports county-level vote-type totals only, so "
                  "Republican precinct rows are unavailable."),
    "cass": ("Only a county-cumulative summary exists (vote-method totals per "
            "race, no precinct columns); not suitable for precinct rows."),
    "brazos": ("Precinct rows are built from 35 voting-location reports plus the "
               "mail-by-group and limited-ballot reports; the mail votes of "
               "multi-precinct mail groups carry the group's precinct list as "
               "the precinct label. Roughly 3% of Republican statewide votes "
               "(257 on US Senate) are missing from the provided location "
               "report set compared to the SOS canvass."),
    "hamilton": ("OCR-derived from scans; per-precinct rows for the four "
                 "commissioner precincts; county-level sums fall short of SOS "
                 "totals due to OCR errors on low-contrast digits."),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--dir", default="2026/counties")
    ap.add_argument("--json", default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    baseline = load_county_baseline()
    files = sorted(glob.glob(os.path.join(args.dir, "20260303__tx__primary*precinct.csv")))
    counties = set()
    for c in baseline:
        counties.add(c[0])
    counties = sorted(counties)

    per = {}
    all_files = []
    for f in files:
        name = os.path.basename(f)
        cslug = re.sub(r"20260303__tx__primary__|__precinct\.csv$", "", name)
        pf, diffs = verify([f], baseline)
        mism = [d for d in diffs if d[7] == "mismatch"]
        nocov = [d for d in diffs if d[7] == "no precinct coverage"]
        nb = [d for d in diffs if d[7] == "not in baseline"]
        info = pf[f]
        per[cslug] = {
            "file": f,
            "precincts": info["precincts"],
            "n_offices": len(info["offices"]),
            "rows": info["rows"],
            "mismatches": [{"office": d[1], "district": d[2], "party": d[3],
                            "candidate": d[4], "parsed": d[5], "baseline": d[6]}
                           for d in mism],
            "no_coverage": [{"office": d[1], "district": d[2], "party": d[3],
                             "candidate": d[4], "baseline": d[6]}
                            for d in nocov],
            "not_in_baseline": len(nb),
        }
        all_files.append(cslug)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(per, fh, indent=1)

    if args.out:
        with open(args.out, "w") as fh:
            done = set(all_files)
            fh.write("# 2026 March 3 Texas primary — precinct-level results\n\n")
            fh.write("## County status\n\n")
            fh.write(f"{len(done)} of {len(counties)} counties have precinct-level "
                     f"CSVs under `2026/counties/`.\n\n")
            fh.write("## Verification against the county-level SOS canvass\n\n")
            totals = {"match": 0}
            for cslug in sorted(per):
                p = per[cslug]
                total = 1 if p["mismatches"] or p["no_coverage"] else 0
                totals["match" if total == 0 else "diff"] = totals.get(
                    "match" if total == 0 else "diff", 0) + 1
            fh.write(f"- counties with every statewide candidate matching the SOS "
                     f"canvass exactly: **{totals.get('match', 0)}**\n")
            fh.write(f"- counties with discrepancies (detailed below): "
                     f"**{totals.get('diff', 0)}**\n\n")
            for cslug in sorted(per):
                p = per[cslug]
                status = ("OK" if not p["mismatches"] and not p["no_coverage"]
                          else ("discrepancies" if p["mismatches"] else "partial"))
                fh.write(f"### {cslug} — {status}\n\n")
                fh.write(f"{p['rows']} rows, {len(p['precincts'])} precincts, "
                         f"{p['n_offices']} offices.\n\n")
                if cslug in NOTES:
                    fh.write(f"Note: {NOTES[cslug]}\n\n")
                if p["mismatches"]:
                    fh.write("Mismatches vs the SOS county canvass:\n\n"
                             "| office | district | party | candidate | precinct sum | SOS |\n"
                             "|---|---|---|---|---|---|\n")
                    for m in p["mismatches"]:
                        fh.write(f"| {m['office']} | {m['district']} | {m['party']} | "
                                 f"{m['candidate']} | {m['parsed']} | {m['baseline']} |\n")
                    fh.write("\n")
                if p["no_coverage"]:
                    fh.write("Candidates in the SOS canvass with no precinct "
                             "coverage (values present in the SOS only):\n\n")
                    for m in p["no_coverage"]:
                        fh.write(f"- {m['office']} | {m['district']} | {m['party']} | "
                                 f"{m['candidate']} (SOS {m['baseline']})\n")
                    fh.write("\n")
        print(f"wrote {args.out}")
    if not args.quiet:
        for cslug in sorted(per):
            p = per[cslug]
            flag = "!" if (p["mismatches"] or p["no_coverage"]) else " "
            print(f"{flag} {cslug:16} rows={p['rows']:6} precincts={len(p['precincts']):3} "
                  f"mismatch={len(p['mismatches']):4} nocov={len(p['no_coverage']):4} "
                  f"notbase={p['not_in_baseline']:4}")


if __name__ == "__main__":
    main()