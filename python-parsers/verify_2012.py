#!/usr/bin/env python3
"""Verify May 29, 2012 primary precinct CSVs against the county-level baseline
(2012/20120529__tx__primary__county.csv).

Baseline quirks (checked 2026-11-10):
  * Total rows carry a blank party; they are advisory only (the SOS generator
    sometimes equals the candidate sum minus under votes).
  * 21 corrupt rows in 13 counties where the generator collapsed fields so the
    votes column holds 'DEM' — those candidate votes are unknown; the office is
    marked corrupt and the check falls back to the sum of its known candidates.
  * Baseline office naming differs from the county sources:
    'President/VicePresident', 'Justice Supreme Court' (place in the district
    column), 'Presiding Judge, Court of Criminal Appeals', 'Railroad
    Commissioner Unexpired Term', 'U. S. Representative', 'District Judge'
    with a bare judicial-district number.

Verification semantics are those of verify_2014 (candidate sums are the
primary check; proposition offices are coverage-only). Parties are kept in
the candidate key; a primary candidate appears under a single party.

Usage:
  uv run python3 python-parsers/verify_2012.py FILE.csv [FILE2.csv ...] --json-report out.json
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from verify_2014 import canon_office, office_key, name_key, PROP_SENTINEL  # noqa: E402,F401

BASELINE_DEFAULT = os.path.join(HERE, os.pardir, "2012", "20120529__tx__primary__county.csv")

BASE_PARTY = {"D": "DEM", "R": "REP", "DEM": "DEM", "REP": "REP",
              "DEMOCRATIC": "DEM", "REPUBLICAN": "REP"}

# source-level name typos confirmed against the county-level file
NAME_ALIASES_2012 = {
    "TAWANA L CADIEN": "TAWANA W CADIEN",   # Austin county export vs SOS file
    "RAPLH M HALL": "RALPH M HALL",         # Morris county export typo
    "JOHN GRUNWOLD": "JOHN GRUNWALD",       # Calhoun county export typo
    "ELIZABETH MURRAY KOLB": "ELIZABETH MURRAYKOLB",  # county exports hyphenate it
    "MICHELE BACHMAN": "MICHELE BACHMANN",      # Bowie county export
    "UNCOMMITTEED": "UNCOMMITTED",              # Bowie / Hockley exports
    "ADDLE DAINELL ALLEN": "ADDIE DAINELL ALLEN",  # Bowie county export
    "WARRAN CHISUM": "WARREN CHISUM",           # Hockley county export
    "JOE COTTON": "JOE COTTEN",                 # Hockley county export
    "CHARLES ROEMER": "CHARLES BUDDY ROEMER",   # Hansford export
    "BAILEY C MOSELY": "BAILEY C MOSELEY",      # Bowie county export
    "LEON F PESEK JR": "LEON PESEK JR",         # Bowie county export ('F.' middle)
    "EVAN PIERCEJONES": "EVAN PIERCE JONES",    # Concho county export spacing
    "JOHN HUNSTMAN": "JON HUNTSMAN",            # Oldham county export
    "LELA PETTINGER": "LELA PITTENGER",         # Oldham county export
    "JOE POLL JR": "JOE POOL JR",               # Oldham county export
    "RICK SANTRUM": "RICK SANTORUM",            # McMullen county export
    "JOH HUNTSMAN": "JON HUNTSMAN",             # McMullen county export
    "MICHELE BACHM": "MICHELE BACHMANN",        # McMullen county export
    "REBECCA SIMM": "REBECCA SIMMONS",          # McMullen county export
    "PHYLIS J SPE": "PHYLIS J SPEEDLIN",        # McMullen county export
    "PHYLIS J SPEEDIN": "PHYLIS J SPEEDLIN",    # McMullen county export
    "WILLIAM R HAGAR": "WILLIAM R HAGER",       # McMullen/Midland export variants
    "TOM LEPPER": "TOM LEPPERT",                # McMullen county export
    "LELA PETTENGE": "LELA PITTENGER",          # McMullen county export
    "CHARLES BUDDY ROEME": "CHARLES BUDDY ROEMER",
    "GLENN ADDISOGN": "GLENN ADDISON",
}


def name_key_2012(s):
    k = name_key(s)
    return NAME_ALIASES_2012.get(k, k)


def _pre_canon(t):
    """Fixes on already-normalized parser office text before canon_office."""
    t = re.sub(r"\s+(?<=\S)\s+(REP|DEM)$", "", t, flags=re.I)  # concho party suffix
    t = re.sub(r"\bREPRESENATIVE\b", "REPRESENTATIVE", t, flags=re.I)  # Hamilton typo
    t = re.sub(r"\bCRIMINAL\s+APPEA[L]?[S]?\s+COURT\b", "COURT OF CRIMINAL APPEALS",
               t, flags=re.I)
    # Hood/Grayson-style truncations: 'Presiding Judge Ct Appeals' with no court
    # number and no party label is the Court of Criminal Appeals presiding judge
    m = re.match(r"PRESIDING\s+JUDGE\b.*\bAPPEA[L]?[S]?(?:\s+DISTRICT)?\s*$", t, re.I)
    if m:
        t = "PRESIDING JUDGE COURT OF CRIMINAL APPEALS"
    t = re.sub(r"\bMEMBER,?\s+(STATE\s+)?BOARD(?=\s+OF\s+EDUCATION)", "MEMBER STATE BOARD",
               t, flags=re.I)
    # Bosque-style reordering
    m = re.match(r"CRIMINAL\s+APPEALS\s+JUDGE,?\s*(?:PL(?:ACE)?\.?\s*)?(\d+)?\s*$", t, re.I)
    if m:
        t = "Judge Court of Criminal Appeals" + (f" Place {m.group(1)}" if m.group(1) else "")
    else:
        m = re.match(r"JUDGE\s+CRIMINAL\s+APPEALS\s*$", t, re.I)
        if m:
            t = "Presiding Judge Court of Criminal Appeals"
    m = re.match(r"JUSTICE,?\s+PLACE\s*(\d+)\s*$", t, re.I)
    if m:
        t = f"Justice, Supreme Court, Place {m.group(1)}"
    m = re.match(r"(DISTRICT (?:JUDGE|ATTORNEY))\s+(\d+)(?:ST|ND|RD|TH)?\s*"
                 r"(?:J\s+)?(?:JUD(?:I)?[A-Z]*\s*)?(?:DISTRICT)?\s*$", t, re.I)
    if m:  # Montague 'District Attorney 97th District' -> office + bare district
        t = f"{m.group(1)} District {m.group(2)}"
    t = re.sub(r"\bCTOF\s*AP?P?E?A?L?S?\.?\b", "COURT OF APPEALS", t, flags=re.I)
    m = re.match(r"(CHIEF )?JUSTICE\s+PLACE\s+(\d+)\s+(\d+)(?:ST|ND|RD|TH)?\s+"
                 r"COURT OF APPEALS DISTRICT", t, re.I)
    if m:  # Williamson: place before the court number
        t = (f"{m.group(1) or ''}JUSTICE {m.group(3)} COURT OF APPEALS DISTRICT "
             f"PLACE {m.group(2)}").strip()
    return t


def _post_key2(s, d):
    """Post-canon fixes shared with the baseline mapping."""
    if s.startswith("DISTRICT JUDGE") and s != "DISTRICT JUDGE":
        # 'District Judge 2nd 25th Judicial District' -> district '2 25'
        tail = s[len("DISTRICT JUDGE"):].strip()
        d = re.sub(r"\bJUDICIAL\s+DISTRICT\b", "", f"{d} {tail}", flags=re.I).strip()
        s = "DISTRICT JUDGE"
    if s.startswith("DISTRICT ATTORNEY") and s != "DISTRICT ATTORNEY":
        tail = s[len("DISTRICT ATTORNEY"):].strip()
        d = re.sub(r"\bJUDICIAL\s+DISTRICT\b", "", f"{d} {tail}", flags=re.I).strip()
        s = "DISTRICT ATTORNEY"
    if s in ("DISTRICT JUDGE", "DISTRICT ATTORNEY"):
        d = re.sub(r"\s*UNEXPIRED(\s+TERM)?\b", "", d, flags=re.I).strip()
        d = re.sub(r"\s+\bJ\b\s*", " ", d).strip()  # stray truncated 'J' (Midland)
        d = re.sub(r"\bDISTRICT\b\s*$", "", d).strip()
        d = _strip_jd(d)
    return (s, d)


def _strip_jd(d):
    """Judicial-district suffixes: the bare '3' and '3 JD' spellings mean the
    same race within a county, so collapse both to the bare number (applies
    to district judges and district attorneys)."""
    return re.sub(r"\s*JD\s*$", "", d).strip()


def base_office(office, district, county_name=""):
    """Map the SOS baseline (office, district) onto the canonical key."""
    s = (office or "").strip()
    su = s.upper()
    d = (district or "").strip()
    if su == "PRESIDENT/VICEPRESIDENT":
        return office_key("President", "")
    if su == "JUSTICE SUPREME COURT":
        return office_key("Justice Supreme Court Place " + d if d
                          else "Justice Supreme Court", "")
    if su.startswith("RAILROAD COMMISSIONER"):
        if "UNEXPIRED" in su:
            return ("RAILROAD COMMISSIONER UNEXPIRED", "")
        return ("RAILROAD COMMISSIONER", "")
    if su == "DISTRICT JUDGE" and re.fullmatch(r"\d+", d):
        return ("DISTRICT JUDGE", d)
    if "COURT OF CRIMINAL APPEALS" in su:
        # 'Presiding Judge, ...' vs 'Judge ...' rows; a placeless CCA row on
        # the parser side is the presiding-judge race
        if "PRESIDING" in su:
            return ("COURT OF CRIMINAL APPEALS", "PRESIDING")
        return ("COURT OF CRIMINAL APPEALS", _strip_jd(d))
    return _post_key2(*office_key(s, d, county_name))


def precinct_office(raw_office, raw_district, county_name="", raw_title=""):
    """Canonical key for an office as it appears in a parsed precinct CSV,
    with 2012 post-fixes that canon_office cannot see from the normalized
    text alone."""
    s, d = canon_office(_pre_canon(raw_office), raw_district, county_name)
    # 'Presiding Judge, Court of Criminal Appeals' keeps its identity; the
    # normalized parser text loses 'Presiding', so a placeless CCA row is it
    if s == "COURT OF CRIMINAL APPEALS":
        d = "PRESIDING" if d in ("", "PRESIDING") else _strip_jd(d)
    return _post_key2(s, d)


def load_baseline(path=None):
    path = path or BASELINE_DEFAULT
    cand = {}          # (county, office_key, party, name) -> votes or None
    totals = {}        # (county, office_key) -> Total-row value
    corrupt_rows = set()
    pres_congressional = 0
    with open(path) as fh:
        for r in csv.DictReader(fh):
            county, office, district = r["county"].strip(), r["office"], (r["district"] or "").strip()
            # the SOS file carries the presidential preference a second time as
            # 'President Congressional' rows by congressional district; those
            # duplicate the President/VicePresident rows and are skipped here
            if re.match(r"President Congressional", office or "", re.I):
                pres_congressional += 1
                continue
            if (r["candidate"] or "").strip() == "Total":
                try:
                    s, d = base_office(office, district, county)
                    totals[(county, s, d)] = int(r["votes"].replace(",", ""))
                except (ValueError, AttributeError):
                    pass
                continue
            try:
                v = int(r["votes"].replace(",", ""))
            except (ValueError, AttributeError):
                v = None
                corrupt_rows.add((county, office))
            party = BASE_PARTY.get((r["party"] or "").strip().upper(),
                                   (r["party"] or "").strip().upper())
            s, d = base_office(office, district, county)
            cand[(county, s, d, party, name_key_2012(r["candidate"]))] = v
    return cand, totals, corrupt_rows


def load_precinct(path):
    """(cand_sums, office_sums, over_under_sums, n_rows, bad_rows)."""
    sums_c = defaultdict(int)
    sums_o = defaultdict(int)
    ovu = defaultdict(lambda: [0, 0])
    rows = 0
    bad_rows = []
    m = re.match(r"20120529__tx__primary(?:__\w+)?__([a-z_]+)__precinct",
                 os.path.basename(path))
    c_name = (m.group(1).upper().replace("_", " ") if m else "")
    with open(path) as fh:
        for r in csv.DictReader(fh):
            office = (r["office"] or "").strip()
            if not office:
                continue
            if office.upper().startswith(("REGISTERED VOTERS - TOTAL", "BALLOTS CAST - ")):
                continue
            vs = str(r["votes"]).replace(",", "").strip()
            if not vs or not re.fullmatch(r"-?\d+", vs):
                bad_rows.append(f"{r['precinct']}|{office}|{r['candidate']}|{r['votes']!r}")
                continue
            rows += 1
            v = int(vs)
            title = r.get("district") or ""
            k = precinct_office(office, (r["district"] or "").strip(), c_name)
            # railroad unexpired-term race: distinguish from the full term
            if k[0] == "RAILROAD COMMISSIONER" and re.search(
                    r"UNEXPIRED", (office + " " + str(r.get("district") or "")).upper()):
                k = ("RAILROAD COMMISSIONER UNEXPIRED", "")
            c = (r["candidate"] or "").upper()
            sums_c[k + ((r["party"] or "").strip(), name_key_2012(r["candidate"]))] += v
            if re.match(r"^OVER VOTES?$", c):
                ovu[k][0] += v
            elif re.match(r"^UNDER VOTES?$", c):
                ovu[k][1] += v
            else:
                sums_o[k] += v
    return sums_c, sums_o, ovu, rows, bad_rows


def verify(path, cand, totals, corrupt_rows):
    sums_c, sums_o, ovu, rows, bad_rows = load_precinct(path)
    county = os.path.basename(path)
    m = re.match(r"20120529__tx__primary(?:__\w+)?__([a-z_]+)__precinct", county)
    c_name = m.group(1).upper().replace("_", " ") if m else None
    if c_name is None:
        return {"error": f"cannot infer county from {county}"}

    offices = {}
    for (cnty, s, d), tot_v in totals.items():
        if cnty == c_name:
            offices[(s, d)] = tot_v
    base_cands = {}
    for (cnty, s, d, party, name), v in cand.items():
        if cnty == c_name and name:
            base_cands[(s, d, party, name)] = v

    alt_c = defaultdict(int)
    for k, v in sums_c.items():
        alt_c[k[:3] + (re.sub(r"[^A-Z]", "", k[3]),)] += v
    my_props = {k: v for k, v in sums_o.items() if k[0].startswith(PROP_SENTINEL)}
    base_props = {k: v for k, v in offices.items() if k[0].startswith(PROP_SENTINEL)}
    results = {
        "rows": rows,
        "offices_baseline": sum(1 for k in offices if not k[0].startswith(PROP_SENTINEL)),
        "offices_missing": sorted(set(offices) - set(sums_o)),
        "offices_extra": sorted(set(sums_o) - set(offices)),
        "props_base": len(base_props), "props_mine": len(my_props),
        "total_mismatch": [],
        "total_row_diffs": [],
        "candidate_mismatch": [],
        "zero_override": [],
        "reconstructed_ok": 0,
        "bad_rows": bad_rows,
    }
    results["offices_missing"] = [k for k in results["offices_missing"]
                                  if not k[0].startswith(PROP_SENTINEL)
                                  and offices.get(k, 0) > 0]
    results["offices_extra"] = [k for k in results["offices_extra"]
                                if not k[0].startswith(PROP_SENTINEL)]

    corrupt_office_keys = {base_office(o, "", c_name)[0] for (cnty, o) in corrupt_rows
                          if cnty == c_name}
    for okey, t in sorted(offices.items()):
        if okey[0].startswith(PROP_SENTINEL):
            continue
        got = sums_o.get(okey, 0)
        o, u = ovu.get(okey, (0, 0))
        if okey[0] in corrupt_office_keys:
            good = sum(cv for kc, cv in base_cands.items()
                       if kc[:2] == okey and cv is not None)
            if got < max(good, t):
                results["total_mismatch"].append((okey, got, max(good, t)))
        elif abs((got + o) - (t + u)) > 2:
            results["total_row_diffs"].append((okey, got, t))
    for ckey, cval in sorted(base_cands.items()):
        okey = ckey[:2]
        if okey[0].startswith(PROP_SENTINEL):
            continue
        if ckey[3] in ("OVER VOTES", "UNDER VOTES"):
            continue
        got = sums_c.get(ckey, None)
        if got is None and ckey[3]:
            got = alt_c.get(ckey[:2] + (ckey[2], re.sub(r"[^A-Z]", "", ckey[3])), None)
        if cval is None:
            continue
        if got == cval:
            continue
        if cval == 0 and got is None:
            # the county export omits zero-vote rows for unopposed candidates
            results.setdefault("zeros_missing", []).append((ckey[1], ckey[2], ckey[3]))
            continue
        if cval == 0 and got is not None and got > 0:
            t = offices.get(okey)
            if t is not None:
                o, u = ovu.get(okey, (0, 0))
                if abs((sums_o.get(okey, 0) + o) - (t + u)) <= 2:
                    results["zero_override"].append((ckey[2], ckey[3], got))
                    continue
        results["candidate_mismatch"].append((ckey[0], ckey[1], ckey[2], ckey[3], got, cval))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("precinct_csvs", nargs="+")
    ap.add_argument("--baseline")
    ap.add_argument("--json-report")
    args = ap.parse_args()
    cand, totals, corrupt = load_baseline(args.baseline)
    report = {}
    for path in args.precinct_csvs:
        res = verify(path, cand, totals, corrupt)
        report[os.path.basename(path)] = res
        r = res
        if r.get("error"):
            print(f"== {path}: {r['error']}")
            continue
        print(f"== {os.path.basename(path)}: rows={r['rows']} "
              f"offices={r['offices_baseline']}(+{r['props_base']} props) missing={len(r['offices_missing'])} "
              f"extra={len(r['offices_extra'])} props_mine={r['props_mine']} "
              f"total_mm={len(r['total_mismatch'])} total_diffs={len(r['total_row_diffs'])} "
              f"zero_override={len(r['zero_override'])} cand_mm={len(r['candidate_mismatch'])}"
              f" bad_rows={len(r['bad_rows'])}")
        if r["offices_missing"]:
            print("   MISSING:", r["offices_missing"][:6])
        if r["offices_extra"]:
            print("   EXTRA:", r["offices_extra"][:6])
        for mm in r["total_mismatch"][:6]:
            print(f"   TOTAL-MM {mm[0]}: precinct={mm[1]} floor={mm[2]}")
        for mm in r["candidate_mismatch"][:10]:
            print(f"   CAND ({mm[0]}, {mm[1]}) | {mm[2]} | {mm[3]}: precinct={mm[4]} baseline={mm[5]}")
        for mm in r["zero_override"][:4]:
            print(f"   ZERO-OVERRIDE {mm[0]} | {mm[1]}: precinct={mm[2]} (baseline 0, totals tie)")
    if args.json_report:
        with open(args.json_report, "w") as fh:
            json.dump(report, fh, indent=1, default=str)


if __name__ == "__main__":
    main()
