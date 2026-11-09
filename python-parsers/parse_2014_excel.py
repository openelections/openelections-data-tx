#!/usr/bin/env python3
"""Parse Hart 'Detail Vote Totals'-style spreadsheets (xlsx/xls) from the
March 4, 2014 Texas primary into per-county precinct CSVs.

Recognized shapes (one row per precinct x race x candidate), column names
located by scanning the first ~8 rows for a header containing 'precinct':

  A) 'political_subdivision ... precinct_number reg_voters race_name
     candidate_name party_code early_votes election_votes'
  B) 'PRECINCT # | RACE NAME | CANDIDATE'S NAME | EARLY VOTES |
     ELECTION DAY VOTES ...'

Anything else prints a sample and is skipped (handled per county later).

Usage:
  uv run python3 python-parsers/parse_2014_excel.py -c Fayette \
      -o 2014/counties/20140304__tx__primary__fayette__precinct.csv SRC.xlsx...
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers_2026 import normalize_office, precinct_name, write_county_csv  # noqa: E402

FIELDNAMES = ["county", "precinct", "office", "district", "party", "candidate",
              "votes", "early_voting", "election_day"]

HDR_RE = re.compile(r"precinct", re.I)


def norm_header(h):
    h = re.sub(r"[^A-Z0-9 ]", " ", str(h).upper()).strip()
    h = re.sub(r"\s+", " ", h)
    return h


def header_colmap(candidates, rows_all=None):
    """candidates: list of rows (dicts col index -> value). Returns
    (row_index, {role: col}) for the first plausible header. Wrapped/multi-row
    headers (e.g. 'Political \nSubdivision') are handled by merging up to
    three consecutive rows per column before matching."""
    # try single-row headers first, then merged pairs/triples
    tries = [(ri,) for ri in range(len(candidates))]
    for i in range(len(candidates) - 1):
        tries.append((i, i + 1))
    for i in range(len(candidates) - 2):
        tries.append((i, i + 1, i + 2))
    n = len(rows_all[0]) if rows_all else 40
    for combo in tries:
        row = {}
        for ci in range(n):
            parts = [norm_header(candidates[i].get(ci, "")) for i in combo
                     if ci in candidates[i]]
            t = re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()
            if t:
                row[ci] = t
        merged = row
        cols = {}
        for ci, t in merged.items():
            if False:
                continue
            if re.search(r"\bID\b|\bSEQ\b|\bTYPE\b", t) and not t.startswith("PRECINCT"):
                continue  # e.g. Contest_Id / candidate_id / Candidate_Type
            if re.fullmatch(r"PRECINCT( NUMBER| NO| NO\.| \(.*\))?|PRECINCT #|PCT\.? ?#?", t) \
                    or (t.startswith("PRECINCT ") and len(t) < 20) \
                    or re.fullmatch(r"PCT\.?", t):
                cols.setdefault("precinct", ci)
            elif "RACE" in t or "CONTEST" in t:
                cols.setdefault("race", ci)
            elif "CANDIDATE" in t:
                cols.setdefault("candidate", ci)
            elif re.search(r"EARLY", t) and "VOTE" in t:
                cols.setdefault("early", ci)
            elif (re.search(r"ELECTION", t) or re.search(r"\bED\b", t)) and "VOTE" in t:
                cols.setdefault("election", ci)
            elif re.search(r"TOTAL", t) and "VOTE" in t and "PROV" not in t:
                cols.setdefault("total", ci)
            elif re.search(r"PARTY", t):
                cols.setdefault("party", ci)
            elif "REG" in t and "VOTER" in t:
                cols.setdefault("reg", ci)
            elif "SUBDIV" in t or "POLITICAL" in t:
                cols.setdefault("subdiv", ci)
        if "precinct" in cols and "candidate" in cols and ("race" in cols or "total" in cols):
            base = combo[0]
            return base, cols
    return None, None


def load_sheets(path):
    """Returns (sheet_name, rows) for every nonempty sheet. Trailing all-empty
    rows are trimmed (large SOS exports pad the sheet to the sheet-size cap)."""
    def trim(rows):
        while rows and all(c in (None, "") for c in rows[-1]):
            rows.pop()
        return rows

    if path.lower().endswith((".xlsx", ".xlsm")):
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        out = []
        for name in wb.sheetnames:
            ws = wb[name]
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            if any(any(c not in (None, "") for c in r) for r in rows):
                out.append((name, trim(rows)))
        wb.close()
        return out
    import xlrd
    wb = xlrd.open_workbook(path)
    out = []
    for name in wb.sheet_names():
        sh = wb.sheet_by_name(name)
        rows = [sh.row_values(r) for r in range(sh.nrows)]
        if any(any(str(c).strip() or (isinstance(c, float)) for c in r) for r in rows):
            out.append((name, trim(rows)))
    return out


def to_int(v):
    """int() that tolerates floats-as-strings ('2.0') and comma thousands."""
    s = str(v or "").replace(",", "").strip()
    if not s:
        return ""
    try:
        return int(s)
    except ValueError:
        try:
            return int(float(s))
        except ValueError:
            return ""


def hart_without_header(rows):
    """Fallback for headerless Hart/SOS exports (e.g. Cooke: the data rows
    carry the 'political_subdivision .. early_votes election_votes' layout of
    the standard 11-13 column template with no label row). Returns (ri, cols)
    where cols maps roles to column indexes."""
    def is_num(v):
        return isinstance(v, (int, float)) or re.fullmatch(r"\d[\d.]*", str(v or "").strip())

    def is_str(v):
        s = str(v or "").strip()
        return bool(s) and bool(re.search(r"[A-Za-z]", s))

    for ri, row in enumerate(rows[:12]):
        if len(row) < 12:
            continue
        c0, c7, c8, c10, c11 = row[0], row[7], row[8], row[10], row[11]
        nxt = rows[ri + 1] if ri + 1 < len(rows) else []
        # require the shape to repeat on the next nonblank row (excludes wide
        # pct-by-pct tables whose candidate names fill adjacent columns)
        nx_ok = False
        for nrow in ([nxt] if nxt else []) + rows[ri + 2:ri + 6]:
            if any(c not in (None, "") for c in nrow[:6]) and is_str(nrow[0] if len(nrow) > 0 else None) \
                    and is_str(nrow[7] if len(nrow) > 7 else None) \
                    and is_str(nrow[8] if len(nrow) > 8 else None):
                nx_ok = True
                break
        if is_str(c0) and is_str(c7) and is_str(c8) and (is_num(c10) or c10 in (None, "")) \
                and (is_num(c11) or c11 in (None, "")) and is_num(row[5]) and nx_ok:
            return ri, {"subdiv": 0, "precinct": 5, "race": 7, "candidate": 8,
                        "party": 9, "early": 10, "election": 11}
    return None, None


def parse(path, county):
    out = []
    used = []
    errs = []
    early_present = None
    for sheet_name, rows in load_sheets(path):
        cand_rows = [{i: v for i, v in enumerate(row[:40]) if v not in (None, "")}
                     for row in rows[:24]]
        ri, cols = header_colmap(cand_rows, rows)
        if cols is None:
            ri, cols = hart_without_header(rows)
        if cols is None:
            errs.append(sheet_name)
            continue
        used.append(sheet_name)
        early_present = early_present or ("early" in cols)
        last_race = None
        for row in rows[ri + 1:]:
            def get(c, row=row):
                return (row[cols[c]] if c in cols and cols[c] < len(row) else None)
            pct = get("precinct")
            race = get("race")
            cand = get("candidate")
            if pct in (None, ""):
                continue
            if race not in (None, "") and str(race).strip():
                last_race = race
            elif race in (None, ""):
                race = last_race  # block layout repeats the race only on its first row
            pct_s = str(pct).strip()
            if re.fullmatch(r"\d+\.0+", pct_s):
                pct_s = pct_s.split(".")[0]
            cand_s = re.sub(r"\s+", " ", str(cand or "").strip())
            if not cand_s:
                continue
            race_s = re.sub(r"\s+", " ", str(race or "").strip())
            if not race_s:
                continue
            total = get("total")
            ev = to_int(get("early"))
            edv = to_int(get("election"))
            votes = to_int(total)
            if votes == "" and ev == "" and edv == "":
                continue  # candidate row with no vote data
            if votes == "":
                votes = (ev or 0) + (edv or 0)
            party = str(get("party") or "").strip().upper()
            party = {"D": "DEM", "R": "REP", "DEM": "DEM", "REP": "REP",
                     "DEMOCRATIC": "DEM", "REPUBLICAN": "REP"}.get(party, party)
            if party not in ("DEM", "REP"):
                # some counties' exports leave the party column empty; assign
                # each candidate the party the county-level file gives them
                from parse_2014_wide import cand_office_map
                from verify_2014 import name_key
                look = cand_office_map().get(name_key(cand_s))
                if look:
                    party = look[0][2]
            res = clean_titles(race_s) or normalize_office(race_s)
            if res:
                office, district = (res[0], res[1] if len(res) > 1 else "")
            else:
                office, district = race_s, ""
            rec = {
                "county": county,
                "precinct": precinct_name(pct_s),
                "office": office,
                "district": district,
                "party": party,
                "candidate": cand_s,
                "votes": votes,
            }
            if early_present:
                rec["early_voting"] = ev
                rec["election_day"] = edv
            out.append(rec)
    if not used:
        return None, f"no recognizable header; sheet heads: {errs} / {[s[0] for s in load_sheets(path)]}"
    if not out:
        # every candidate sheet matched a header but yielded no data rows
        return None, "sheets matched but produced no data rows"
    return out, None


def apply_county_quirks(county, recs):
    """Per-county source corrections (documented in the verification report)."""
    c = county.lower().replace(" ", "_")
    for r in recs:
        if c == "oldham":
            # the source increments the district number on every row of the
            # U.S. House block; the race is District 13
            if (r["office"] or "").startswith("U.S. House"):
                try:
                    d = int(r["district"])
                    if 13 <= d <= 33:
                        r["district"] = "13"
                except (TypeError, ValueError):
                    pass
        if c == "wood":
            if str(r["office"]).strip() == "District Attorney":
                r["office"] = "Criminal District Attorney"
    return recs


def smart_expand(title):
    """Expand the heavy abbreviations some county canvass exports use
    ('Chief Just, Sup Ct', 'Jdg, Ct Crim App, Pl 3', 'US Rep, Dist 5')."""
    t = title
    for pat, rep in (
        (r"\bUS\s+REP\b", "US Representative"),
        (r"\bSUP\s+CT\b", "Supreme Court"),
        (r"\bCT\s+CRIM\s+APP\b", "Court of Criminal Appeals"),
        (r"\bCRIM\s+APP\b", "Criminal Appeals"),
        (r"\bCT\s+APP\b\.?", "Court of Appeals"),
        (r"\bJDG\b", "Judge"),
        (r"\bJUST\b", "Justice"),
        (r"\bCOMM\b\.?", "Commissioner"),
        (r"\bOFC\b", "Office"),
        (r"\bGEN\b", "General"),
        (r"\bDIST\b\.?", "District"),
        (r"\bCOMP\b", "Comptroller"),
        (r"\bCRM\b", "Criminal"),
        (r"\bPUB\s+ACCTS\b", "Public Accounts"),
        (r"\bLT\s+GOV\b", "Lieutenant Governor"),
        (r"\bLIEUTENEANT\b", "Lieutenant"),
        (r"\bSTATE\s+REP\b", "State Representative"),
    ):
        t = re.sub(pat, rep, t, flags=re.I)
    return t


def clean_titles(title):
    from parse_2014_asc import clean_title
    from helpers_2026 import expand_abbrevs, title_case_office
    t = clean_title(str(title).strip(), "")
    t = smart_expand(t)
    res = normalize_office(t)
    if res:
        return (res[0], res[1] if len(res) > 1 else "")
    return title_case_office(expand_abbrevs(t)), ""


def run_county(county, out, sources):
    all_rows = []
    failed = []
    seen_sigs = set()
    for src in sources:
        rows, err = parse(src, county)
        if err:
            print(f"{os.path.basename(src)}: ERROR {err}")
            failed.append(os.path.basename(src))
            continue
        sig = tuple(sorted((r["precinct"], r["office"], r["district"], r["party"],
                            r["candidate"], r["votes"]) for r in rows))
        if sig in seen_sigs:
            print(f"{os.path.basename(src)}: duplicate of an earlier source ({len(rows)} rows), skipped")
            continue
        seen_sigs.add(sig)
        print(f"{os.path.basename(src)}: {len(rows)} rows")
        all_rows += rows
    if not all_rows:
        print(f"-- {county}: nothing parsed; no file written (sources: {failed})")
        return 0
    all_rows = apply_county_quirks(county, all_rows)
    fieldnames = list(FIELDNAMES)
    if any("early_voting" in r for r in all_rows):
        fieldnames = FIELDNAMES
    write_county_csv(out, county, all_rows, fieldnames)
    print(f"wrote {out}: {len(all_rows)} rows" + (f" (failed: {failed})" if failed else ""))
    return len(all_rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--county", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("sources", nargs="+")
    args = ap.parse_args()
    run_county(args.county, args.out, args.sources)


if __name__ == "__main__":
    main()
