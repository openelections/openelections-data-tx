#!/usr/bin/env python3
"""Wide / pivoted spreadsheet handlers for the May 29, 2012 Texas primary —
counties whose export is a candidate-rows × precinct-columns table (or a
transposed variant).

Layouts handled (one handler per family; see 2012/20120529__precinct_
verification_report.md):

  * `candidate_rows`: race blocks down the first text column, candidate rows
    below, precinct labels in a header row (bowie, hockley, hansford, cass...).
  * Per-sheet phases: a county may ship EARLY / ELECTION DAY / COMBINED
    sheets or separate files; the merge policy is either 'additive' (sum the
    phases) or 'sheets' (use the sheet named / last COMBINED sheet only).

Usage:
  uv run python3 python-parsers/parse_2012_wide.py -c Bowie \
      -o 2012/counties/20120529__tx__primary__bowie__precinct.csv SRC...
"""
import argparse
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from helpers_2026 import normalize_office, precinct_name, write_county_csv  # noqa: E402
from parse_2012_asc import expand_2012  # noqa: E402
import parse_2012_excel as _px  # noqa: E402  (load_sheets, party from name)

FIELDNAMES = ["county", "precinct", "office", "district", "party", "candidate", "votes"]

NUM_RE = re.compile(r"-?\d[\d,]*(\.\d+)?$")


def lab_name(s):
    s = precinct_name(re.sub(r"\.0+$", "", str(s).strip()))
    return s


def num(v):
    s = str(v if v is not None else "").strip().replace(",", "")
    if not s or not NUM_RE.match(s):
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    if 0 < f < 1 and not f.is_integer():
        return None
    return int(round(f))


PCTISH = re.compile(r"^\d{1,3}[A-Z]?(/\d{1,3}[A-Z]?)*$|^\d{1,3}\s+[A-Z].*$|^[A-Z]?\d+\s*\w*$"
                    r"|^(PCT|PRECINCT)\s+[^,]{1,14}$", re.I)


def precinctish(s):
    s = s.strip()
    if not s or len(s) > 24:
        return False
    return bool(PCTISH.match(s)) or re.fullmatch(r"(\d+[A-Z]?\s*)+[/-]?(\s*[A-Z][a-z]+)?", s) \
        or re.fullmatch(r"\d+(\.0+)?", s)


def phase_of(name, head_txt):
    t = f"{name} {head_txt}".upper()
    if "EARLY" in t and "VOTE" in t.replace("TOTAL", "") and "COMBINED" not in t:
        return "early"
    if "COMBINED" in t or "TOTAL" in t:
        return "total"
    if "ELECTION DAY" in t or "ELECTION" in t:
        return "ed"
    return None


