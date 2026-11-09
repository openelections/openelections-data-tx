#!/usr/bin/env python3
"""Parse Hart InterCivic 'Precinct Results Report' PDFs for the March 3, 2026
Texas primary into per-county precinct-level CSVs.

The report repeats, per precinct: a precinct header line ('<id> <N> of <M>
registered voters' or '<id> <N> ballots cast'), then one block per race —
an office title ending in '(REPUBLICAN|DEMOCRATIC) PARTY' (occasionally wrapped
onto a continuation line), a column-header line naming the vote-method columns,
one row per candidate with method counts printed as '<count> <pct>%', and a
'Cast Votes:' summary row. The last count group in a candidate row is the race
total; earlier groups are the method columns in header order.

Usage:
  uv run python3 python-parsers/parse_2026_hart.py -c COUNTY -o OUT.csv SOURCE.pdf ...
"""

import argparse
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

COUNTS_RE = re.compile(r"(\d[\d,]*)\s+[-(]?\d+(?:\.\d+)?%")
FIELDNAMES = ["county", "precinct", "office", "district", "party", "candidate",
              "votes", "absentee", "early_voting", "election_day", "provisional", "limited"]
PARTY_IN_TITLE = re.compile(
    r"(REPUBLICAN|DEMOCRATIC|NONPARTISAN|LIBERTARIAN|GREEN)\s+PARTY"
    r"(?:\s*-\s*(?:VOTE FOR|NO MORE THAN)?[^,]*)?\W*$", re.I
)
PARTY_CODE = {"REPUB": "REP", "REPUBLICAN": "REP", "REP": "REP",
              "DEMOC": "DEM", "DEMOCRATIC": "DEM", "DEM": "DEM",
              "NONP": "NON", "NONPARTISAN": "NON",
              "LIBE": "LIB", "GREEN": "GRN"}

PRECINCT_HEADER_RE = re.compile(
    r"^\s*([0-9A-Z](?:[0-9A-Za-z \-,.;()]{0,38}?[0-9A-Za-z])?)\s+([\d,]+)\s+"
    r"(?:of\s+[\d,]+\s+registered voters|ballots\w* cast)\b", re.I)

# Lines that are page furniture; never data.
JUNK_SUBSTR = (
    "precinct results report", "canvass results report", "official results",
    "primary election", "election results", "run time", "run date",
    "page ", "precincts reporting", "polling places reporting",
    "copyright", "report generated", "statistics", "final results",
    "all races", "unofficial results", "office of the",
)

SUMMARY_ROW_RE = re.compile(
    r"^(cast votes|undervotes|overvotes|rejected write-in|total votes cast|"
    r"contest totals|ballots cast|registered voters|total ballots)", re.I)

METHOD_TOKENS = [
    ("election day voting", "election_day"),
    ("election night in person", "election_day"),
    ("election day", "election_day"),
    ("early voting", "early_voting"),
    ("early vote", "early_voting"),
    ("early", "early_voting"),
    ("absentee voting", "absentee"),
    ("absence", "absentee"),
    ("absentee", "absentee"),
    ("provisional voting", "provisional"),
    ("provisional", "provisional"),
    ("ballot by mail", "mail"),
    ("limited", "limited"),
    ("mail", "mail"),
]

OFFICE_WORD_RE = re.compile(
    r"(senat|representative|governor|judge|court|commission|comptroller"
    r"|board of education|district attorney|sheriff|clerk|treasurer|justice"
    r"|constable|attorney general|prop|school board|measure|question"
    r"|general land)", re.I)


