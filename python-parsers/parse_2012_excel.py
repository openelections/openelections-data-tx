#!/usr/bin/env python3
"""Run the 2014 Hart-style excel parser over the 2012 May primary sources,
with 2012 fixes:

  * some .xls files are really xlsx (PK zip header) — parsed with openpyxl;
  * 2012 exports often omit the party column — the party is recovered from the
    county-level SOS baseline by candidate name (each candidate appears in a
    single party's primary), with a keyword fallback for the 2012 ballot
    propositions;
  * 'President/VicePresident' titles are normalized to match the baseline.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_2014_excel as _xl  # noqa: E402
from helpers_2026 import write_county_csv  # noqa: E402
from verify_2012 import name_key_2012  # noqa: E402
import csv  # noqa: E402

BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir,
                        "2012", "20120529__tx__primary__county.csv")

PROP_KEYWORDS = (
    (re.compile(r"PRAYER", re.I), ("REP", 3)),
    (re.compile(r"SCHOOL CHOICE|PARENTS", re.I), ("REP", 1)),
    (re.compile(r"OBAMACARE|PATIENT PROTECTION|AFFORDABLE CARE", re.I), ("REP", 2)),
    (re.compile(r"LIMITING.*SPENDING|SPENDING|BALANCED BUDGET|CONTROLLING GOVERNMENT", re.I), ("REP", 4)),
    (re.compile(r"REDRAW|REDISTRICTING|REAPPORTION|LEGISLATIVE DISTRICTS", re.I), ("REP", 5)),
    (re.compile(r"GAMBLING|CASINO", re.I), ("DEM", 3)),
    (re.compile(r"COLLEGES|TUITION", re.I), ("DEM", 2)),
    (re.compile(r"HIGH SCHOOL GRADUATE|LEGAL STATUS", re.I), ("DEM", 1)),
)


def build_name_party_map():
    """name_key -> party, plus (candidate, office-ish) entries kept for props."""
    party = {}
    with open(BASELINE) as fh:
        for r in csv.DictReader(fh):
            c = (r["candidate"] or "").strip()
            p = (r["party"] or "").strip().upper()
            if not c or c == "Total" or not p:
                continue
            party[name_key_2012(c)] = p
    return party


def prop_party(office_text, candidate):
    for pat, (p, _n) in PROP_KEYWORDS:
        if pat.search(office_text or ""):
            return p
    return ""


import parse_2012_asc
pe_expand = parse_2012_asc.expand_2012


def fix_parties(rows, name_party):
    for r in rows:
        # many 2012 exports write the party at the end of the race title
        # ('President DEM', 'Sheriff REP') instead of a party column
        o = r.get("office") or ""
        m = re.search(r"[\s,.]-?\s*(DEM|REP|DEMOCRATIC|REPUBLICAN|REPUBLICAN PARTY|"
                      r"DEMOCRATIC PARTY)\s*$", o, re.I)
        if m:
            r["office"] = re.sub(r"[\s,.]-?\s*(?:DEM|REP|DEMOCRATIC|REPUBLICAN(?:\s+PARTY)?)\s*$",
                                 "", o, flags=re.I).strip(" ,.-")
        p = (r.get("party") or "").strip().upper()
        if p in ("DEM", "REP"):
            r["party"] = p
            continue
        cand = r.get("candidate") or ""
        if cand.upper().startswith(("IN FAVOR", "AGAINST", "OVER", "UNDER", "FOR", "WRITE")) \
                or "PROPOSITION" in (r.get("office") or "").upper():
            r["party"] = prop_party(r.get("office"), cand) or name_party.get(name_key_2012(cand), "")
        else:
            r["party"] = name_party.get(name_key_2012(cand), "") or \
                ("REP" if m and m.group(1).upper().startswith("R") else
                 "DEM" if m and m.group(1).upper().startswith("D") else "")
    return rows


def _read_text_sheet(path):
    """Delimited text exports: one 'sheet' with csv-parsed rows (waller's
    doubled double-quotes normalized)."""
    import csv as _csv, io as _io
    raw = open(path, "r", encoding="latin-1", errors="replace").read()
    name = os.path.basename(path)
    if raw.count('""') > 20 and '"Precinct' not in raw[:4000].replace('""', '"'):
        pass
    # waller-style: the whole file is wrapped once in quotes with doubled
    # quotes inside; collapse them first
    if raw.startswith('"') and '""' in raw[:2000]:
        raw = raw.lstrip('"').rstrip('"').rstrip('"') \
            if raw.rstrip().endswith('"""') else raw.strip('"')
        raw = raw.replace('""', '"')
    sniffer = _csv.Sniffer()
    delim = ","
    try:
        delim = sniffer.sniff(raw[:2000], delimiters=",\t ").delimiter
    except Exception:
        pass
    if "\t" in raw[:2000] and delim == ",":
        delim = "\t"
    rows = list(_csv.reader(_io.StringIO(raw), delimiter=delim))
    rows = [r for r in rows if any(c.strip() for c in r if isinstance(c, str))] if False else rows
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    return [(name, rows)]


