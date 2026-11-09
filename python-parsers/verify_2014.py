#!/usr/bin/env python3
"""Verify 2014 primary precinct CSVs against the county-level baseline
(2014/20140304__tx__primary__county.csv).

Known baseline defects (documented 2026-11-08):
  * ~1163 corrupt rows in 32 counties of the form
    `<county>,<office>,<district>,<candidate>,,,<party>,0` — the generator
    collapsed fields, so those candidate votes are unknown in the baseline.
  * The baseline "Total" rows don't always equal the sum of their candidate
    rows and often equal the candidate sum minus the UNDER VOTES the county
    report carried. They are advisory only; candidate rows are the
    authoritative check.

Verification semantics:
  * Offices are matched on a canonical (office, district) key via canon_office
    (handles 'Justice Supreme Court' <-> 'Supreme Court'/'Place N',
    'Judge Court of Criminal Appeals', 'Comptroller of Public Accounts', and
    the 'Judge, 154th Judicial District' <-> 'District Judge' forms).
  * Proposition offices ('Prop N <text>' in the baseline; county-specific text
    in the county reports) are checked separately: their titles never agree,
    so they are only reported by coverage, never failed.
  * Primary check is per-candidate sums vs baseline candidate rows. A baseline
    row of 0 votes is allowed to differ when the office-level totals tie out
    (the SOS county file wrote 0 for some unopposed candidates).
Usage:
  uv run python3 python-parsers/verify_2014.py FILE.csv [FILE2.csv ...] --json-report out.json
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict

BASELINE_DEFAULT = os.path.join(os.path.dirname(__file__), os.pardir,
                                "2014", "20140304__tx__primary__county.csv")
PROP_SENTINEL = "PROP:"


NAME_ALIASES = {
    "ERNEST WHILE": "ERNEST WHITE",
    "RUBN HINOJOSA": "RUBEN HINOJOSA",  # SOS county file drops the accented e   # county-level file spells Dallas judge's
                                      # name wrong; precinct source has White
    # source-level typos confirmed per county (2014 excel group):
    "CYNTHIA L MUNIZ": "CYNTHIA L MUIZ",  # Zavala source vs baseline spelling
    "JOE COTTON": "JOE COTTEN",           # Coleman/Hall source typo
    "JOHN CORYN": "JOHN CORNYN",          # Newton source typo
    "BAN BRANCH": "DAN BRANCH",           # Hall source typo
    "PONCHO NEVAREZ": "PONCHO NEV REZ",   # Kinney source vs baseline mojibake
    "ROBERT LOWERY": "ROBERT LOWRY",      # Kinney source typo
    "WYANE CHRISTIAN": "WAYNE CHRISTIAN", # Childress source typo
    "W C BUD KIRKENDELL": "W C BUD KIRKENDALL",  # Childress source typo
    "BERT RICHARSON": "BERT RICHARDSON",  # Hockley source typo
    "GREG ABBOT": "GREG ABBOTT",          # Hockley source typo
    "SECEDE KILGOR": "SECEDE KILGORE",    # Hockley source typo
}


def name_key(s):
    import unicodedata
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.upper().replace('"', "").replace("'", "").replace("&", "AND")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return NAME_ALIASES.get(s, s)


def canon_office(office, district="", county_name=""):
    """Canonical (office, district) matching key.

    Proposition offices keep their (county-specific) text, marked with the
    PROP: sentinel; the caller must never fail on them.
    """
    s = office.upper().strip()
    if re.match(r"^PROP|PROPOSITION", s):
        return (PROP_SENTINEL + name_key(s), "")
    # ordinal 7th -> 7
    s = re.sub(r"\b(\d+)(?:ST|ND|RD|TH)\b", r"\1", s)
    s = re.sub(r"\bDIS(TRI|TRICT)?\b\.?", "DISTRICT", s)  # truncated 'Appeals Dis'
    s = re.sub(r"\bCO?U?RT OF\s+AP(S|P|PP)?\.?\b", "COURT OF APPEALS", s)
    s = re.sub(r"\bAP(S|P|PP)LS?\b", "APPEALS", s)
    s = re.sub(r"\bUNEXP(IRE[D])?(\s+TERM)?\b", "UNEXPIRED", s)
    s = re.sub(r"\bSTATE HOUSE\b", "STATE REPRESENTATIVE", s)
    s = re.sub(r"^MEMBER\s+", "", s)
    s = re.sub(r"^(?:DEM|REP)\s+(?=[A-Z])", "", s)

    s = re.sub(r"\bPL\.?\s*(\d)", r"PLACE \1", s)
    s = re.sub(r"\bNO\.?\s*(\d+)", r"PLACE \1", s)
    s = re.sub(r"\bCOMM?I?S?[SO]*NER\b", "COMMISSIONER", s)  # COMMISSONER typo
    if "CHIEF JUSTICE" in s and "SUPREME" in s:
        s = "SUPREME COURT"
        district = (re.sub(r"\bUNEXPIRED( TERM)?\b", "", district.upper())
                    .replace("PLACE", "").strip() if district else "CHIEF")
    if re.search(r"GENERAL\s+LAND", s) or re.search(r"LAND\s+COMMISSIONER", s):
        s = "LAND COMMISSIONER"
    if "COMPTROLLER" in s:
        s = "COMPTROLLER"
    s = re.sub(r"^(LIEUTENANT )?GOVE[^\s]*\s*R$", r"\1GOVERNOR", s)
    s = re.sub(r"U\.?\s?S\.?\s+CONGRESSIONAL", "U S HOUSE", s)
    s = re.sub(r"\bST\.?\s+BOARD\b", "STATE BOARD", s)
    # trailing '<office> District <n>' -> district
    mtd = re.match(r"^(.*\S)\s+DISTRICT\s+(\d+)$", s)
    if mtd and not (district or "").strip():
        s, district = mtd.group(1), mtd.group(2)
        if s == "STATE REP":
            s = "STATE REPRESENTATIVE"
    for pat, rep in ((r"UNITED STATES REP\b", "U S HOUSE"), (r"^U S REP\.?\b", "U S HOUSE"),):
        s = re.sub(pat, rep, s)
    # Criminal district attorney/judge. Baseline forms:
    #   office='Criminal', district='Attorney <County> County'
    #   office='Criminal District Judge[,.] <County>', district='1' (court no)
    #   office='Criminal District Attorney', district='' or '<County>'
    # Parser forms ('Dem Criminal District Judge Court 5', county-stripped
    # titles) are normalized onto the same key; the county itself is injected
    # by the caller (county_name) when absent.
    if s == "CRIMINAL":
        s = "CRIMINAL DISTRICT ATTORNEY"
        d = re.sub(r"^\s*ATTORNEY\b", "", (district or "").upper()).strip()
        d = re.sub(r"\s+COUNTY\b", "", d).strip()
        district = d or (district or "").strip()
    mcd = re.match(r"^CRIMINAL DISTRICT (JUDGE|ATTORNEY)[,. ]+(.+)$", s)
    if mcd:
        s = f"CRIMINAL DISTRICT {mcd.group(1)}"
        rest = mcd.group(2)
        mc = re.search(r"COURT\s*(?:NO\.?\s*)?(\d+)", rest)
        if mc:
            district = district or mc.group(1)
    s = re.sub(r"^CRIMINAL DISTRICT ATTORNEY\b(.*)$", r"CRIMINAL DISTRICT ATTORNEY", s)
    m2 = re.match(r"^CRIMINAL DISTRICT ATTORNEY[,. ]+(.+)$", s)
    if m2:
        s = "CRIMINAL DISTRICT ATTORNEY"
        d = re.sub(r"[^A-Z0-9]+", " ", m2.group(1).upper().replace("_COUNTY", " COUNTY")).strip()
        district = d or district
    if s == "CRIMINAL DISTRICT ATTORNEY" and not (district or "").strip():
        district = county_name  # county reported implicitly
    # Dallas truncation: 'Family District Judge 301st Judicial',
    # 'Judge 116th Judicial' (the word DISTRICT is cut off)
    s = re.sub(r"^FAMILY\s+DIST(RICT)?\s+JUDGE", "DISTRICT JUDGE", s)
    mdj = re.match(r"^(?:DISTRICT |FAMILY DISTRICT |[A-Z]+ )?JUDGE[,.]?\s*(\d+)(ST|ND|RD|TH)?\s+JUDICIAL\.?\s*$", s)
    if mdj is None:
        mdj = re.match(r"^(?:FAMILY DISTRICT )?JUDGE[,.]?\s*(\d+)(ST|ND|RD|TH)?\s+JUDICIAL\.?$", s)
    if mdj and not (district or "").strip():
        district = mdj.group(1) + " JD"
        s = "DISTRICT JUDGE"
    # District judges: 'Judge, 154th Judicial District' <-> 'District Judge'
    m3 = re.match(r"^(?:DISTRICT )?JUDGE[,\s]+(\d+)\s+JUDICIAL\s+DISTRICT\b\s*$", s)
    if m3 and not district:
        district = m3.group(1) + " JD"
    s = re.sub(r"^(?:DISTRICT )?JUDGE[,\s]+(\d+)\s+JUDICIAL\s+DISTRICT\b", "DISTRICT JUDGE", s)
    s = re.sub(r"^\s*JUDGE\s+(?=\d)", "DISTRICT JUDGE ", s)
    # Courts of appeals: baseline 'Justice 13th Court of Appeals District' +
    # district '6'; parser form carries 'Place 6' inside the office text.
    s = re.sub(r"COURT OF APPEALS(?!\s+DISTRICT)(\s+|$)", "COURT OF APPEALS DISTRICT ", s)
    s = s.rstrip(" ")
    mcoa = re.match(r"^(?:(?:CHIEF )?JUSTICE[,.]?\s*)?(\d+)(ST|ND|RD|TH)?\s+COURT OF APPEALS DISTRICT"
                    r"(?:[,.]?\s*(?:PLACE|PL\.?|P)\s*(\d+))?(\s.*)?$", s)
    if mcoa:
        s = f"{mcoa.group(1)} COURT OF APPEALS DISTRICT"
        coa_place = mcoa.group(3)
        coa_tail = mcoa.group(4) or ""
        if coa_place and coa_place not in (district or ""):
            district = (district or "") + (" PLACE " + coa_place)
        if "UNEXPIRED" in coa_tail.upper() and district:
            district += " UNEXPIRED"
    s = re.sub(r"^(?:CHIEF )?JUSTICE,?\s+(?=\d)", "", s)
    s = re.sub(r"^\s*JUDGE\s+(?=COURT OF CRIMINAL APPEALS)", "", s)
    # 'Judge, Supreme Court, Place 8' — the role prefix has no place meaning
    s = re.sub(r"^\s*JUDGE,?\s+(?=SUPREME COURT)", "", s)
    s = re.sub(r"\bSPREME\b", "SUPREME", s)  # Hockley's 'Justice Spreme Court'
    msc = re.match(r"^(?:CHIEF )?JUSTICE\s+SUPREME COURT[,.]?\s*PLACE\s*(\d+)(.*)$", s)
    if msc:
        s = "SUPREME COURT"
        tail = msc.group(2) or ""
        district = (district or "") + (" PLACE " + msc.group(1))
        if "UNEXPIRED" in tail.upper() and district:
            district += " UNEXPIRED"
    mcca = re.match(r"^(?:CHIEF )?(?:JUDGE|JUSTICE)\s+COURT OF CRIMINAL APPEALS[,.]?\s*"
                    r"(?:PLACE|PL\.?|P)\s*(\d+)(.*)$", s)
    if mcca:
        s = "COURT OF CRIMINAL APPEALS"
        district = (district or "") + (" PLACE " + mcca.group(1))
    s = re.sub(r"^(?:CHIEF )?JUSTICE,?\s+(?=\d)", "", s)
    s = re.sub(r"^\s*JUSTICE\s+(?=\d)", "", s)
    s = re.sub(r"^\s*JUSTICE\s+(?=SUPREME COURT)", "", s)
    s = re.sub(r"\bUNEXPIRED( TERM)?\b", "", s)
    # U.S. representative / house
    s = re.sub(r"U\.?\s?S\.?\s+REPRESENTATIVE", "U S HOUSE", s)
    s = re.sub(r"UNITED STATES REPRESENTATIVE", "U S HOUSE", s)
    s = re.sub(r"U\.?\s?S\.?\s+SENAT", "US SENATE", s)
    s = re.sub(r"UNITED STATES SENAT", "US SENATE", s)
    if re.search(r"\bHOUSE\b", s):
        s = "U S HOUSE"
    mreph = re.match(r"^(?:STATE )?REP\.?\s+D(?:IST|ISTRICT)\.?\s*(\d+)$", s)
    if mreph:
        s = "STATE REPRESENTATIVE"
        if not (district or "").strip():
            district = mreph.group(1)
    s = re.sub(r"[^A-Z0-9]+", " ", s).strip()
    d = district or ""
    d = re.sub(r"\b(\d+)(?:ST|ND|RD|TH)\b", r"\1", d.upper())
    d = re.sub(r"\bUNEXPIRED( TERM)?\b", "", d)
    d = re.sub(r"JUDICIAL DISTRICT", "JD", d)
    d = re.sub(r"^\s*PLACE\s*", "", d.strip())
    d = re.sub(r"[^A-Z0-9]+", " ", d).strip()
    return (s, d)


def office_key(office, district="", county_name=""):
    return canon_office(office, district, county_name)


def load_baseline(path=None):
    path = path or BASELINE_DEFAULT
    cand = {}          # (county, office, district, party, candidate) -> votes or None
    totals = {}        # (county, office, district) -> Total-row value
    corrupt_rows = set()   # (county, office) with corrupt rows
    with open(path) as fh:
        for r in csv.DictReader(fh):
            k = (r["county"], r["office"], (r["district"] or "").strip(),
                 (r["party"] or "").strip(), (r["candidate"] or "").strip())
            if k[4] == "Total":
                try:
                    totals[k[:3]] = int(r["votes"].replace(",", ""))
                except ValueError:
                    pass
                continue
            try:
                v = int(r["votes"].replace(",", ""))
            except ValueError:
                v = None
                corrupt_rows.add((r["county"], r["office"]))
            cand[k] = v
    return cand, totals, corrupt_rows


def load_precinct(path):
    """Returns (cand_sums, office_sums, over_under_sums, n_rows).

    REGISTERED VOTERS / BALLOTS CAST rows are skipped. OVER/UNDER VOTES rows
    are kept in cand_sums but excluded from office_sums; their sums are
    reported separately so advisory total diffs can be explained.
    """
    sums_c = defaultdict(int)
    sums_o = defaultdict(int)
    ovu = defaultdict(lambda: [0, 0])  # office key -> [over, under]
    rows = 0
    bad_rows = []
    mm = re.match(r"20140304__tx__primary(?:__\w+)?__([a-z_]+)__precinct", os.path.basename(path))
    c_name = (mm.group(1).upper().replace("_", " ") if mm else "")
    with open(path) as fh:
        for r in csv.DictReader(fh):
            if not (r["office"] or "").strip():
                continue
            if r["office"].upper().startswith(("REGISTERED VOTERS - TOTAL", "BALLOTS CAST - ")):
                continue
            vs = str(r["votes"]).replace(",", "").strip()
            if not vs or not re.fullmatch(r"-?\d+", vs):
                bad_rows.append(f"{r['precinct']}|{r['office']}|{r['candidate']}|{r['votes']!r}")
                continue
            rows += 1
            v = int(vs)
            k = office_key(r["office"].strip(), (r["district"] or "").strip(), c_name)
            c = (r["candidate"] or "").upper()
            sums_c[k + ((r["party"] or "").strip(), name_key(r["candidate"]))] += v
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
    m = re.match(r"20140304__tx__primary(?:__\w+)?__([a-z_]+)__precinct", county)
    if m:
        c_name = m.group(1).upper().replace("_", " ")
    else:
        c_name = None
    if c_name is None:
        return {"error": f"cannot infer county from {county}"}

    offices = {}
    for tot_key, tot_v in totals.items():
        if tot_key[0] == c_name:
            offices[office_key(tot_key[1], tot_key[2], c_name)] = tot_v
    base_cands = {}
    for ckey, cval in cand.items():
        if ckey[0] == c_name and ckey[4]:
            k = office_key(ckey[1], ckey[2], c_name) + (ckey[3], name_key(ckey[4]))
            base_cands[k] = cval

    # no-punctuation fallback for candidate names ('Harper-Brown' vs 'HarperBrown')
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
        "zero_override": [],   # baseline 0 vs precinct >0, office totals tie out
        "reconstructed_ok": 0,
        "bad_rows": bad_rows,
    }
    results["offices_missing"] = [k for k in results["offices_missing"]
                                  if not k[0].startswith(PROP_SENTINEL)
                                  and offices.get(k, 0) > 0]
    results["offices_extra"] = [k for k in results["offices_extra"]
                                if not k[0].startswith(PROP_SENTINEL)]

    corrupt_office_keys = {office_key(o, "", c_name) for (_, o) in corrupt_rows if _ == c_name}
    for okey, t in sorted(offices.items()):
        if okey[0].startswith(PROP_SENTINEL):
            continue
        got = sums_o.get(okey, 0)
        o, u = ovu.get(okey, (0, 0))
        if okey in corrupt_office_keys:
            good = sum(cv for kkey, cv in base_cands.items()
                       if kkey[:2] == okey and cv is not None)
            if got < max(good, t):
                results["total_mismatch"].append((okey, got, max(good, t)))
        elif abs((got + o) - (t + u)) > 2:
            results["total_row_diffs"].append((okey, got, t))
    # candidate-level
    for ckey, cval in sorted(base_cands.items()):
        okey = ckey[:2]
        if okey[0].startswith(PROP_SENTINEL):
            continue
        if ckey[3] in ("OVER VOTES", "UNDER VOTES"):
            continue
        got = sums_c.get(ckey, None)
        if got is None and ckey[3]:
            got = alt_c.get(ckey[:3] + (re.sub(r"[^A-Z]", "", ckey[3]),), None)
        if cval is None:
            continue
        if got == cval:
            continue
        if cval == 0 and got is not None and got > 0:
            t = offices.get(okey)
            if t is not None:
                o, u = ovu.get(okey, (0, 0))
                if abs((sums_o.get(okey, 0) + o) - (t + u)) <= 2:
                    results["zero_override"].append((ckey[2], ckey[3], got))
                    continue
        results["candidate_mismatch"].append((ckey[2], ckey[3], got, cval))
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
            print(f"   CAND {mm[0]} | {mm[1]}: precinct={mm[2]} baseline={mm[3]}")
        for mm in r["zero_override"][:4]:
            print(f"   ZERO-OVERRIDE {mm[0]} | {mm[1]}: precinct={mm[2]} (baseline 0, totals tie)")
    if args.json_report:
        with open(args.json_report, "w") as fh:
            json.dump(report, fh, indent=1, default=str)


if __name__ == "__main__":
    main()