def parse_candidate_rows(name, sheet, county, cfg):
    """Race blocks down a text column; candidate rows beneath; precinct
    labels in a header row. cfg keys (all optional):
      label_row   index of the row carrying precinct labels (found if absent)
      label_col   first column holding precinct labels (auto)
      race_col    column holding the race title (auto: first text column)
      cand_col    column holding candidate names (defaults to race_col)
      skip_sheets sheets to ignore
      phase       force a phase for this file/sheet ('' disables phases)
      total_col   county-total column to ignore (bowie 'Early Votes' col)
    Returns records {office, district, candidate, label, votes, phase}."""
    out = []
    label_row = cfg.get("label_row")
    label_col = cfg.get("label_col")
    race_col = cfg.get("race_col")
    cand_col = cfg.get("cand_col")
    skip_sheets = cfg.get("skip_sheets", ())
    skip_re = re.compile(cfg.get("skip_sheet_re", r"200\d-"), re.I)
    total_col = cfg.get("total_col")

    # skip junk sheets (2008 primaries etc.)
    head_txt = " ".join(str(c) for row in sheet[:6] for c in row if c)
    if re.search(skip_re, head_txt):
        return out
    if name in skip_sheets:
        return out
    phase = cfg.get("phase")
    if phase is None:
        # a stray 'TOTAL' column label in the header band must not mark the
        # whole sheet as a totals sheet; look at the file name and the first
        # two columns only
        lead_txt = " ".join(str(row[ci]).strip() for row in sheet[:3]
                            for ci in (0, 1) if ci < len(row) and row[ci])
        phase = phase_of(name, lead_txt)
    if phase == "total" and cfg.get("merge") != "sheets":
        return out

    # ---- find the label row / label columns
    if label_row is None and cfg.get("label_row_before_re"):
        for i, row in enumerate(sheet[:14]):
            c0 = str(row[0]).strip() if row and row[0] else ""
            if re.search(cfg["label_row_before_re"], c0, re.I) and i > 0:
                label_row = i - 1
                break
    if label_row is None:
        # candidate rows often look like label rows too; prefer rows whose
        # labels are NOT purely numeric (headers), then the earliest row
        best = (None, [])
        for i, row in enumerate(sheet[:12]):
            labs = [(c, str(v).strip()) for c, v in enumerate(row)
                    if v not in (None, "") and str(v).strip() not in ("None",)]
            labs = [(c, s) for c, s in labs
                    if (label_col is None or c >= label_col) and precinctish(s)]
            if len(labs) >= 3:
                span = labs[-1][0] - labs[0][0] + 1
                if span <= len(labs) * 2 + 2:  # roughly contiguous
                    nonnum = sum(1 for _, s in labs if not re.fullmatch(r"\d+(\.0+)?", s))
                    cur_nonnum = sum(1 for _, s in best[1] if not re.fullmatch(r"\d+(\.0+)?", s)) \
                        if best[1] else -1
                    if (nonnum, -i) > (cur_nonnum, -i):
                        best = (i, labs)
        if best[0] is None:
            return out
        label_row, labs = best
    else:
        labs = [(c, str(v).strip()) for c, v in enumerate(sheet[label_row])
                if v not in (None, "") and str(v).strip() != "None"]
    if not labs:
        return out
    opening_race = str(sheet[label_row][0]).strip() \
        if label_row < len(sheet) and race_col is None else None
    if not opening_race or precinctish(opening_race) or \
            re.search(r"ELECTION|EARLY|TOTAL", opening_race, re.I):
        opening_race = None
    if label_col is None:
        label_col = labs[0][0]
    # duplicate precinct labels (hansford prints '5' twice): keep the column
    # with the most populated cells (the other is usually an empty stray)
    def n_filled(c):
        return sum(1 for row in sheet if len(row) > c and row[c] not in (None, ""))
    by_lab = {}
    for c, s in labs:
        if c < label_col:
            continue
        lab = lab_name(s)
        cur = by_lab.get(lab)
        if cur is None or n_filled(c) > n_filled(cur[0]):
            by_lab[lab] = (c, s)
    col_map = {c: lab for lab, (c, s) in by_lab.items()}
    raw_labels = {c: s for lab, (c, s) in by_lab.items()}
    excl = cfg.get("exclude_label_re")
    col_map = {c: lab for c, lab in col_map.items()
               if c > (cand_col if cand_col is not None else -1)
               and not (excl and re.search(excl, lab, re.I))
               and lab.upper() not in ("TOTAL", "TOTALS", "EARLY VOTE", "EARLY VOTES", "EV")}
    cw = cfg.get("countywide_col_re")
    cw_cols = {}
    if cw:
        scan = list(col_map.items()) + \
            [(c, str(sheet[label_row][c]).strip()) for c in range(len(sheet[label_row]))
             if c not in col_map and sheet[label_row][c] not in (None, "")
             and str(sheet[label_row][c]).strip() != "None"]
        for c, lab in scan:
            if re.search(cw, lab, re.I) and c not in cw_cols:
                cw_cols[c] = lab
                col_map.pop(c, None)
                raw_labels.setdefault(c, lab)
    if len(col_map) < 2:
        return out

    # ---- walk the blocks
    race = opening_race
    started = bool(opening_race)
    for i, row in enumerate(sheet):
        if label_row is not None and i <= label_row:
            continue
        cells = list(row) + [None] * 3
        c0 = str(cells[0]).strip() if cells[0] not in (None, "") else ""
        if cand_col is not None:
            cand = str(cells[cand_col]).strip() if cells[cand_col] not in (None, "") else ""
        else:
            cand = c0
        rtxt = c0 if not cand_col else (str(cells[race_col]).strip() if race_col is not None and cells[race_col] not in (None, "") else "")
        # race rows are text rows with no (non-total) numeric values
        nums = {ci: v for ci, v in enumerate(cells) if num(v) is not None}
        nums = {ci: v for ci, v in nums.items() if ci not in (total_col,) and ci in col_map}
        # a race row repeats the precinct labels in the label columns
        # (hockley: 'PRESIDENT | 14 | 15 | 16 ...')
        lab_vals = [str(cells[c]).strip() if c < len(cells) else None
                    for c in col_map]
        if raw_labels and lab_vals == [raw_labels[c] for c in col_map]:
            if c0:
                race = c0
                started = True
            continue
        cand_txt = cand.strip()
        if cand_txt in ("", "None"):
            if rtxt:
                race = rtxt
                started = True
            continue
        if cand_txt.upper() in ("TOTAL", "TOTAL VOTES", "ALL PRECINCTS"):
            continue
        if not nums:
            race = rtxt or cand_txt
            started = True
            continue
        # a race-title row that also carries candidate + votes in other
        # columns (hansford) updates the race and falls through as the
        # candidate row
        if rtxt and rtxt != cand_txt:
            race = rtxt
            started = True
        if race is None:
            race = rtxt or cand_txt
        for c, lab in col_map.items():
            v = num(cells[c]) if c < len(cells) else None
            if v is None:
                continue
            out.append({"office": race, "district": "", "candidate": cand_txt,
                        "precinct": lab, "votes": v, "phase": phase or ""})
        for c in cw_cols:
            v = num(cells[c]) if c < len(cells) else None
            if v is None:
                continue
            out.append({"office": race, "district": "", "candidate": cand_txt,
                        "precinct": "Absentee", "votes": v, "phase": "",
                        "party": None, "party2": None})
    return out