def load_sheets(path):
    """Magic-number-based sheet loader (some .xls files are xlsx inside)."""
    with open(path, "rb") as fh:
        head = fh.read(8)
    with open(path, "rb") as fh:
        head2 = fh.read(8)
    if head[:2] not in (b"PK",) and head[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return _read_text_sheet(path)
    if head[:2] == b"PK":
        try:
            import io
            import openpyxl
            with open(path, "rb") as fh:
                buf = io.BytesIO(fh.read())
            wb = openpyxl.load_workbook(buf, data_only=True, read_only=True)
            out = []
            for name in wb.sheetnames:
                ws = wb[name]
                rows = [list(r) for r in ws.iter_rows(values_only=True)]
                if any(any(c not in (None, "") for c in r) for r in rows):
                    out.append((name, rows))
            wb.close()
            return out
        except Exception:
            pass  # fall through to xlrd (mis-titled old .xls)
    import xlrd
    wb = xlrd.open_workbook(path)
    out = []
    for name in wb.sheet_names():
        sh = wb.sheet_by_name(name)
        rows = [sh.row_values(r) for r in range(sh.nrows)]
        if any(any(str(c).strip() or (isinstance(c, float)) for c in r) for r in rows):
            out.append((name, rows))
    return out


def _nm(k):
    return re.sub(r"[^A-Z]", "", k.upper())


def build_base_cand():
    out = {}
    with open(BASELINE) as fh:
        for r in csv.DictReader(fh):
            c = (r["candidate"] or "").strip()
            if not c or c == "Total":
                continue
            try:
                v = int(r["votes"].replace(",", ""))
            except (ValueError, AttributeError):
                continue
            out[(r["county"].upper(), _nm(c))] = v
    return out


def extra_header_cols(head_rows):
    """Bare-label header scan for sheets the 2014 header matcher rejects
    ('Precinct | Candidate | Party | Type | Count')."""
    hdr = [str(x or "").strip() for x in (head_rows[0] if head_rows else [])]
    cols = {}
    for ci, label in enumerate(hdr):
        lu = re.sub(r"[^A-Z ]", " ", label.upper()).strip()
        lu = re.sub(r"\s+", " ", lu)
        if re.fullmatch(r"PRECINCT( NUMBER| NO| NO\.| PCT)?.*|PCT.*", lu.split(" NAME")[0]):
            cols.setdefault("precinct", ci)
        elif "RACE" in lu or lu in ("OFFICE", "CONTEST"):
            cols.setdefault("race", ci)
            if lu == "CANDIDATE" and "OFFICE OFFICE" not in lu:
                pass
        elif "CANDIDATE" in lu and "PARTY" not in lu:
            cols.setdefault("candidate", ci)
        elif "PARTY" in lu and "CODE" in lu or lu == "PARTY":
            cols.setdefault("party", ci)
        elif lu.startswith("COUNT COUNT") or lu.startswith("TOTAL") or lu == "COUNT":
            cols.setdefault("total", ci)
        elif lu.startswith("EARLY") and "DATE" not in lu:
            cols.setdefault("early", ci)
        elif lu.startswith("ELECTION DAY") or lu == "ELECTION" and "DATE" not in lu:
            cols.setdefault("election", ci)
        elif lu in ("TYPE", "COUNT TYPE", "MEANING"):
            cols.setdefault("type", ci)
        if lu.startswith("CANDIDATE NAME"):
            cols["candidate"] = ci
        if re.match(r"RACE NAME|^RACE$|^OFFICE$", lu):
            cols["race"] = ci
        if lu == "PRECINCT_NUMBER":
            cols["precinct"] = ci
        if lu == "COUNT_COUNT":
            cols["total"] = ci
    if "type" in cols and not any(k in cols for k in ("early", "election", "total")):
        return None
    if "type" in cols and ("total" in cols or ("early" in cols and "election" in cols)):
        cols["_combine_type_rows"] = True
    return cols or None


def _iv(v):
    return v if isinstance(v, int) else 0


def _broaden_cols(cols, header_row):
    """Extend a matched 2014 header with bare-label vote columns."""
    if header_row is None:
        return cols
    for ci, label in enumerate(header_row):
        lu = re.sub(r"[^A-Z ]", " ", str(label or "").upper()).strip()
        lu = re.sub(r"\s+", " ", lu)
        if not lu:
            continue
        if lu.startswith("COUNT COUNT") and "total" not in cols:
            cols.setdefault("total", ci)
        elif lu.startswith(("TOTAL", "COUNT OF")) and "TYPE" not in lu and "total" not in cols:
            cols.setdefault("total", ci)
        elif lu.startswith("EARLY") and "early" not in cols and "DATE" not in lu:
            cols.setdefault("early", ci)
        elif (lu.startswith("ELECTION DAY") and "DATE" not in lu) or lu == "ELECTION":
            if "election" not in cols:
                cols.setdefault("election", ci)
        if re.match(r"^(COUNT TYPE|TYPE|MEANING)$", lu):
            cols.setdefault("type", ci)
    if "type" in cols and ("total" in cols or ("early" in cols and "election" in cols)):
        cols["_combine_type_rows"] = True
    return cols


def run_county(county, out, sources):
    global base_cand
    base_cand = build_base_cand()
    name_party = build_name_party_map()

    all_rows, seen_sigs, failed = [], set(), []
    for src in sources:
        sheet_rows, errs = [], []
        early_present = False
        for sheet_name, sheet in load_sheets(src):
            head_txt = " ".join(str(c) for row in sheet[:6] for c in row if c)
            sheet_party = ("REP" if re.search(r"REPUBLICAN\s+PARTY\s+PRIMARY", head_txt, re.I)
                           else "DEM" if re.search(r"DEMOCRATIC\s+PARTY\s+PRIMARY", head_txt, re.I)
                           else "")
            cand_rows = [{i: v for i, v in enumerate(row[:40]) if v not in (None, "")}
                         for row in sheet[:24]]
            ri, cols = _xl.header_colmap(cand_rows, sheet)
            if cols is None:
                ri, cols = _xl.hart_without_header(sheet)
            if cols is None and sheet:
                cols = extra_header_cols(sheet[:4])
                ri = 0
            if cols is not None:
                cols = _broaden_cols(dict(cols), sheet[ri] if ri < len(sheet) else None)
            if cols is None:
                errs.append(sheet_name)
                continue
            type_col = cols.pop("type", None)
            combine_type_rows = cols.pop("_combine_type_rows", False)
            if "early" in cols or "election" in cols or "total" in cols:
                early_present = True
            star_race = None
            last_race = None
            for row in sheet[ri + 1:]:
                def get(c, row=row):
                    return (row[cols[c]] if c in cols and cols[c] < len(row) else None)
                pct = get("precinct")
                race = get("race")
                cand = get("candidate")
                if pct in (None, "") and star_race is None:
                    # Childress-style office marker rows ('****' in col 0)
                    if type_col is not None and (row[0] or "") == "****" and row[1]:
                        star_race = re.sub(r"\s+", " ", str(row[1]).strip())
                    continue
                race_txt = str(race or "").strip()
                if race_txt and race_txt != '"' and race_txt != "None":
                    last_race = race_txt
                race = last_race or star_race
                pct_s = str(pct).strip() if pct not in (None, "****") else ""
                if not pct_s:
                    continue
                if re.fullmatch(r"\d+\.0+", pct_s):
                    pct_s = pct_s.split(".")[0]
                cand_s = re.sub(r"\s+", " ", str(cand or "").strip())
                if not cand_s or cand_s.lower() == "total":
                    continue
                race_s = re.sub(r"\s+", " ", str(race or "").strip())
                if not race_s:
                    continue
                ml = re.match(r"^(DEM|REP|DEMOCRATIC|REPUBLICAN)\b[\s,.-]+", race_s, re.I)
                lead_party = ("REP" if ml.group(1).upper().startswith("R")
                              else "DEM") if ml else ""
                if ml:
                    race_s = re.sub(r"^(DEM|REP|DEMOCRATIC|REPUBLICAN)\b[\s,.-]+",
                                    "", race_s, flags=re.I)
                    if re.search(r"\b(DEM|REP)\b", race_s) is None:
                        pass
                race_s = pe_expand(race_s)
                if re.search(r"RAILROAD|^R\s+R\b", race_s, re.I):
                    race_s = ("Railroad Commissioner Unexpired Term"
                              if re.search(r"UNEXPIRED", race_s, re.I)
                              else "Railroad Commissioner")
                ev = _xl.to_int(get("early"))
                edv = _xl.to_int(get("election"))
                votes = _xl.to_int(get("total"))
                summed = False
                if votes == "" and ev == "" and edv == "":
                    # COUNT_TYPE-style sheets: the count column carries one
                    # count per type row (Early / Election Day)
                    if type_col is not None and cols.get("total") is not None:
                        votes = _xl.to_int(row[cols["total"]]) if cols["total"] < len(row) else ""
                        ev, edv, summed = "", "", False
                    else:
                        continue
                elif votes == "":
                    votes = (ev or 0) + (edv or 0)
                    summed = (ev != "" and edv != "")
                party = str(get("party") or "").strip().upper() or lead_party or sheet_party
                party = {"D": "DEM", "R": "REP", "DEM": "DEM", "REP": "REP",
                         "DEMOCRATIC": "DEM", "REPUBLICAN": "REP"}.get(party, party)
                if re.search(r"RAILROAD", race_s, re.I):
                    office = ("Railroad Commissioner Unexpired Term"
                              if re.search(r"UNEXPIRED", race_s, re.I)
                              else "Railroad Commissioner")
                    district = ""
                else:
                    res = _xl.clean_titles(race_s) or _xl.normalize_office(race_s)
                    office, district = (res[0], res[1] if len(res) > 1 else "") \
                        if res else (race_s, "")
                rec = {"county": county, "precinct": _xl.precinct_name(pct_s),
                       "office": office, "district": district, "party": party,
                       "candidate": cand_s, "votes": votes}
                if summed:
                    rec["_summed"] = True
                    rec["_ed"] = edv
                if combine_type_rows and type_col is not None:
                    tval = str(row[type_col] or "").strip()
                    rec["_type"] = tval
                    rec["_pct_key"] = (rec["precinct"], rec["office"], rec["candidate"])
                if early_present:
                    rec["early_voting"] = ev
                    rec["election_day"] = edv
                sheet_rows.append(rec)
            # combine COUNT_TYPE rows (Early + Election Day -> one row)
            if combine_type_rows and sheet_rows:
                groups = {}
                keep = []
                for r in sheet_rows:
                    tk = str(r.pop("_type") or "")
                    pk = r.pop("_pct_key", None)
                    if tk == "":
                        keep.append(r)
                        continue
                    g = groups.setdefault(pk, {"total": None, "sum": 0,
                                               "ev": 0, "ed": 0})
                    if re.match(r"TOTAL VOTES?|^TOTAL$", tk, re.I):
                        g["total"] = r["votes"]
                    elif re.search(r"ELECTION", tk, re.I):
                        g["sum"] += _iv(r["votes"])
                        g["ed"] += _iv(r["votes"])
                    else:
                        g["sum"] += _iv(r["votes"])
                        g["ev"] += _iv(r["votes"])
                sheet_rows = keep
                for pk, g in groups.items():
                    pct, office, cand = pk
                    votes = g["total"] if g["total"] is not None else g["sum"]
                    if votes in (None, ""):
                        continue
                    rec = {"county": county, "precinct": pct, "office": office,
                           "district": "", "party": "", "candidate": cand,
                           "votes": votes}
                    if early_present:
                        rec["early_voting"] = g["ev"]
                        rec["election_day"] = g["ed"]
                    sheet_rows.append(rec)
        sig = tuple(sorted((r["precinct"], r["office"], r["district"], r["party"],
                            r["candidate"], r["votes"]) for r in sheet_rows))
        # interpretation of 'Election Day' columns that actually hold totals
        summed_rows = [r for r in sheet_rows if r.get("_summed")]
        if summed_rows:
            nA, nB = 0, 0
            for r in summed_rows:
                v = base_cand.get((county.upper(), _nm(r["candidate"])))
                if v is None:
                    continue
                if r["votes"] == v:
                    nA += 1
                if r["_ed"] == v:
                    nB += 1
            if nB > nA:
                for r in summed_rows:
                    r["votes"] = r["_ed"]
                    r["election_day"] = ""
                print(f"  sheet '{sheet_name if False else ''}': 'Election Day' column holds totals "
                      f"({nB} baseline matches vs {nA})")
        for r in sheet_rows:
            r.pop("_summed", None)
            r.pop("_ed", None)
            r.pop("_type", None)
            r.pop("_pct_key", None)
        if not sheet_rows:
            if errs:
                failed.append(os.path.basename(src))
                print(f"{os.path.basename(src)}: ERROR no recognizable header; "
                      f"sheet heads: {errs}")
            continue
        if sig in seen_sigs:
            print(f"{os.path.basename(src)}: duplicate of an earlier source "
                  f"({len(sheet_rows)} rows), skipped")
            continue
        seen_sigs.add(sig)
        print(f"{os.path.basename(src)}: {len(sheet_rows)} rows")
        all_rows += sheet_rows
    # drop exact duplicate rows (workbooks repeating rows across both-party sheets)
    ded = []
    seen_k = set()
    for r in all_rows:
        k = (r["precinct"], r["office"], r["district"], r["party"], r["candidate"], r["votes"])
        if k in seen_k:
            continue
        seen_k.add(k)
        ded.append(r)
    if len(ded) != len(all_rows):
        print(f"  dropped {len(all_rows) - len(ded)} exact duplicate rows across sheets")
    all_rows = ded
    if not all_rows:
        print(f"-- {county}: nothing parsed (sources: {failed})")
        return 0
    all_rows = fix_parties(all_rows, name_party)
    for r in all_rows:
        o = (r.get("office") or "")
        if re.match(r"^President\s*/\s*V", o, re.I):
            r["office"] = "President"
    fieldnames = ["county", "precinct", "office", "district", "party", "candidate", "votes"]
    if any("early_voting" in r for r in all_rows):
        fieldnames = ["county", "precinct", "office", "district", "party", "candidate",
                      "votes", "early_voting", "election_day"]
    write_county_csv(out, county, all_rows, fieldnames)
    print(f"wrote {out}: {len(all_rows)} rows" + (f" (failed: {failed})" if failed else ""))
    return len(all_rows)
