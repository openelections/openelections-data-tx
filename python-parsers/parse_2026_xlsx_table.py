#!/usr/bin/env python3
"""Parse the 2026 primary Excel exports into precinct-level CSVs.

Two layouts are supported:

* Collin-style table: one row per precinct, one column per racexcandidate.
  Row 0 = race titles repeated per candidate column, row 1 = party markers,
  row 2 = candidate names (with 'OVER VOTES'/'UNDER VOTES' columns), row 3+ =
  precinct rows. OVER/UNDER VOTES columns are dropped.

* Terrell-style transposed table: rows = candidates, stacked vote-method
  groups as columns ('ABSENTEE BY MAIL' / 'EV IN PERSON' / 'ELECTION DAY' /
  'TOTAL'), each group spanning the precinct columns ('PCT 1' ... in row 1).
  Race titles are single rows between '*****' separators.

Usage:
  uv run python3 python-parsers/parse_2026_xlsx_table.py -c COUNTY -o OUT.csv SOURCE.xlsx ...
"""

import argparse
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers_2026 import normalize_office, precinct_name, write_county_csv  # noqa: E402

FIELDNAMES = ["county", "precinct", "office", "district", "party", "candidate",
              "votes", "absentee", "early_voting", "election_day", "provisional", "limited"]

SKIP_NAMES = {"OVER VOTES", "UNDER VOTES", "OVERVOTES", "UNDERVOTES"}