def parse_fixed_cols(name, sheet, county, cfg):
    """One row per candidate with fixed party/race/candidate columns; the
    precincts are columns labeled in a header row (terry, cass) and/or an
    explicit per-row total column (willacy). childress-style sheets combine
    their Type rows (Early / Election Day / Total)."""
    out = []
    party_col = cfg.get("party_col")
    race_col = cfg.get("race_col", 0)
    cand_col = cfg.get("cand_col", 1)
    label_row = cfg.get("label_row")
    vote_from = cfg.get("vote_from")
    total_col = cfg.get("total_col")
    type_col = cfg.get("type_col")
    skip_sheets = cfg.get("skip_sheets", ())
    skip_re = re.compile(cfg.get("skip_sheet_re", r"200\d-"), re.I)
    head_txt = " ".join(str(c) for row in sheet[:6] for c in row if c)
    if re.search(skip_re, head_txt) or name in skip_sheets:
        return out
    if label_row is None and vote_from is None:
        for i, row in enumerate(sheet[:4]):
            cells = [(c, v) for c, v in enumerate(row) if v not in (None, "") and str(v) != "None"]
            nums = [(c, v) for c, v in cells if isinstance(v, (int, float))
                    or re.fullmatch(r"\d+(\.0+)?", str(v).strip())]
            if len(nums) >= 3 and nums[0][0] >= 1:
                label_row, vote_from = i, nums[0][0]
                break
    if label_row is None and vote_from is not None:
        label_row = 0
    if label_row is None and vote_from is None:
        return out
    # per-row TOTAL column (willacy): the row's total column is the vote
    if total_col is not None and type_col is None:
        for i, row in enumerate(sheet):
            if i <= (label_row or 0):
                continue
            cells = list(row) + [None] * 4
            cand = str(cells[cand_col]).strip() if cells[cand_col] not in (None, "") else ""
            race = str(cells[race_col]).strip() if cells[race_col] not in (None, "") else ""
            if not cand or not race:
                continue
            votes = num(cells[total_col]) if total_col < len(cells) else None
            if votes is None:
                continue
            party = str(cells[party_col]).strip() if party_col is not None and cells[party_col] not in (None, "") else ""
            out.append({"office": race, "district": "", "candidate": cand,
                        "precinct": "County Total", "votes": votes, "phase": "total",
                        "party": party or None, "party2": party or None})
        return out
    labs = [(c, str(v).strip()) for c, v in enumerate(sheet[label_row])
            if v not in (None, "") and str(v) != "None"]
    col_map = {}
    for c, s in labs:
        if vote_from is not None and c < vote_from:
            continue
        if total_col is not None and c == total_col:
            continue
        col_map[c] = lab_name(s)
    if not col_map and not total_col:
        # no header labels (terry DEM): emit with column indexes; labels are
        # filled in from a source that has them
        for i, row in enumerate(sheet):
            cells = list(row) + [None] * 4
            cand = str(cells[cand_col]).strip() if cells[cand_col] not in (None, "") else ""
            race = str(cells[race_col]).strip() if cells[race_col] not in (None, "") else ""
            if not cand:
                continue
            if race and race.upper() == "TOTAL":
                continue
            votes = {}
            for c in range(vote_from, min(len(cells), vote_from + 20)):
                v = num(cells[c])
                if v is not None:
                    votes[c] = v
            if not votes:
                continue
            party = None
            if party_col is not None and cells[party_col] not in (None, ""):
                party = {"D": "DEM", "R": "REP"}.get(
                    str(cells[party_col]).strip().upper())
            out.append({"office": race, "district": "", "candidate": cand,
                        "precinct": None, "_cidx": votes, "votes": 0, "phase": "",
                        "party": party, "party2": party})
        return out
    last_race = None
    type_groups = {}
    type_keep = []
    for i, row in enumerate(sheet):
        if i <= label_row:
            continue
        cells = list(row) + [None] * 4
        cand = str(cells[cand_col]).strip() if cells[cand_col] not in (None, "") else ""
        race = str(cells[race_col]).strip() if cells[race_col] not in (None, "") else ""
        if cand and (not race or race.upper() in ("TOTAL",)) and last_race:
            race = last_race
        if race:
            if race.upper() == "TOTAL":
                race = last_race
            else:
                last_race = race
        if not cand:
            continue
        if cand.upper() == "TOTAL":
            continue
        party = None
        if party_col is not None and cells[party_col] not in (None, ""):
            party = {"D": "DEM", "R": "REP"}.get(str(cells[party_col]).strip().upper())
        if type_col is not None:
            tval = str(cells[type_col] or "").strip()
            tnum = {c: num(cells[c]) for c in col_map if c < len(cells)}
            pk = (race, cand)
            if re.match(r"TOTAL", tval, re.I):
                for c, lab in col_map.items():
                    v = tnum.get(c)
                    if v is not None:
                        type_keep.append({"office": race, "district": "",
                                          "candidate": cand, "precinct": lab,
                                          "votes": v, "phase": "total",
                                          "party": party, "party2": party})
                continue
            g = type_groups.setdefault(pk, {"sum": defaultdict(int)})
            for c, lab in col_map.items():
                v = tnum.get(c)
                if v is not None:
                    g["sum"][lab] += v
            continue
        for c, lab in col_map.items():
            v = num(cells[c]) if c < len(cells) else None
            if v is None:
                continue
            out.append({"office": race, "district": "", "candidate": cand,
                        "precinct": lab, "votes": v, "phase": "",
                        "party": party, "party2": party})
    for pk, g in type_groups.items():
        race, cand = pk
        party = None
        for lab, v in g["sum"].items():
            out.append({"office": race, "district": "", "candidate": cand,
                        "precinct": lab, "votes": v, "phase": "",
                        "party": party, "party2": party})
    out += type_keep
    return out