def page_lines(pdf):
    """Layout text: pdftotext for PDFs; OCR sidecar (.ocr.txt) text files pass
    through directly."""
    if pdf.endswith(".txt"):
        with open(pdf) as fh:
            return fh.read().splitlines()
    out = subprocess.run(
        ["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True, check=True
    )
    return out.stdout.splitlines()


def is_junk(line):
    s = line.strip()
    if not s:
        return True
    low = s.lower()
    # short banner fragments
    if len(s) <= 40 and any(
        frag in low for frag in ("official results", "preliminary results",
                                 "unofficial results", "official", "total", "all races",
        )
    ):
        return True
    for frag in JUNK_SUBSTR:
        if frag in low:
            return True
    return False


def method_header(line):
    """Return the vote-method keys in display order if line is the method header."""
    low = line.strip().lower()
    if "total" not in low:
        return None
    if not any(k in low for k in ("absentee", "early", "election day",
                                  "provisional", "limited", "mail")):
        return None
    found = []
    for name, key in METHOD_TOKENS:
        idx = 0
        while True:
            idx = low.find(name, idx)
            if idx == -1:
                break
            found.append((idx, -len(name), key))
            idx += 1
    found.sort(key=lambda x: x[0])
    methods = []
    for idx, _, key in found:
        if methods and methods[-1] == key:
            continue  # overlapping/contained duplicate of the same column
        methods.append(key)
    return methods or None


def strip_party(txt):
    """Strip a leading 'REP '/'(D) ' party marker; return (title, party)."""
    m = re.match(r"^\s*\(([RDNL])\)\s*(.*)$", txt, re.I)
    if m:
        return m.group(2).strip(), {"R": "REP", "D": "DEM", "N": "NON", "L": "LIB"}[m.group(1).upper()]
    m = re.match(r"^(REPUB|REPUBLICAN|REP|DEMO|DEMOC|DEMOCRATIC|DEM|NON|NONPARTISAN)[A-Z. ]", txt, re.I)
    if m:
        code = m.group(1).upper()
        party = {"REPUB": "REP", "REPUBLICAN": "REP", "REP": "REP",
                 "DEMO": "DEM", "DEMOC": "DEM", "DEMOCRATIC": "DEM", "DEM": "DEM",
                 "NON": "NON", "NONPARTISAN": "NON"}.get(code, code[:3])
        return txt[m.end(1):].strip(), party
    return txt.strip(), None


def looks_like_race_title(stripped):
    """Heuristic for an office-title line that lacks the party suffix (wrap case)."""
    if COUNTS_RE.search(stripped):
        return False
    if len(stripped) > 100:
        return False
    if re.match(r"^(choice|party|vote for 1|vote for)", stripped, re.I):
        return False
    return bool(OFFICE_WORD_RE.search(stripped))


def parse_files(files):
    records = []
    warnings = []
    for pdf in files:
        lines = page_lines(pdf)
        precinct = None
        methods = []
        candidate_title_txt = None  # prefix-style buffered race title
        recent_titles = []  # office-title fragments seen since the last boundary
        office = None
        district = ""
        party = None

        for raw in lines:
            line = raw.rstrip()
            if is_junk(line):
                continue

            pm = PRECINCT_HEADER_RE.match(line)
            if pm:
                precinct = precinct_name(pm.group(1))
                methods = []
                candidate_title_txt = None
                recent_titles = []
                office, district, party = None, "", None
                continue

            mh = method_header(line)
            if mh:
                methods = mh
                continue

            stripped = line.strip()
            if SUMMARY_ROW_RE.match(stripped):
                # end of a race block
                recent_titles = []
                methods = []
                office, district, party = None, "", None
                continue

            party_m = PARTY_IN_TITLE.search(stripped)
            if party_m:
                title = stripped[: party_m.start()].rstrip(" -,")
                if recent_titles:
                    title = " ".join(recent_titles + [title])
                recent_titles = []
                norm = normalize_office(title)
                party = PARTY_CODE[party_m.group(1).upper()]
                if norm:
                    office, district = norm
                else:
                    warnings.append(f"{pdf}: unrecognized office title: {title!r}")
                    office, district = None, ""
                continue

            if looks_like_race_title(stripped):
                recent_titles.append(stripped)
                continue

            if recent_titles:
                # a buffered title that never received the party suffix: these
                # are prefix-style titles ('REP Justice, 12th Ct of App Dist,
                # Pl 3') — promote it when the data rows follow
                candidate_title_txt = " ".join(recent_titles)
                recent_titles = []

            if office is None or precinct is None:
                continue

            grps = COUNTS_RE.findall(line)
            if not grps:
                continue
            if candidate_title_txt and looks_like_race_title(candidate_title_txt):
                norm = normalize_office(strip_party(candidate_title_txt)[0])
                if norm:
                    office, district = norm
                    p = strip_party(candidate_title_txt)[1]
                    if p:
                        party = p
                candidate_title_txt = None
            first = re.search(COUNTS_RE, line)
            name_part = line[: first.start()].strip()
            name_part = re.sub(r"\s*\b(?:DEM|DEMOC|REP|REPUBLIC|R|D)\s*$", "", name_part,
                               flags=re.I)
            name = clean_candidate(name_part)
            if not name:
                warnings.append(f"{pdf}{precinct}: candidate row without name: {line!r}")
                continue
            counts = [g.replace(",", "") for g in grps]
            total = counts[-1]
            rec = {
                "precinct": precinct,
                "office": office,
                "district": district,
                "party": party,
                "candidate": name,
                "votes": total,
            }
            if methods and len(counts) == len(methods) + 1:
                for i, key in enumerate(methods):
                    rec[key] = counts[i]
            elif methods and len(counts) == len(methods):
                # source printed method counts only; last is the last method?? —
                # treat last as that method and also as votes (ambiguous; warn)
                warnings.append(
                    f"{pdf}{precinct}: row count mismatch methods={methods} counts={counts}")
                for i, key in enumerate(methods):
                    rec[key] = counts[i]
            elif len(counts) > 1:
                warnings.append(
                    f"{pdf}{precinct}: unmatched column counts, "
                    f"methods={methods} counts={counts}, row={line!r}")
                rec["_unmatched"] = counts
            records.append(rec)
        # end file
    return records, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--county", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--party", default=None, help="accepted for CLI uniformity; unused unless the format needs it")
    ap.add_argument("sources", nargs="+")
    args = ap.parse_args()
    records, warnings = parse_files(args.sources)
    write_county_csv(args.out, args.county.title(), records, FIELDNAMES)
    print(f"{args.county}: wrote {len(records)} rows -> {args.out}")
    for w in warnings[:40]:
        print("  WARN", w)
    if len(warnings) > 40:
        print(f"  ... {len(warnings) - 40} more warnings")


if __name__ == "__main__":
    main()