def load_rows(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            rows.append(list(row))
    return rows


def is_party_marker(v):
    return isinstance(v, str) and re.fullmatch(r"(REP|DEM|NON|LIB|GRN)", v.strip().upper() or v)


def normalize_party(v):
    v = (v or "").strip().upper()
    return {"REP": "REP", "R": "REP", "DEM": "DEM", "D": "DEM", "NON": "NON",
            "LIB": "LIB", "GRN": "GRN"}.get(v, v)


def strip_party_prefix(t):
    return re.sub(r"^(?:REPUBLICAN|DEMOCRATIC|NONPARTISAN|REP|DEM)\s+", "", t.strip(), flags=re.I)


# ---------------------------------------------------------------- Collin layout

def parse_collin_style(rows, county):
    hidx = None
    for i, r in enumerate(rows[:6]):
        if any(isinstance(c, str) and re.search(r"PRECINCT\s*(CODE|NUMBER)", c or "", re.I) for c in r):
            hidx = i
            break
    if hidx is None:
        return []
    title_row = rows[hidx]
    party_row = rows[hidx + 1]
    cand_row = rows[hidx + 2]
    records = []
    cur_title = None
    for j in range(len(title_row)):
        t = str(title_row[j]).strip() if title_row[j] is not None else ""
        party = normalize_party(party_row[j]) if j < len(party_row) else "NON"
        name = str(cand_row[j]).strip() if j < len(cand_row) else ""
        if t:
            cur_title = t
        if not name or name.upper() in SKIP_NAMES:
            continue
        if re.search(r"REGISTERED VOTERS|BALLOTS CAST", (cur_title or ""), re.I):
            continue  # ballot-count columns, not races
        if clean(name).lower() in ("none", "nan") or "PRECINCT CODE" in (cur_title or "").upper():
            continue  # header leakage rows
        norm = normalize_office(strip_party_prefix(cur_title or ""))
        office, district = norm if norm else (clean_title(cur_title), "")
        records.append((j, office, district, party, clean(name)))
    records_data = []
    for r in rows[hidx + 3 :]:
        code = r[1] if len(r) > 1 else None
        if code is None or not str(code).strip() or re.search(r"TOTAL|\bZZ\w*", str(code), re.I):
            continue
        prec = precinct_name(str(code).strip().replace(".0", ""))
        for j, office, district, party, name in records:
            if len(r) <= j:
                continue
            v = r[j]
            if v is None or str(v).strip() == "":
                continue
            try:
                votes = int(float(str(v).replace(",", "")))
            except ValueError:
                continue
            records_data.append({
                "precinct": prec, "office": office, "district": district,
                "party": party, "candidate": name, "votes": str(votes),
            })
    return records_data


def clean(s):
    return re.sub(r"\s+", " ", str(s or "").strip())


def clean_title(t):
    return re.sub(r"\s+", " ", str(t or "").replace("#", " ")).strip()


# --------------------------------------------------------------- Terrell layout

def normalize_method_label(label):
    if "MAIL" in label or "ABSEN" in label:
        return "absentee"
    if "EV " in label + " " or "EARLY" in label or "EV" == label.strip():
        return "early_voting"
    if "ELECTION" in label or "ED" == label.strip():
        return "election_day"
    if "TOTAL" in label:
        return "votes"
    if "PROVIS" in label:
        return "provisional"
    if "LIMIT" in label:
        return "limited"
    return None


def parse_terrell_style(rows):
    """Rows = candidates; column groups = vote methods spanning the precinct
    columns ('PCT 1'... in the row above the separator). Returns grouped records."""
    pct_row_idx = None
    for i, r in enumerate(rows[:10]):
        vals = [str(c).upper() if c is not None else "" for c in r]
        if sum(v.startswith("PCT") for v in vals) >= 2:
            pct_row_idx = i
            break
    if pct_row_idx is None:
        return []
    flat0 = " ".join(str(c) for c in rows[0] if c is not None).upper()
    party = ("REP" if "REPUBLICAN" in flat0 or "REP " in flat0 else "DEM")
    # method groups: contiguous column runs tagged by the non-empty label in row 0;
    # a group extends from its label to just before the next label
    labels = [(j, str(c).upper().strip()) for j, c in enumerate(rows[0]) if c is not None]
    groups = []
    for g_i, (j0, label) in enumerate(labels):
        j1 = labels[g_i + 1][0] - 1 if g_i + 1 < len(labels) else len(rows[0]) - 1
        groups.append((label, j0, j1))
    # per column: method key + precinct (from the PCT row), and the last
    # untagged column in a group named TOTAL is the county-wide total column
    col_method = {}
    col_precinct = {}
    for label, j0, j1 in groups:
        key = normalize_method_label(label)
        if key is None:
            continue
        pct_cols = [j for j in range(min(j0, j1), j1 + 1)
                    if j < len(rows[pct_row_idx]) and rows[pct_row_idx][j] is not None
                    and str(rows[pct_row_idx][j]).upper().startswith("PCT")]
        for j in range(min(j0, j1), j1 + 1):
            if key == "votes" and not pct_cols:
                col_method.pop(j, None)  # county-wide total column; never emitted
            elif j < len(rows[pct_row_idx]) and rows[pct_row_idx][j] is not None:
                pval = str(rows[pct_row_idx][j]).upper().strip()
                if pval.startswith("PCT"):
                    col_method[j] = key
                    col_precinct[j] = precinct_name(pval)
    records = []
    race = None
    for i in range(pct_row_idx + 1, len(rows)):
        r = rows[i]
        c0 = clean(r[0]).upper() if r and r[0] is not None else ""
        if not c0:
            continue
        if re.search(r"(SENAT|REPRESENTATIVE|GOVERNOR|JUDGE|COURT(?!NEY)|COMMISSION|"
                     r"BOARD|ATTORNEY|SHERIFF|CLERK|TREASURER|CONSTABLE|CHAIR|PROP)", c0, re.I):
            race = c0
            continue
        if "*" in c0 or "TOTAL" in c0:
            race = None if "TOTAL" in c0 else race
            continue
        if race is None:
            continue
        name = clean(r[0])
        for j, key in col_method.items():
            if len(r) <= j or r[j] is None or r[j] == "":
                continue
            try:
                v = int(str(r[j]).replace(",", ""))
            except (ValueError, TypeError):
                continue
            prec = col_precinct[j] or "NA"
            rec = records_entry(race, party, name, prec)
            if key == "votes":
                rec["votes"] = str(v)
            else:
                rec[key] = str(v)
            records.append(rec)
    # combine one record per (precinct, office, party, candidate)
    grouped = {}
    for rec in records:
        k = (rec["precinct"], rec["office"], rec["party"], rec["candidate"])
        g = grouped.setdefault(k, {"precinct": rec["precinct"], "office": rec["office"],
                                   "district": "", "party": rec["party"],
                                   "candidate": rec["candidate"], "votes": "",
                                   "absentee": "", "early_voting": "",
                                   "election_day": "", "provisional": "", "limited": ""})
        for f in ("absentee", "early_voting", "election_day", "provisional", "limited"):
            if rec.get(f):
                g[f] = rec[f]
        if rec.get("votes"):
            g["votes"] = rec["votes"]
    out = [g for g in grouped.values()]
    for g in out:
        if not g["votes"]:
            g["votes"] = str(sum(int(g[f] or 0) for f in
                                 ("absentee", "early_voting", "election_day",
                                  "provisional", "limited")))
    # county-wide total columns (no precinct) are not emitted; they only verify
    return out


def records_entry(race, party, name, prec):
    norm = normalize_office(strip_party_prefix(race))
    office, district = norm if norm else (clean_title(race), "")
    return {"precinct": prec, "office": office, "district": district,
            "party": party, "candidate": name, "votes": ""}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--county", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--layout", choices=["collin", "terrell", "auto"], default="auto")
    args = ap.parse_args()
    records = []
    for src in args.sources:
        rows = load_rows(src)
        layout = args.layout
        if layout == "auto":
            head = [c for r in rows[:4] for c in r if c is not None]
            layout = "collin" if any(isinstance(c, str) and re.search(r"PRECINCT\s*(CODE|NUMBER)", c, re.I) for c in head) else "terrell"
        if layout == "collin":
            records.extend(parse_collin_style(rows, args.county))
        else:
            records.extend(parse_terrell_style(rows))

    write_county_csv(args.out, args.county, records, FIELDNAMES)
    print(f"{args.county}: wrote {len(records)} rows -> {args.out}")


if __name__ == "__main__":
    main()