def parse_narrow(name, sheet, county, cfg):
    """Hart-template one-row-per-candidate sheets (terrell, parker, concho):
    race/candidate/precinct identified by column; races and precincts carry
    forward on repeated rows."""
    out = []
    cols = cfg["cols"]
    skip_sheets = cfg.get("skip_sheets", ())
    skip_re = re.compile(cfg.get("skip_sheet_re", r"200\d-"), re.I)
    head_txt = " ".join(str(c) for row in sheet[:6] for c in row if c)
    if re.search(skip_re, head_txt) or name in skip_sheets:
        return out
    start = cfg.get("start_row", 0)
    last_race = last_pct = None
    for i, row in enumerate(sheet):
        if i < start:
            continue
        cells = list(row) + [None] * 30
        def cell(role):
            c = cols.get(role)
            return cells[c] if c is not None and c < len(cells) else None
        cand = str(cell("candidate") or "").strip()
        if not cand or cand in ("None",):
            # candidate continuation rows with blank names: skip
            continue
        race = str(cell("race") or "").strip()
        if race:
            last_race = race
        pct = cell("precinct")
        pct_s = str(pct).strip() if pct not in (None, "") else ""
        if pct_s:
            last_pct = pct_s
        cand_u = cand.upper()
        if cand_u in ("TOTAL", "TOTAL VOTES", "OVER VOTES", "UNDER VOTES") \
                or cand_u.startswith("REGISTERED"):
            continue
        votes = num(cell("votes"))
        if votes is None:
            ev = num(cell("early")) or 0
            ed = num(cell("election"))
            if ev == 0 and ed is None:
                continue
            votes = ev + (ed or 0)
        party = str(cell("party") or "").strip().upper()
        party = {"D": "DEM", "R": "REP"}.get(party, party or None)
        pct_lab = precinct_name(lab_name(last_pct or "0")) if last_pct else "0"
        out.append({"office": last_race or "", "district": "",
                    "candidate": cand, "precinct": pct_lab,
                    "votes": votes, "phase": "", "party": party,
                    "party2": party})
    return out


