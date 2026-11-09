#!/usr/bin/env python3
"""Parse Electionware 'Summary Results Report' per-precinct pages whose races
are headed '<DEM|REP> <office title>' with a bare precinct-number section label
(Lee County 2026 primary; also fits counties with the same style). Each page of
the report is one precinct (or several): a line holding only a 2-4 digit
precinct number at the left margin starts a precinct; race blocks follow:

  DEM US Senator
  Vote For 1
                                        TOTAL Absentee        Early   Election
                                                             Voting       Day
  Ahmad R. Hassan                            2             0     0          2

Candidate rows end with 4 integers: TOTAL, Absentee, Early, Election Day; the
breakdown columns are emitted. 'Total Votes Cast' rows are skipped.

Usage:
  uv run python3 python-parsers/parse_2026_leestyle.py -c COUNTY -o OUT.csv
        SOURCE-dem.pdf SOURCE-rep.pdf
"""

import argparse
import csv
import re
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers_2026 import (  # noqa: E402
    normalize_office,
    clean_candidate,
    precinct_name,
    write_county_csv,
)

FIELDNAMES = ["county", "precinct", "office", "district", "party", "candidate",
              "votes", "absentee", "early_voting", "election_day", "provisional", "limited"]

JUNK_RE = re.compile(
    r"(summary results report|precinct results report|precinct summary|"
    r"report generated with|2026 primary election|primary election|"
    r"^march 3, 2026)", re.I)

ROW_RE = re.compile(r"^(.*?)(?:\s+(\d{1,3}(?:,\d{3})*)\s+(\d{1,3}(?:,\d{3})*)"
                    r"\s+(\d{1,3}(?:,\d{3})*)\s+(\d{1,3}(?:,\d{3})*))\s*$")


def layout_text(pdf_path):
    res = subprocess.run(["pdftotext", "-layout", pdf_path, "-"],
                         capture_output=True, text=True, check=True)
    return res.stdout.splitlines()


def parse_files(files):
    records, warnings = [], []
    for src in files:
        base = os.path.basename(src).lower()
        if "_rep" in base:
            file_party = "REP"
        elif "_dem" in base:
            file_party = "DEM"
        else:
            file_party = "NA"

        precinct = None
        office = None      # (office, district) or fallback string
        office_party = file_party
        state = "idle"
        for line in layout_text(src):
            stripped = line.rstrip("\x0c").strip()
            if not stripped or JUNK_RE.search(stripped):
                continue
            if re.match(r"^\d{2,4}$", stripped):
                precinct = precinct_name(stripped)
                state = "idle"
                office = None
                continue
            if re.match(r"^(?:Vote For\s+.*)$", stripped, re.I):
                state = "candidates"
                continue
            m = re.match(r"^(DEM|REP|R|D)\s+(.*)$", stripped)
            if m and len(line) - len(line.lstrip()) <= 4:
                office_party = {"REP": "REP", "R": "REP", "DEM": "DEM",
                                "D": "DEM"}[m.group(1).upper()]
                title = m.group(2).strip()
                norm = normalize_office(title)
                if norm:
                    office = norm
                else:
                    office = (title, "")
                    warnings.append(f"{src}: unrecognized office title: {title!r}")
                state = "office"
                continue
            if state == "office":
                # wrapped office title continuation (no digits present)
                if not re.search(r"\d", stripped) and re.search(r"[A-Za-z]", stripped):
                    title = (office[1] if office else "")
                    office = None
                    warnings.append(f"{src}: check wrapped office {title!r}")
                    state = "idle"
                    continue
            if state == "candidates":
                if re.match(r"^total\b", stripped, re.I) or \
                   re.match(r"^voting\b", stripped, re.I) or \
                   re.match(r"^election day$", stripped, re.I):
                    continue
                mrow = ROW_RE.match(stripped)
                if mrow:
                    name = mrow.group(1).strip()
                    if re.match(r"^total votes cast", name, re.I):
                        continue
                    counts = [g.replace(",", "") for g in mrow.group(2, 3, 4, 5)]
                    if not name:
                        warnings.append(f"{src}: unnamed data row: {stripped!r}")
                        continue
                    rec = {
                        "precinct": precinct,
                        "office": office[0] if isinstance(office, tuple) else office,
                        "district": office[1] if isinstance(office, tuple) else "",
                        "party": office_party if file_party == "NA" else file_party,
                        "candidate": clean_candidate(name),
                        "votes": counts[0],
                        "absentee": counts[1],
                        "early_voting": counts[2],
                        "election_day": counts[3],
                    }
                    records.append(rec)
                    continue
                if re.match(r"^(total votes cast|cast votes|undervotes|overvotes)", stripped, re.I):
                    continue
                if re.match(r"^\d{1,3}(?:,\d{3})*$", stripped):
                    # lone trailing number column spillover; attach to previous row
                    continue
                if re.search(r"[A-Za-z]", stripped):
                    warnings.append(f"{src}: unparsed candidate line: {stripped!r}")
            # office-title garbage or headers with digits; ignore
    return records, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--county", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("sources", nargs="+")
    args = ap.parse_args()
    records, warnings = parse_files(args.sources)
    write_county_csv(args.out, args.county, records, FIELDNAMES)
    print(f"{args.county}: wrote {len(records)} rows -> {args.out} (warn {len(warnings)})")
    for wtxt in warnings[:15]:
        print("  WARN", wtxt)


if __name__ == "__main__":
    main()
