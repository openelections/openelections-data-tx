#!/usr/bin/env python3
"""Parse Hart/SOS 'PREC REPORT-GROUP DETAIL' (EL30A/EL45A) text exports —
Calhoun's 2012 .LST files (and similar text reports) — into precinct CSV rows.

Layout (verified against CALHOUN EL30A.LST):
    0001 PRECINCT 1
                 TOTAL VOTES     %   EARLY VOTING  ELECTION DAY
    President
    VOTE FOR  1
     John Davis .  .  .  .  .  .  .  .       0                     0             0
Binaries (Chambers .WRK etc.) are 200-byte records prefixed with a marker byte
+ \x00\x00\x01 and 3-digit line counters, stripped here. Only the first
numeric field (TOTAL VOTES) is used.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers_2026 import normalize_office, precinct_name
from parse_2012_asc import expand_2012

SKIP_PATTERNS = re.compile(r"RUN DATE|^REPORT-|^SUMMARY REPT|^PREC REPORT|PRIMARY ELECTION"
                           r"|" r"MAY 29, 2012" r"|VOTE FOR", re.I)
STATS_RE = re.compile(r"PRECINCTS COUNTED|BALLOTS CAST|REGISTERED VOTERS|VOTER TURNOUT"
                      r"|TOTAL VOTES|STATISTICS", re.I)
CAND_RE = re.compile(r"^(\s*)(.+?)\s*\.(?:\s*\.)+\s*(.*)$")
PCT_RE = re.compile(r"^(\d{1,4})\s+PRECINCT\s+(?:NO\.?\s*)?(\d+[A-Z]?)\s*$", re.I)


def read_text_lines(path):
    raw = open(path, "rb").read()
    txt = re.sub(rb"[\x80-\xff]\x00\x00\x01", b"\n", raw).decode("latin-1")
    lines = [re.sub(r"^[\x80-\xff]\d+\s*", "", l).rstrip() for l in txt.split("\n")]
    return lines


def parse_file(path):
    """Returns list of (precinct, raw_office_title_or_STAT marker, candidate,
    votes, party). The LST files interleave DEM and REP pages in one file; the
    party comes from the page header."""
    rows = []
    precinct = None
    office = None
    party = None
    for line in read_text_lines(path):
        s = line.strip()
        if not s:
            continue
        mrun = re.search(r"(REPUBLICAN|DEMOCRATIC)\s+PARTY", s)
        if mrun and "RUN DATE" in s:
            party = "REP" if mrun.group(1).upper().startswith("R") else "DEM"
        m = PCT_RE.match(s)
        if m:
            precinct = precinct_name(m.group(2))
            office = None
            continue
        stat = re.match(r"^(REGISTERED VOTERS - .*?|BALLOTS CAST - .*?)\s*\.(?:\s*\.)+\s*(.*)$",
                        s, re.I)
        if stat:
            cand = stat.group(1).strip()
            nums = re.findall(r"\d[\d,]*(?:\.\d+)?", stat.group(2))
            sp = ("REP" if "REPUBLICAN" in cand.upper() else
                  "DEM" if "DEMOCRATIC" in cand.upper() else "")
            rows.append((precinct, "__STAT__:" + cand, cand,
                         int(nums[0].replace(",", "")) if nums else 0, sp))
            continue
        if STATS_RE.search(s) or SKIP_PATTERNS.search(s):
            continue
        m = CAND_RE.match(line)
        if m and m.group(2) and office:
            name = m.group(2).strip()
            nums = re.findall(r"\d[\d,]*(?:\.\d+)?", m.group(3))
            row_name = name.title() if name.lower() in ("over votes", "under votes") \
                or name.lower().startswith("write-in") else name
            rows.append((precinct, office, row_name,
                         int(nums[0].replace(",", "")) if nums else 0, party))
            continue
        if len(s) <= 60 and not re.search(r"^\d+$", s):
            office = s
    return rows


def run_county(county, out, sources, party_default=None):
    import parse_2014_asc
    all_rows = []
    for src in sources:
        low = os.path.basename(src).lower()
        party = parse_2014_asc.party_from_filename(src, party_default or "")
        for precinct, title, cand, votes in parse_file(src):
            if precinct is None:
                continue
            if title.startswith("__STAT__:"):
                stat = title[len("__STAT__:"):].strip().upper()
                party_of_stat = "REP" if "REPUBLICAN" in stat else ("DEM" if "DEMOCRATIC" in stat else "")
                all_rows.append({
                    "county": county, "precinct": precinct,
                    "office": stat.title(), "district": "", "party": party_of_stat,
                    "candidate": stat.title(), "votes": votes})
                continue
            title_e = _base.clean_title(expand_2012(title), county)
            res = normalize_office(title_e)
            office, district = (res[0], res[1] if len(res) > 1 else "") \
                if res else (title_e.title(), "")
            all_rows.append({
                "county": county, "precinct": precinct,
                "office": office, "district": district, "party": party,
                "candidate": cand, "votes": votes})
    from helpers_2026 import write_county_csv
    write_county_csv(out, county, all_rows,
                     ["county", "precinct", "office", "district", "party", "candidate", "votes"])
    print(f"wrote {out}: {len(all_rows)} rows")
    return len(all_rows)