def parse_named_cols(name, sheet, county, cfg):
    """Candidate-rows races but votes in NAMED columns (willacy: EARLY /
    ELECTION DAY / TOTAL in the label row)."""
    out = []
    race_col = cfg.get("race_col", 0)
    label_row = cfg.get("label_row", 0)
    total_col = cfg.get("total_col")
    start = label_row + 1
    race = None
    for i, row in enumerate(sheet):
        if i < start:
            continue
        cells = list(row) + [None] * 12
        c0 = str(cells[race_col]).strip() if cells[race_col] not in (None, "") else ""
        nums_present = any(num(v) is not None for c, v in enumerate(cells)
                           if c >= (total_col or 0) and num(v) is not None                            and (total_col is None or True))
        has_nums = any(num(v) is not None for v in cells)
        if c0 and not has_nums:
            race = c0
            continue
        if c0 and has_nums and total_col is not None:
            votes = num(cells[total_col])
            if votes is None:
                continue
            out.append({"office": race or c0, "district": "", "candidate": c0,
                        "precinct": "County Total", "votes": votes,
                        "phase": "total", "party": None, "party2": None})
        elif not c0:
            continue
    return out


def parse_transposed(name, sheet, county, cfg):
    """Brewster-style: precincts down the rows, candidates across the
    columns, race blocks spread horizontally over a title row with candidate
    first/last names stacked beneath."""
    out = []
    title_row = cfg.get("title_row", 3)
    name_rows = cfg.get("name_rows", (4, 5))
    precinct_col = cfg.get("precinct_col", 0)
    data_from = cfg.get("data_from", 6)
    # map column -> (race, candidate)
    colinfo = {}
    cur_race = None
    for c in range(1, len(sheet[title_row])):
        t = str(sheet[title_row][c] or "").strip()
        if t:
            cur_race = re.sub(r"\s+", " ", t)
        f = str(sheet[name_rows[0]][c] or "").strip() if name_rows[0] < len(sheet) else ""
        l = str(sheet[name_rows[1]][c] or "").strip() if name_rows[1] < len(sheet) else ""
        if not l and not f:
            continue
        name = re.sub(r"\s+", " ", (l + " " + f) if l else f).strip()
        if name:
            colinfo[c] = (cur_race, name)
    for i, row in enumerate(sheet):
        if i < data_from:
            continue
        cells = list(row) + [None] * 4
        pcv = cells[precinct_col]
        pct = lab_name(pcv) if pcv not in (None, "") else None
        if pct is None and num(pcv) is None:
            continue
        for c, (race, cand) in colinfo.items():
            v = num(cells[c]) if c < len(cells) else None
            if v is None:
                continue
            out.append({"office": race, "district": "", "candidate": cand,
                        "precinct": pct, "votes": v, "phase": "",
                        "party": None, "party2": None})
    return out


HANDLERS = {
    # county slug -> (kind, cfg)
    "bowie": ("candidate_rows", {"merge": "additive", "total_col": 1}),
    "hockley": ("candidate_rows", {"merge": "sheets"}),
    "hansford": ("candidate_rows", {"merge": "sheets", "label_col": 4, "cand_col": 2,
                                    "race_col": 0}),
    "willacy": ("fixed_cols", {"race_col": 0, "cand_col": 0, "total_col": 8,
                               "label_row": 0}),
    "terry": ("fixed_cols", {"party_col": 0, "race_col": 1, "cand_col": 2}),
    "cass": ("fixed_cols", {"race_col": 0, "cand_col": 1, "vote_from": 4,
                            "label_row": 0, "sheets": ("TOTALS",)}),
    "childress": ("fixed_cols", {"race_col": 1, "cand_col": 1, "party_col": 2,
                                 "type_col": 3, "vote_from": 0}),
    "concho": ("narrow", {"cols": {"precinct": 0, "race": 10, "candidate": 14,
                                   "votes": 19}, "start_row": 1}),
    "parker": ("narrow", {"cols": {"precinct": 3, "race": 13, "candidate": 17,
                                   "votes": 22}, "start_row": 1}),
    "terrell": ("narrow", {"cols": {"precinct": 5, "race": 7, "candidate": 8,
                                    "early": 10, "election": 12},
                           "start_row": 2}),
    "oldham": ("candidate_rows", {"race_col": 0, "cand_col": 0, "label_col": 4,
                                  "label_row": 10, "countywide_col_re": r"^VOTE"}),

    "mcmullen": ("candidate_rows", {"race_col": 0, "cand_col": 0,
                                    "merge": "additive",
                                    "label_row_before_re": r"TOTAL REG",
                                    "exclude_label_re": r"^(TOTAL|EARLY VOTE|VOTER|TOTAL REG)"}),
    "panola": ("candidate_rows", {"race_col": 0, "cand_col": 3, "label_col": 5,
                                  "countywide_col_re": r"^EV$",
                                  "exclude_label_re": r"^(TOTAL|EARLY)"}),
    "willacy": ("named_cols", {"race_col": 0, "label_row": 0, "total_col": 8}),
    "brewster": ("transposed", {"title_row": 3, "name_rows": (4, 5),
                                "precinct_col": 0, "data_from": 6}),
}


