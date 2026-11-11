#!/usr/bin/env python3
"""Parse the May 29, 2012 Texas primary 180-char Hart ASC/.001 files into
per-county precinct CSVs.

Same record layout as 2014 (parse_2014_asc), but the 2012 exports write the
contest titles in heavy abbreviation style that must be expanded first:
'Judge, CT of Criminal AP, P7', 'Member, State BoE, DIST 9',
'Railroad Commissioner, UNEXP', 'DISTRICT ATTORNEY DIST 159'.
Also carries 'Unexpired Term' out of the title into the office text (the
Railroad Commissioner races) and normalizes 'P7'/'Pl 7' place markers.
"""
import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_2014_asc as _base  # noqa: E402
from helpers_2026 import normalize_office, precinct_name, write_county_csv  # noqa: E402


def expand_2012(t):
    """Expand the abbreviated Hart contest-title styles of the 2012 exports.

    Dialects seen: Angelina 'Judge, CT of Criminal AP, P7' / 'DISTRICT ATTORNEY
    DIST 159'; Dallas 'Dem Judge, 14th Judicial District DEM COUNTY WIDE'
    (leading party prefix + repeated party-echo fragment); Bexar 'Justice, 4th
    Crt Appeals Dist, Pl, 2' / 'Presiding Judge, Court Criminal Appeals';
    Cameron 'Presiding Judge, Crt of Criminal Appeals'.
    """
    t = str(t)
    # Dallas-style leading party prefix + trailing party-echo fragment
    # ('Dem Judge, 14th Judicial District DEM COUNTY WIDE'): only strip the
    # echo when the title also leads with a party prefix
    if re.match(r"^(?:Dem|Rep)\s+", t, flags=re.I):
        t = re.sub(r"\s+(?:DEM|REP)\s+(?:COUNTY\s*WIDE|COUNTYWIDE|DIST(?:RICT)?\s*\.?\s*\d+"
                   r"|COMM\s+DIST\w*\s*\d+|PCT\s*\d+)[A-Z ]*$", "", t, flags=re.I)
        t = re.sub(r"^(?:Dem|Rep)\s+", "", t, flags=re.I)
    t = re.sub(r"\s+(?:STATE\s*WIDE|STATEWIDE|FEDERAL)\s*$", "", t, flags=re.I)
    # Williamson-style truncated titles: 'JUSTICE PL 2, 3RD COURT OF'
    t = re.sub(r"\bJUSTICE\s+PL\.?\s*(\d+),?\s*(\d+)(?:ST|ND|RD|TH)?\s+COURT\b.*$",
               r"Justice \2 Court Of Appeals District Place \1", t, flags=re.I)
    t = re.sub(r"\bCrt\b\.?", "COURT", t, flags=re.I)
    t = re.sub(r"\bCT\b\.?", "COURT", t, flags=re.I)
    t = re.sub(r"\bCRT\b\.?", "COURT", t, flags=re.I)
    t = re.sub(r"\bAPPLS\b\.?", "APPEALS", t, flags=re.I)
    t = re.sub(r"\bPRES\s+JUDGE\b", "Presiding Judge", t, flags=re.I)
    t = re.sub(r"\bREPRESENTATIVES\b", "REPRESENTATIVE", t, flags=re.I)
    t = re.sub(r"\bCTOF\s*AP?P?E?A?L?S?\.?\b", "COURT OF APPEALS", t, flags=re.I)
    # 'Court Criminal Appeals' -> 'Court of Criminal Appeals'
    t = re.sub(r"\bCOURT\s+CRIM(?:INAL)?\b\.?", "COURT OF CRIMINAL", t, flags=re.I)
    t = re.sub(r"\bCRIM(?:INAL)?\s+APP?E?A?L?S?\.?\b", "CRIMINAL APPEALS", t, flags=re.I)
    t = re.sub(r"\bCTOF\s*APP?E?A?L?S?\.?\b", "COURT OF APPEALS", t, flags=re.I)
    t = re.sub(r"\bAP?P?E?A?L?S?\.?\b(?!\s*COUNTY)", "Appeals", t, flags=re.I)
    t = re.sub(r"\bCOURT\s+APPEALS\b", "COURT OF APPEALS", t, flags=re.I)
    t = re.sub(r"\bJ\s+DIST\b\.?", "Judicial District", t, flags=re.I)
    t = re.sub(r"\bDIST\b\.?", "DISTRICT", t, flags=re.I)
    t = re.sub(r"\bJUDICIALDISTRICT\b", "Judicial District", t, flags=re.I)
    t = re.sub(r"\bATTY\b\.?", "Attorney", t, flags=re.I)
    t = re.sub(r"\bCR\b\.?", "CRIMINAL", t, flags=re.I)
    t = re.sub(r"\bUNEX(P)?\b\.?(\s+TERM)?", "Unexpired Term", t, flags=re.I)
    t = re.sub(r"\bUS\s+REP\b\.?", "US Representative", t, flags=re.I)
    t = re.sub(r"\bUS\s+CONGRESSIONAL\b", "US Representative", t, flags=re.I)
    t = re.sub(r"\bBOE\b", "State Board Of Education", t, flags=re.I)
    t = re.sub(r"\bAPPEALS?\s+DIS\b\.?", "APPEALS DISTRICT", t, flags=re.I)
    t = re.sub(r"\s+FEDERAL\s*$", "", t, flags=re.I)
    t = re.sub(r"^PREFERENCE FOR (THE )?PRESIDENTIAL NOMINEE", "President", t, flags=re.I)
    t = re.sub(r"\bST\.?\s+BOARD\b", "STATE BOARD", t, flags=re.I)

    t = re.sub(r"\bSUPREME\s+CT\b\.?", "Supreme Court", t, flags=re.I)
    t = re.sub(r"\bSUP\s+CT\b\.?", "Supreme Court", t, flags=re.I)
    t = re.sub(r"\bSUP\s+COURT\b", "Supreme Court", t, flags=re.I)
    t = re.sub(r"\bPL\.?,?\s*(\d+)\b", r"PLACE \1", t, flags=re.I)
    t = re.sub(r"\bP\.?\s?(\d+)\b", r"PLACE \1", t, flags=re.I)
    return t


