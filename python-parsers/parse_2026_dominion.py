#!/usr/bin/env python3
"""Parse Electionware/Dominion per-precinct 'Summary Results Report' PDFs for
the March 3, 2026 Texas primary into per-county precinct-level CSVs.

Each precinct section starts with a precinct label line followed by a
'Statistics' line (or both on one line), a statistics block ('Registered
Voters - Total', 'Ballots Cast - ...', 'Voter Turnout - ...'), then one block
per race: a header line '<REP|DEM|(R)|(D)> <Office>' and 'Vote For <n>', a
column header line starting with 'TOTAL' (optionally wrapped, listing method
columns), one row per candidate ('name <counts>' possibly with interleaved
'pct%' tokens), and 'Total Votes Cast' / 'Overvotes' / 'Undervotes' /
'Contest Totals' rows that end the block.

Usage:
  uv run python3 python-parsers/parse_2026_dominion.py -c COUNTY -o OUT.csv SOURCE.pdf ...
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

FIELDNAMES = ["county", "precinct", "office", "district", "party", "candidate",
              "votes", "absentee", "early_voting", "election_day", "provisional", "limited"]

PARTY_PREFIX_RE = re.compile(
    r"^\s*(?:\(?([RDNL])\)?\s+|(REPUB|REP|DEMO|DEM|NONPART|NON)\s+)(.*)$", re.I
)
PARTY_CODE = {"R": "REP", "REP": "REP", "REPUB": "REP", "REPUBLICAN": "REP",
              "D": "DEM", "DEM": "DEM", "DEMO": "DEM", "DEMOC": "DEM",
              "N": "NON", "NON": "NON", "NONPART": "NON", "NONPARTISAN": "NON"}

STATISTICS_RE = re.compile(r"^\s*Statistics\b\.?\s*$|^\s*.*\sStatistics\.?\s*$", re.I)

TOTAL_HEADER_WORDS = re.compile(
    r"^(?:total|absentee|early|election|voting|day|vote|vote %|provisional|limited|mail|\s|%)*$",
    re.I,
)

# per-county overrides for the precinct-label cleanup, if needed


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


JUNK_SUBSTR = (
    "report generated", "copyright", "summary results report",
    "precinct summary", "precinct results report", "election summary",
    "statistics", "registered voters -", "ballots cast -", "voter turnout -",
    "vote for", "overvotes", "undervotes", "total votes cast", "contest totals",
    "precinct summary", "official results", "final results", "unofficial results",
    "election", "primary", "march 3", "march", "page ",
)


def is_race_header(line):
    """Return (office_title, party) if the line starts a race block."""
    m = PARTY_PREFIX_RE.match(line.strip())
    if not m:
        return None
    title = m.group(3).strip()
    if not title or len(title) < 2:
        return None
    # must look like an office, not a statistics row or a name with an R/D initial
    if not re.search(r"(senat|represent|governor|judge|court|commission|board|prop"
                     r"|attorney|constable|sheriff|clerk|chair|treasurer|assessor"
                     r"|district attorney|justice|comptroller|general land)", title, re.I):
        return None
    code = (m.group(1) or m.group(2) or "").upper()
    party = PARTY_CODE.get(code)
    if party is None:
        return None
    return (title, party)


def parse_total_header(lines, i):
    """Parse the TOTAL column header starting at lines[i]; return (methods, next_i).
    Header lines may wrap: 'TOTAL Absentee Early Voting' + 'Election Day'."""
    merged = lines[i].strip()
    j = i
    # merge up to 2 following lines if they are pure header-keyword remnants
    while j + 1 < len(lines):
        nxt = lines[j + 1].strip()
        if nxt and TOTAL_HEADER_WORDS.fullmatch(nxt):
            merged += " " + nxt
            j += 1
        else:
            break
    low = merged.lower()
    methods = []
    for key, name in [
        ("provisional", "provisional"),
        ("limited", "limited"),
        ("ballot by mail", "mail"),
        ("absentee", "absentee"),
        ("early", "early_voting"),
        ("election day", "election_day"),
        ("election", "election_day"),
    ]:
        p = low.find(key)
        if p >= 0:
            methods.append((p, name))
    methods.sort(key=lambda x: x[0])
    # dedupe same-position matches ('election day' and 'election' both hit)
    uniq = []
    for p, name in methods:
        if uniq and uniq[-1][0] == p:
            continue
        uniq.append((p, name))
    return [m[1] for m in uniq], j + 1


COUNT_TOKEN = re.compile(r"(\d[\d,]*)$")


def parse_data_row(stripped, k):
    """Line of 'name  <n> [...pct%] <n> ...' -> (name, [counts]) using the last k
    integer tokens; pct tokens ('48.53%', '100.00%') are excluded."""
    stripped = re.sub(r"(?<=\d\s)[AOao](?=\s)", "0", stripped)
    toks = stripped.split()
    ints = []
    for pos, t in enumerate(toks):
        if re.fullmatch(r"\d[\d,]*", t):
            ints.append(pos)
    if not ints:
        return None
    if k and len(ints) > k:
        start = ints[-k]
    else:
        start = ints[0]
    if k:
        counts = [toks[p].replace(",", "") for p in ints[-k:]]
    else:
        counts = [toks[p].replace(",", "") for p in ints]
    name = " ".join(toks[:start])
    if not name:
        return None
    return name, counts


def parse_files(files):
    records = []
    warnings = []
    for pdf in files:
        lines = page_lines(pdf)
        precinct = None
        methods = []
        k = 0  # number of count columns (TOTAL first)
        current = None  # (office, district, party)
        k_page = 0
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            stripped = line.strip()
            if not stripped:
                i += 1
                continue

            # --- precinct header: label line ending with/near 'Statistics'
            if not precinct or True:
                # check: current line itself is '<label> Statistics' or bare label
                # followed by 'Statistics'
                label = None
                if re.match(r"^\s*statistics\b", stripped, re.I):
                    # label is the nearest previous non-blank, non-header-wrap line
                    back = i - 1
                    while back >= 0:
                        cand = lines[back].strip()
                        if not cand or TOTAL_HEADER_WORDS.fullmatch(cand):
                            back -= 1
                            continue
                        label = cand
                        break
                else:
                    m = re.match(r"^(.*\S)\s+Statistics\.?\s*$", stripped, re.I)
                    if m:
                        label = m.group(1)
                if label is not None:
                    # For 'PCT 001' / 'Commissioner Precinct 1' style: extract
                    # the id token following a pct/precinct/box marker, or the
                    # leading id
                    idm = re.search(r"(?:\bpct\.?\s*#?\s*|\bprecinct\b\s*|\bbox\b\s*#?\s*|#)"
                                    r"([0-9][0-9a-zA-Z/\-#]*)", label, re.I)
                    if not idm:
                        idm = re.match(r"^\s*([0-9][0-9a-zA-Z/\-#]*)", label)
                    if idm:
                        pid = idm.group(1)
                        pid_plain = pid.lstrip("#").replace("#", "")
                        if re.search(r"[0-9]", pid_plain):
                            precinct = precinct_name(pid_plain)
                        else:
                            precinct = precinct_name(pid_plain)
                    else:
                        # e.g. 'PCT X PCT' — keep tokens that aren't 'PCT'
                        parts = [p for p in re.split(r"\s+", label) if p]
                        keep = [p for p in parts if not re.fullmatch(r"(?i)(pct\.?|precinct|box)", p)]
                        label2 = " ".join(keep)
                        if re.search(r"county", label2, re.I):
                            label2 = re.sub(r"^(.*?)\s+county\b", r"\1", label2,
                                            flags=re.I).strip()
                        precinct = precinct_name(label2)
                    methods, k, k_page, current = [], 0, 0, None
                    i += 1
                    continue

            # --- race header
            race = is_race_header(line)
            if race:
                title, party = race
                norm = normalize_office(title)
                if norm:
                    current = (norm[0], norm[1], party)
                else:
                    current = (title_case_fallback(title), "", party)
                    warnings.append(f"{pdf}: unrecognized office title: {title!r}")
                i += 1
                continue

            # --- TOTAL column header
            if re.fullmatch(r"TOTAL.*", stripped, re.I) and \
               not low.startswith("total votes cast"):
                meth, i = parse_total_header(lines, i)
                methods = meth
                k = 1 + len(methods)
                k_page = max(k_page, k)
                continue

            low = stripped.lower()
            if low.startswith("ballots cast - total"):
                # learn the page's expected count-column total (total+methods)
                toks = [t for t in stripped.split() if re.fullmatch(r"\d[\d,]*", t)]
                if toks and len(toks) > 1:
                    k_page = max(k_page or 0, len(toks))
                i += 1
                continue
            if any(low.startswith(j) for j in
                   ("total votes cast", "overvotes", "undervotes", "contest totals",
                    "registered voters -", "ballots cast -", "voter turnout -",
                    "voter turnout")):
                i += 1
                continue
            if is_junk(stripped):
                i += 1
                continue
            if current is None or precinct is None:
                i += 1
                continue
            row = parse_data_row(stripped, max(k, k_page) or 1)
            if row is None:
                warnings.append(f"{pdf}: unparsed line: {stripped!r}")
                i += 1
                continue
            name, counts = row
            name = clean_candidate(name)
            if not name or re.fullmatch(r"pct\.?|precinct|box", name, re.I):
                warnings.append(f"{pdf}: suspicious data row: {stripped!r}")
                i += 1
                continue
            rec = {
                "precinct": precinct,
                "office": current[0],
                "district": current[1],
                "party": current[2],
                "candidate": name,
                "votes": counts[0] if counts else "0",
            }
            if len(counts) == len(methods) + 1 and methods:
                rec["votes"] = counts[0]
                for j2, key in enumerate(methods):
                    rec[key] = counts[j2 + 1]
            else:
                rec["votes"] = str(counts[0] if len(counts) == 1 else max(counts, key=int))
            records.append(rec)
            i += 1
    return records, warnings


def title_case_fallback(title):
    return title.strip()


def is_junk(stripped):
    low = stripped.lower()
    for frag in JUNK_SUBSTR:
        if frag in low:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--county", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--party", default=None, help="accepted for CLI uniformity; unused unless the format needs it")
    ap.add_argument("sources", nargs="+")
    args = ap.parse_args()
    records, warnings = parse_files(args.sources)
    write_county_csv(args.out, args.county, records, FIELDNAMES)
    print(f"{args.county}: wrote {len(records)} rows -> {args.out}")
    from collections import Counter
    wc = Counter(w.split(":")[0] for w in warnings)
    for w, n in wc.most_common(10):
        print(f"  WARN {n}x {w}")


if __name__ == "__main__":
    main()