def merge_records(county, recs):
    slug = county.lower().replace(" ", "_").split("@")[0]
    merge = HANDLERS[slug][1].get("merge") if slug in HANDLERS else None
    if merge != "additive":
        # keep only rows from 'total'/'ed' phases: prefer total, else ed
        phased = defaultdict(list)
        for r in recs:
            phased[(r["office"], r["candidate"], r["precinct"])].append(r)
        out = []
        for k, rs in phased.items():
            for want in ("total", "ed"):
                pick = [r for r in rs if r["phase"] == want]
                if pick:
                    out.append(pick[0])
                    break
            else:
                out.append(rs[0])
        return out
    # additive: sum the phase values per (office, candidate, precinct)
    sums = defaultdict(lambda: [0, None, False])
    for r in recs:
        k = (r["office"], r["district"], r["candidate"], r["precinct"])
        sums[k][0] += r["votes"]
        if r.get("party"):
            sums[k][1] = r["party"]
        elif sums[k][1] is None and r.get("party2"):
            sums[k][1] = r["party2"]
        if r.get("_repaired"):
            sums[k][2] = True
    return [{"office": o, "district": d, "candidate": c, "precinct": p, "votes": v,
             "phase": "", "party": pa, "_repaired": rep}
            for (o, d, c, p), (v, pa, rep) in sums.items()]


_ORDINALS = {n: f"{n}th" for n in range(2, 16)}
_ORDINALS.update({2: "2nd", 3: "3rd"})


def canon_to_display(s, d):
    """Turn a canonical office key back into (office_text, district_text)."""
    if s == "PRESIDENT":
        return "President", ""
    if s == "US SENATE":
        return "U.S. Senate", ""
    if s == "U S HOUSE":
        return "U.S. House", d or ""
    if s == "SUPREME COURT":
        return "Supreme Court", ("Place " + d if d else "")
    if s == "COURT OF CRIMINAL APPEALS":
        return ("Court of Criminal Appeals", "" if d == "PRESIDING"
                else ("Place " + d if d else ""))
    if s == "RAILROAD COMMISSIONER UNEXPIRED":
        return "Railroad Commissioner Unexpired Term", ""
    if s == "RAILROAD COMMISSIONER":
        return "Railroad Commissioner", ""
    if s == "STATE SENATE":
        return "State Senate", d or ""
    if s == "STATE REPRESENTATIVE":
        return "State Representative", d or ""
    if s == "STATE BOARD OF EDUCATION":
        return "State Board of Education", d or ""
    if s == "DISTRICT JUDGE":
        return "District Judge", d or ""
    if s == "DISTRICT ATTORNEY":
        return "District Attorney", d or ""
    m = re.match(r"^(CHIEF JUSTICE )?(\d+) COURT OF APPEALS DISTRICT$", s)
    if m:
        n = int(m.group(2))
        who = m.group(1) or "Justice "
        return (f"{who}{_ORDINALS.get(n, n)} Court of Appeals District".strip(),
                "Place " + d if d else "")
    return None