def _norm_row(county, pct, title, cand, party, votes):
    title_e = _base.clean_title(expand_2012(title), county)
    for cc in (county.upper().replace(" ", "_"), county):
        title_e = re.sub(r"\s+" + re.escape(cc) + r"\s+COUNTY\s*$", "", title_e, flags=re.I)
    res = normalize_office(title_e)
    office, district = (res[0], res[1] if len(res) > 1 else "") if res else (title_e.title(), "")
    if re.search(r"UNEX", title.upper()) and not re.search(
            r"UNEXPIRED", (office + " " + str(district)).upper()):
        office = office + " Unexpired Term"
    return {
        "county": county,
        "precinct": precinct_name(pct) if pct else pct,
        "office": office,
        "district": district,
        "party": party,
        "candidate": cand,
        "votes": votes,
    }


def run_county(county, out, sources, party_default=None):
    import parse_2012_el30
    all_rows, seen, seen_dup = [], {}, 0
    bad_total = []
    uniq_srcs = {}
    for src in sources:
        ext = os.path.basename(src).lower().rsplit(".", 1)[-1]
        h = hashlib.md5(open(src, "rb").read()).hexdigest()
        if h in uniq_srcs:
            print(f"skipping {os.path.basename(src)} (identical to {uniq_srcs[h]})")
            continue
        uniq_srcs[h] = os.path.basename(src)
        fp = _base.party_from_filename(src, party_default or "")
        if ext in ("lst", "wrk"):  # EL30A text report
            n_before = len(all_rows)
            for pct, title, cand, votes, rparty in parse_2012_el30.parse_file(src):
                r = _norm_row(county, pct, title, cand, rparty or fp, votes)
                r["eff_party"] = None
                all_rows.append(r)
            print(f"{os.path.basename(src)}: EL30A text {len(all_rows) - n_before} rows")
            continue
        raw = open(src, encoding="latin-1").read().splitlines()
        rows, bad = _base.parse_lines(raw)
        bad_total += [(os.path.basename(src),) + b for b in bad]
        n_before = len(all_rows)
        for r in rows:
            eff = r["party"].upper()
            if eff not in ("DEM", "REP"):
                eff = ""
            # 2012 exports often ship one file covering both parties: the
            # in-row party label wins over the filename
            key = (eff or fp, r["contest"], r["cand_no"], r["pct_code"], r["label"])
            idx = seen.get(key)
            if idx is not None:
                if r["votes"] > all_rows[idx]["votes"]:
                    # keep the party assignment of the row being replaced
                    r["eff_party"] = all_rows[idx].get("eff_party")
                    all_rows[idx] = r
                seen_dup += 1
                continue
            seen[key] = len(all_rows)
            r["eff_party"] = eff or fp or r["party"]
            all_rows.append(r)
        print(f"{os.path.basename(src)}: {len(rows)} lines, party={fp} "
              f"({len(all_rows) - n_before} new rows, bad={len(bad)})")

    fieldnames = ["county", "precinct", "office", "district", "party", "candidate", "votes"]
    out_rows = []
    for r in all_rows:
        if r.get("eff_party") is None:
            # rows pre-built by the EL30A path already carry party
            out_rows.append(r)
            continue
        out_rows.append(_norm_row(
            county,
            r["pct_name"] if r.get("pct_name") else r["pct_code"],
            r["title"], r["label"],
            r.get("eff_party") or r.get("party"), r["votes"]))
    write_county_csv(out, county, out_rows, fieldnames)
    print(f"wrote {out}: {len(out_rows)} rows "
          f"({seen_dup} duplicate rows dropped, {len(bad_total)} bad lines)")
    for b in bad_total[:8]:
        print("  bad:", b)