def _lev1(a, b):
    """True when two tokens differ by one edit (typos in truncated exports)."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1 or len(a) < 4:
        return False
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    return a[i + (1 if len(a) > len(b) else 0):] == b[i:]


def repair_offices(recs, county):
    """County-side races whose office text is fragmented/unreliable get their
    office from the SOS baseline by candidate name (statewide candidates are
    unambiguous)."""
    from verify_2012 import load_baseline, name_key_2012, base_office, precinct_office
    cand, _t, _c = load_baseline()
    nm = county.upper()
    by_name = {}
    ambiguous = set()
    for (cnty, s, d, party, name), v in cand.items():
        if cnty != nm or not name:
            continue
        k = name_key_2012(name)
        if k in by_name and by_name[k] != (s, d, party):
            ambiguous.add(k)
        by_name[k] = (s, d, party)
    # counties listing candidates by surname only need a surname index
    surnames = {}
    amb_s = set()
    firsts = {}
    amb_f = set()
    for (cnty, s_, d_, party_, name_), v in cand.items():
        if cnty != nm or not name_:
            continue
        key = name_key_2012(name_)
        parts = key.split()
        if not parts:
            continue
        k = (parts[-1], party_)
        if k in surnames and surnames[k] != (s_, d_):
            amb_s.add(k)
        surnames[k] = (s_, d_)
        f0 = (parts[0], party_)
        lst = firsts.setdefault(f0, [])
        lst.append((key, s_, d_))
    # first-token groups with two or more distinct offices are ambiguous
    for f0, lst in firsts.items():
        if len(lst) >= 2:
            amb_f.add(f0)
    n = 0
    for r in recs:
        k = name_key_2012(r["candidate"])
        hit = None
        if k in by_name and k not in ambiguous:
            hit = by_name[k]
        else:
            parts = k.split()
            if parts:
                sk = (parts[-1], r.get("party"))
                if sk in surnames and sk not in amb_s:
                    hit = surnames[sk]
                elif len(parts) >= 2:
                    fk = (parts[0], r.get("party"))
                    if fk in surnames and fk not in amb_s and parts[0] not in ("BOB",):
                        hit = surnames[fk]
        if hit is None and r.get("party"):
            # single-character surname typos (Hunstman/Santorum/Poll): party-
            # scoped unique lev-1 surname match
            parts = k.split()
            if parts[-1] in ("JR", "II", "III") and len(parts) >= 2:
                parts = parts[:-1]
            tok = parts[-1]
            if len(tok) >= 4:
                hits2 = [(s2, d2) for (kk, s2, d2) in
                         [(kk, sd[0], sd[1]) for kk, sd in surnames.items() if kk[1] == r.get("party")]
                         if kk != 'DUMMY' and _lev1(tok, kk[0]) and not (kk, r.get("party")) in amb_s]
                hits2 = [(s2, d2) for kk, s2, d2 in
                         ((kk, sd[0], sd[1]) for kk, sd in surnames.items()
                          if kk[1] == r.get("party"))
                         if _lev1(tok, kk[0]) and (kk, r.get("party")) not in amb_s
                         and kk[0] != tok]
                if len(hits2) == 1:
                    hit = (hits2[0][0], hits2[0][1], r.get("party"))
        if hit is None:
            # truncated name lists (oldham '   MITT ', terrell surnames): match
            # the (party-scoped) surname token, else the first token, allowing
            # a partial second token ('JOHN D' -> John Davis). When the row's
            # (unrepaired) office text resolves to a baseline office, restrict
            # the fallback to the candidates of that office.
            parts = k.split()
            scope = None
            raw_office = r.get("office") or ""
            oc = None
            try:
                oc = precinct_office(raw_office, r.get("district") or "", nm)
            except Exception:
                oc = None
            if oc:
                hits_oc = {kc2 for kc2, cv in cand.items()
                           if kc2[0] == nm and kc2[1] == oc[0] and kc2[2] == oc[1]}
                if hits_oc:
                    scope = hits_oc
            def in_scope(s_, d_):
                return scope is None or (s_, d_) in scope
            if parts:
                if scope is not None and len(scope) == 1:
                    # the row's office pins the race: accept the unique
                    # party match inside the office when the name is unique
                    cand_hits = [kc2 for kc2 in scope
                                 if kc2[3] == (r.get("party") or None)
                                 or not any(m[3] == kc2[3] for m in scope)]
                    matches = [e for e in cand.items()
                               if (e[0][0], e[0][1], e[0][2]) in scope
                               and (e[0][3] == (r.get("party") or None))]
                    if len(matches) == 1:
                        hit = (matches[0][0][1], matches[0][0][2], matches[0][0][3])
                if hit is None:
                    sk = (parts[-1], r.get("party"))
                    if sk in surnames and sk not in amb_s and in_scope(*surnames[sk][:2]):
                        hit = surnames[sk]
                    elif len(parts) >= 2:
                        fk = (parts[0], r.get("party"))
                        if fk not in amb_f and fk in firsts:
                            cands = firsts[fk]
                            t1 = parts[1]
                            hits = [e for e in cands if e[0].split()[1].startswith(t1)] \
                                if len(cands) > 1 else cands
                            hits = [e for e in hits if in_scope(e[1], e[2])]
                            if len(hits) == 1:
                                hit = (hits[0][1], hits[0][2], r.get("party"))
                if hit is None and len(parts) == 1:
                    fk = (k, r.get("party"))
                    if fk not in amb_f and fk in firsts:
                        cands = [e for e in firsts[fk] if in_scope(e[1], e[2])]
                        if len(cands) == 1:
                            hit = (cands[0][1], cands[0][2], r.get("party"))
        if hit is None:
            continue
        s_, d_ = hit[0], hit[1]
        disp = canon_to_display(s_, d_)
        if disp:
            r["office"], r["district"] = disp
            r["_repaired"] = True
            n += 1
    return n


def run_county(county, out, sources):
    cfg, kind = {}, None
    if county.lower().replace(" ", "_") in HANDLERS:
        kind, cfg = HANDLERS[county.lower().replace(" ", "_")]
    recs = []
    seen_sigs = set()
    import hashlib
    seen_md5 = {}
    for src in list(sources):
        h = hashlib.md5(open(src, "rb").read()).hexdigest()
        if h in seen_md5:
            print(f"skipping {os.path.basename(src)} (identical to {seen_md5[h]})")
            sources.remove(src)
            continue
        seen_md5[h] = os.path.basename(src)
    for src in sources:
        try:
            sheets = _px.load_sheets(src)
        except Exception as e:
            print(f"{os.path.basename(src)}: load error {e}")
            continue
        pre = n_before = len(recs)
        party = None
        import parse_2014_asc as _base
        party = _base.party_from_filename(src, "")
        low = os.path.basename(src).lower()
        local_cfg = dict(cfg)
        kind_local = kind or "candidate_rows"
        only_sheets = local_cfg.pop("sheets", None)
        for name, sheet in sheets:
            if only_sheets and not re.search(r"|".join(only_sheets), name, re.I):
                continue
            if kind_local == "candidate_rows":
                recs += parse_candidate_rows(name, sheet, county, local_cfg)
            elif kind_local == "fixed_cols":
                recs += parse_fixed_cols(name, sheet, county, local_cfg)
            elif kind_local == "narrow":
                recs += parse_narrow(name, sheet, county, local_cfg)
            elif kind_local == "named_cols":
                recs += parse_named_cols(name, sheet, county, local_cfg)
            elif kind_local == "transposed":
                recs += parse_transposed(name, sheet, county, local_cfg)
        sig = tuple(sorted((str(r["precinct"]), str(r["office"]),
                            str(r["candidate"]), r["votes"]) for r in recs[pre:]))
        if sig in seen_sigs:
            print(f"{os.path.basename(src)}: duplicate signature of an earlier "
                  f"source ({len(recs) - pre} rows), skipped")
            del recs[pre:]
            continue
        seen_sigs.add(sig)
        print(f"{os.path.basename(src)}: {len(recs) - pre} wide rows, party={party}")
        for r in recs[pre:]:
            r["party"] = r.get("party") or party
    if not recs:
        print(f"-- {county}: wide parse found nothing")
        return 0
    # exact duplicate rows across sources (counties whose party files both
    # carry both parties' tables): keep the first
    seen_rows = set()
    ded = []
    for r in recs:
        k = (r["precinct"], r["office"], r["candidate"], r["votes"],
             r.get("phase") or "", r.get("party") or "")
        if k in seen_rows and not r.get("_cidx"):
            continue
        seen_rows.add(k)
        ded.append(r)
    if len(ded) != len(recs):
        print(f"  dropped {len(recs) - len(ded)} exact duplicate rows")
    recs = ded
    n_rep = repair_offices(recs, county)
    recs = merge_records(county, recs)
    rows = []
    for r in recs:
        if r.get("_repaired"):
            office, district = r["office"], r["district"]
        else:
            title = _r_clean(r["office"])
            res = normalize_office(title)
            office, district = (res[0], res[1] if len(res) > 1 else "") if res else (title, "")
        rows.append({"county": county, "precinct": r["precinct"], "office": office,
                     "district": district, "party": r["party"],
                     "candidate": r["candidate"], "votes": r["votes"]})
    write_county_csv(out, county, rows, FIELDNAMES)
    print(f"wrote {out}: {len(rows)} rows")
    return len(rows)


def _r_clean(title):
    t = re.sub(r"\s+", " ", str(title or "").strip())
    t = re.sub(r"\s*\(.{0,20}(?:VOTES|TOTAL).{0,10}\)\s*$", "", t, flags=re.I)
    return expand_2012(_px_strip_party(t))


def _px_strip_party(t):
    t = re.sub(r"^(?:Dem|Rep)\s+", "", t, flags=re.I)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--county", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("sources", nargs="+")
    args = ap.parse_args()
    run_county(args.county, args.out, args.sources)


if __name__ == "__main__":
    main()
