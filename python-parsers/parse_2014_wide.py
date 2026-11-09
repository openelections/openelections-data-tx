#!/usr/bin/env python3
"""Wide / block-table spreadsheet handlers for the March 4, 2014 Texas primary
(counties whose only precinct source is not a one-row-per-candidate export).

Each handler parses one layout family and returns records in the canonical
county CSV columns. Races are emitted with the source's title text; office
canonicalization and repair happen downstream (verify_2014 / repair_2014).

Used as a fallback by build_2014.py's excel flow when parse_2014_excel yields
nothing for a county:
  uv run python3 python-parsers/parse_2014_wide.py -c Cottle \
      -o 2014/counties/20140304__tx__primary__democratic__cottle__precinct.csv SRC.xlsx...
"""
import argparse
import csv as csvmod
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers_2026 import precinct_name, write_county_csv  # noqa: E402
from parse_2014_excel import load_sheets, to_int, clean_titles  # noqa: E402
from verify_2014 import name_key  # noqa: E402
from repair_2014 import build_map, repair_file  # noqa: E402

FIELDNAMES = ["county", "precinct", "office", "district", "party", "candidate",
              "votes", "early_voting", "election_day"]

NUM_RE = re.compile(r"-?\d[\d,]*(\.\d+)?$")


def num(v):
    """Numeric cell -> int, else None. Percent share cells (0 < f < 1 with a
    real fraction) read as None."""
    s = str(v if v is not None else "").strip()
    s = s.replace(",", "")
    if not s or not NUM_RE.match(s):
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    if 0 < f < 1 and not f.is_integer():
        return None
    return int(round(f))


def to_f(v):
    """Numeric cell as float (used by waller's [votes, pct] pair rows)."""
    sv = str(v if v is not None else "").strip().replace(",", "")
    if not sv or not NUM_RE.match(sv):
        return None
    try:
        return float(sv)
    except ValueError:
        return None


WIDE_SMART_TOKENS = [
    (r"CHIEF\s*JUSTICE", "Chief Justice"),
    (r"\bCOUNT\b(?![A-Za-z])", "Court"),
    (r"\b(\d+)\s+CCA\b", "\\1 Court of Appeals"),
    (r"\bUS\s+REP\b", "US Representative"),
    (r"\bSUP\s+CT\b", "Supreme Court"),
    (r"\bCT\s+CRIM\s+APP\b", "Court of Criminal Appeals"),
    (r"\bCRIM\s+APP\b", "Criminal Appeals"),
    (r"\bCT\s+APP\b\.?", "Court of Appeals"),
    (r"\bCCA\b", "Court of Criminal Appeals"),
    (r"\bPLC\b", "Place"),
    (r"\bCRM\b", "Criminal"),
    (r"\bJDG\b", "Judge"),
    (r"\bJUST\b", "Justice"),
    (r"\bCOMP\b", "Comptroller"),
    (r"\bPUB\s+ACCTS\b", "Public Accounts"),
    (r"\bCOMM\b\.?", "Commissioner"),
    (r"\bOFC\b", "Office"),
    (r"\bGEN\b", "General"),
    (r"\bDIST\b\.?", "District"),
    (r"\bLT\s+GOV\b", "Lieutenant Governor"),
    (r"\bLIEUTENEANT\b", "Lieutenant"),
    (r"\bSTATE\s+REP\b", "State Representative"),
    (r"\bAT\s*TNY\b", "Attorney"),
    (r"\bATORNEY\b", "Attorney"),
    (r"\bCRIMINAL\s+APPEALS?\b", "Criminal Appeals"),
    (r"\bAPPEALS\b", "Court of Appeals"),
    (r"\bJUDGE\s+COURT\s+CRIMINAL\b", "Judge Court of Criminal"),
    (r"\bCOMR\b", "Commissioner"),
    (r"\bCOURT\s+CRIMINAL\b", "Court of Criminal"),
    (r"\bCRIMINAL\b", "Criminal"),
    (r"\bAT[T]?Y\s+GEN(E(RAL)?)?\b", "Attorney General"),
    (r"\bLT\s+GOV\w*\b", "Lieutenant Governor"),
    (r"\bRRC\b", "Railroad Commissioner"),
    (r"\bGLO\b", "General Land Office"),
    (r"\bCH\s+JUSTICE\s+S\.?C\.?\b", "Chief Justice Supreme Court"),
    (r"\bJUSTICE\s*#\s*(\d)", "Justice, Supreme Court, Place \\1"),
    (r"\bAPPEALS\s*#\s*(\d)", "Court of Criminal Appeals Place \\1"),
    (r"\bJP\b", "Justice of the Peace"),
    (r"\bCOMM\b\.?", "Commissioner"),
    (r"\bOFC\b", "Office"),
    (r"\bGEN\b", "General"),
    (r"\bSU?PREME\b", "Supreme"),
    (r"\bRR\b", "Railroad"),
    (r"\bS\.?C\.?,?\b", "Supreme Court"),
    (r"\bSC\b", "Supreme Court"),
    (r"\bCCA\b", "Court of Criminal Appeals"),
]


def resolve_office(title):
    """(office, district) via the canonical helpers, with the ASC title
    cleaner as the fallback."""
    from helpers_2026 import normalize_office
    t = re.sub(r"\s+", " ", str(title or "").strip())
    if not t:
        return "", ""
    if re.fullmatch(r"land office|commissioner land", t, re.I):
        t = "Commissioner of the General Land Office"
    for pat, rep in WIDE_SMART_TOKENS:
        t = re.sub(pat, rep, t, flags=re.I)
    if re.search(r"public accounts", t, re.I) and not re.search(r"comptroller", t, re.I):
        t = "Comptroller of Public Accounts"
    if re.fullmatch(r"commissioner\s+(of\s+)?agri?c?(ulture)?", t.rstrip("?."), re.I):
        t = "Commissioner of Agriculture"
    # 'United State Representative' (Kinney's typo for United States ...) would
    # otherwise normalize as a state house race
    t = re.sub(r"\bUnited State\b(?!s)", "United States", t, flags=re.I)
    # Rockwall canvass suffixes and the 'Govenor' typo
    t = re.sub(r"\bGovenor\b", "Governor", t, flags=re.I)
    t = re.sub(r"\s+\w+\s+COUNTYWIDE.*$", "", t, flags=re.I)
    t = re.sub(r"\s+COUNTYWIDE.*$", "", t, flags=re.I)
    t = re.sub(r"\s+(DEM|REP)\s*$", "", t, flags=re.I)
    res = normalize_office(t)
    if res:
        office, district = (res[0], res[1] if len(res) > 1 else "")
        return (office or ""), (district or "")
    office, district = clean_titles(t)
    return (office or ""), (district or "")


SKIP_ROW_RE = re.compile(
    r"^\s*(total\b|totals\b|under votes|over votes|ballots cast|registered voters"
    r"|current voters|%\s*$|number of registered|early total|election total"
    r"|grand total|total ballots|total votes cast|ed total|ev total|final\b"
    r"|total no\. voted|total votes? by pct|votes cast)", re.I)


def mk(county, pct, office, cand, party, votes, ev="", ed="", district=""):
    def as_int(x):
        if x in ("", None):
            return ""
        try:
            return int(x)
        except (TypeError, ValueError):
            return 0
    votes = as_int(votes)
    ev = as_int(ev) if ev != "" else ""
    ed = as_int(ed) if ed != "" else ""
    pct = re.sub(r"\.0+$", "", str(pct))
    return {"county": county, "precinct": pct, "office": office,
            "district": str(district).strip(),
            "party": party, "candidate": str(cand).strip(), "votes": votes,
            "early_voting": ev, "election_day": ed}


def skip_row(c0, cells):
    return (not c0) or SKIP_ROW_RE.match(c0)


# ---------------------------------------------------------------------------
# zavala: candidate rows with one combined total column, no precinct breakdown
# ---------------------------------------------------------------------------
def zavala(sheets, county, party):
    recs = []
    for name, rows in sheets:
        race = None
        for row in rows:
            c0 = str(row[0] or "").strip() if row else ""
            cells = [v for v in row[1:] if num(v) is not None]
            if not cells:
                if c0:
                    race = c0
                continue
            if race is None:
                race = c0
                continue
            if skip_row(c0, cells):
                continue
            office, district = resolve_office(race)
            recs.append(mk(county, "", office, c0, party, cells[-1],
                           district=district))
    return recs


# ---------------------------------------------------------------------------
# kinney: two column bands (EARLY VOTING pcts 1-4 + subtotal | ELECTION DAY
# pcts 1-4 + subtotal | TOTAL); race rows all-caps in col 0
# ---------------------------------------------------------------------------
def kinney(sheets, county, party):
    """Columns: 4 early pcts | EV subtotal | 4 ED pcts | ED subtotal | TOTAL."""
    recs = []
    for name, rows in sheets:
        race = None
        # locate the subtotal/total columns on the label row
        sub_cols = {}
        for row in rows:
            for i in range(1, len(row)):
                t = str(row[i] or "").strip().upper()
                if t in ("SUB TOTAL", "SUBTOTAL", "TOTAL"):
                    sub_cols[i] = True
            break
        for row in rows:
            c0 = str(row[0] or "").strip() if row else ""
            u = c0.upper()
            if u.startswith(("UNOFFICIAL", "EARLY VOTING", "ELECTION DAY")):
                continue
            vals = [(i, num(row[i])) for i in range(1, len(row))]
            vals = [(i, v) for i, v in vals if v is not None]
            # race rows are ALL-CAPS labels (candidates are title case)
            if c0.isupper() and c0 and re.search(r"[A-Z]{3}", u) \
                    and u not in ("SUB", "TOTAL"):
                race = c0
                continue
            if not vals or not c0:
                continue
            ev = sum(v for i, v in vals if 1 <= i <= 4)
            ed = sum(v for i, v in vals if 6 <= i <= 9)
            total = vals[-1][1]
            office, district = resolve_office(race)
            recs.append(mk(county, "", office, c0, party, total, ev, ed,
                           district=district))
    return recs


# ---------------------------------------------------------------------------
# childress: Precinct | Candidate | Party | Type(Early/Election) | Count,
# with race named on '****' rows
# ---------------------------------------------------------------------------
def childress(sheets, county, party):
    recs = []
    for name, rows in sheets:
        race = None
        for row in rows[1:]:
            c0 = str(row[0] or "").strip()
            racec = str(row[1] or "").strip() if len(row) > 1 else ""
            cand = str(row[1] or "").strip() if len(row) > 1 else ""
            ctype = str(row[3] or "").strip() if len(row) > 3 else ""
            count = num(row[4]) if len(row) > 4 else None
            if len(row) < 5:
                continue
            if c0 == "Precinct" and racec == "Candidate":
                continue
            if c0 == "****" or (c0 and not cand and not ctype):
                race = racec or c0
                continue
            if c0 and cand and ctype:
                ev = count if ctype == "Early" else ""
                ed = count if ctype == "Election" else ""
                office, district = resolve_office(race or "")
                recs.append(mk(county, str(precinct_name(c0)), office, cand,
                               party, (ev or 0) + (ed or 0), ev, ed,
                               district=district))
    return recs


# ---------------------------------------------------------------------------
# floyd: the SOS 'detail vote total' CSV pasted into one cell per row; the
# 37-column DVT schema lets us split deterministically.
# ---------------------------------------------------------------------------
DVT_SCHEMA = ["political_subdivision", "election_date", "election_name",
              "precinct_name", "split_name", "reporting_flag", "update_count",
              "pct_id", "pct_seq_nbr", "reg_voters", "turn_out", "contest_id",
              "contest_seq_nbr", "contest_title", "contest_party_name",
              "selectable_options", "candidate_id", "candidate_name",
              "candidate_type", "cand_seq_nbr", "party_code", "total_ballots",
              "total_votes", "total_under_votes", "total_over_votes",
              "absentee_ballots", "absentee_votes", "absentee_under_votes",
              "absentee_over_votes", "early_ballots", "early_votes",
              "early_under_votes", "early_over_votes", "election_ballots",
              "election_votes", "election_under_votes", "election_over_votes"]


def floyd(sheets, county, party):
    recs = []
    for name, rows in sheets:
        for row in rows:
            blob = None
            for c in row:
                s = str(c or "")
                if s.count(",") >= 20:
                    blob = s
                    break
            if blob is None:
                continue
            cells = next(csvmod.reader([blob]))
            if len(cells) < 30:
                continue
            # the blob starts at the 4th schema column (precinct_name)
            d = zip_longest(DVT_SCHEMA[3:], cells)
            if (d.get("candidate_name") or "").strip() in ("", "candidate_name"):
                continue
            votes = to_int(d.get("total_votes"))
            ev = to_int(d.get("early_votes"))
            ed = to_int(d.get("election_votes"))
            if votes == "" and ev == "" and ed == "":
                continue
            office, district = resolve_office(d.get("contest_title"))
            pct_s = str(d.get("precinct_name") or "").strip()
            party = (d.get("party_code") or "").strip().upper()
            if party not in ("DEM", "REP"):
                look = cand_office_map().get(name_key_s(d.get("candidate_name")))
                if look:
                    party = look[0][2]
            recs.append(mk(county, str(precinct_name(pct_s)) if pct_s else "",
                           office, d.get("candidate_name").strip(), party, votes,
                           ev if ev != "" else "", ed if ed != "" else "",
                           district=district))
    return recs


def name_key_s(cand):
    from verify_2014 import name_key
    return name_key(cand or "")


def zip_longest(names, cells):
    out = {}
    for i, nm in enumerate(names):
        out[nm] = cells[i] if i < len(cells) else ""
    return out


# ---------------------------------------------------------------------------
# tom_green: Hart-layout rows without a race column at all; each candidate is
# assigned to the office the (statewide/candidate) baseline says they ran for.
# ---------------------------------------------------------------------------
_CAND_OFFICE = None


def cand_office_map():
    """(name_key, party-collapsed candidate) -> (office, district, party)."""
    global _CAND_OFFICE
    if _CAND_OFFICE is not None:
        return _CAND_OFFICE
    from verify_2014 import name_key
    from collections import defaultdict
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir,
                        "2014", "20140304__tx__primary__county.csv")
    counts = defaultdict(lambda: defaultdict(int))
    partycnt = defaultdict(lambda: defaultdict(int))
    with open(base) as fh:
        for r in csvmod.DictReader(fh):
            c = (r["candidate"] or "").strip()
            if not c or c == "Total":
                continue
            votes = (r["votes"] or "").replace(",", "").strip()
            if votes and not votes.isdigit() and " " in votes:
                continue  # corrupt row (party in the votes column etc.)
            counts[name_key(c)][(r["office"].strip(), (r["district"] or "").strip())] += 1
            partycnt[name_key(c)][(r["party"] or "").strip().upper()] += 1
    mp = {}
    for nkey, offices in counts.items():
        # candidate ran for exactly one (office, district)
        if len(offices) == 1:
            (office, district), n = next(iter(offices.items()))
            ps = [(n, p) for p, n in partycnt[nkey].items() if p in ("DEM", "REP")]
            party = max(ps)[1] if ps else ""
            mp[nkey] = ((office, district, party), n)
        else:
            mp[nkey] = None
    _CAND_OFFICE = mp
    return mp


def tom_green(sheets, county, party):
    recs = []
    unknown = set()
    cmap = cand_office_map()
    from verify_2014 import name_key
    for name, rows in sheets:
        for row in rows[1:]:
            pct = row[5] if len(row) > 5 else None
            cand = row[7] if len(row) > 7 else None
            ev = to_int(row[9]) if len(row) > 9 else ""
            ed = to_int(row[10]) if len(row) > 10 else ""
            if pct in (None, "") or cand in (None, "") or \
                    not str(cand).strip() or to_int(pct) == "":
                continue
            cand_s = re.sub(r"\s+", " ", str(cand).strip())
            if cand_s.upper() in ("FOR", "AGAINST", "YES", "NO", "IN FAVOR"):
                continue  # proposition FOR/AGAINST rows: offices unidentifiable
            votes = (ev or 0) + (ed or 0) if ev != "" or ed != "" else 0
            look = cmap.get(name_key(cand_s))
            if not look:
                unknown.add(cand_s)
                office, district = "@@", ""
            else:
                (office, district, bparty), _ = look
                office, district = resolve_office(
                    office if not district else f"{office} {district}")
            recs.append(mk(county, str(precinct_name(str(pct).strip())),
                           office, cand_s, str(bparty or party or "").upper(),
                           votes, ev, ed))
    if unknown:
        print(f"   tom_green: candidates not in the map: {sorted(unknown)}")
    return recs


HANDLERS = {
    "zavala": zavala,
    "kinney": kinney,
    "childress": childress,
    "floyd": floyd,
    "tom_green": tom_green,
}


# ---------------------------------------------------------------------------

def parse_sources(county, sources):
    """Dispatch by county; returns (records, notes) or (None, reason).

    Handlers are called once per sheet with (sheets, county, party); source
    name is stashed in SOURCE_NAME for handlers that need per-file context."""
    key = county.lower().replace(" ", "_")
    handler = HANDLERS.get(key)
    if handler is None:
        return None, f"no wide handler for {county}"
    recs = []
    notes = []
    seen = set()
    for src in sources:
        SOURCE_NAME["name"] = os.path.basename(src).upper()
        for name, rows in load_sheets(src):
            got = handler([(name, rows)], county, party_of_source(src, rows))
            sig = tuple(sorted((r["precinct"], r["office"], r["district"],
                                r["candidate"], r["votes"])
                               for r in got))
            if sig in seen:
                notes.append(f"{os.path.basename(src)}:{name}: duplicate rows skipped")
                continue
            seen.add(sig)
            recs.extend(got)
    if not recs:
        return None, "; ".join(notes) or "no wide records"
    return recs, notes


SOURCE_NAME = {}


# ---------------------------------------------------------------------------
# waller: one sheet per race page for a single precinct; candidate rows carry
# [early votes, pct, election-day votes, pct, total, pct]
# ---------------------------------------------------------------------------
WALLER_JASPER_MAP = {
    "US SENATOR": "U.S. Senate", "UNITED STATES SENATOR": "U.S. Senate",
    "US REP": "U.S. House", "GOVERNOR": "Governor", "LT GOV": "Lieutenant Governor",
    "AG": "Attorney General", "CPA": "Comptroller", "CGLO": "Land Commissioner",
    "COM OF AG": "Commissioner of Agriculture", "RRC": "Railroad Commissioner",
    "CJSC": "Supreme Court", "JSC#6": "Supreme Court", "JSC#7": "Supreme Court",
    "JCCA#3": "Court of Criminal Appeals", "SBE#7": "State Board of Education",
    "CJ": "County Judge", "DC": "District Clerk", "CC": "County Clerk",
    "CT": "County Treasurer", "CO CHAIR": "County Chairman",
}


def jasper_office(banner):
    """Resolve a jasper banner/abbreviation to (office, district)."""
    u = str(banner).strip().upper()
    if u.startswith("JP#"):
        return (f"Justice of the Peace Pct {u[3:].strip()}", "")
    if u.startswith("CONS#"):
        return (f"Constable Pct {u[5:].strip()}", "")
    if u.startswith("COMM"):
        m2 = re.search(r"(\d+)", u)
        return ((f"County Commissioner Pct {m2.group(1)}" if m2 else u), "")
    if u in WALLER_JASPER_MAP:
        return (WALLER_JASPER_MAP[u], "")
    return resolve_office(banner)


def waller(sheets, county, party):
    recs = []
    for name, rows in sheets:
        race = None
        pct = ""
        for row in rows:
            c0 = row[0] if row else ""
            joined = " ".join(str(c) for c in row if str(c).strip())
            m = re.search(r"Precinct\s+(\d+)", joined)
            if m and "Ballots Cast" in joined:
                pct = m.group(1)
                continue
            t = str(c0).strip() if isinstance(c0, str) else ""
            if t and not num(c0) and not t.lower().startswith(("cast", "over", "under")):
                m2 = re.match(r"^(?:DEM|REP|LIB|GRN)\s*-\s*(.+?),\s*Vote", t, re.I)
                if m2:
                    race = m2.group(1).strip()
                continue
            if not race or not t:
                continue
            # numeric cells in row order: [early, pct, election, pct, total, pct]
            nums = []
            for c in row[1:]:
                f = to_f(c)
                if f is not None:
                    nums.append(f)
            if len(nums) < 5:
                continue
            ev, ed, tot = nums[0], nums[2], nums[4]
            office, district = resolve_office(race)
            recs.append(mk(county, pct, office, t, party, tot, ev, ed,
                           district=district))
    return recs


# ---------------------------------------------------------------------------
# rockwall: sheets 'Early Voting ...' / 'Election Day ...' with header
# 'Contest | Party | Turnout | <precincts> | Total'
# ---------------------------------------------------------------------------
def rockwall(sheets, county, party):
    recs = []
    for name, rows in sheets:
        lname = name.lower()
        if "summary" in lname:
            phase = "total"
        elif "early" in lname:
            phase = "early"
        elif "election day" in lname:
            phase = "election"
        else:
            phase = None
        if phase is None:
            continue
        labels = []
        header_row = None
        for row in rows:
            if str(row[0] or "").strip().lower() == "contest":
                header_row = row
                for i in range(3, len(row)):
                    t = str(row[i] or "").strip()
                    if t.lower() in ("total", ""):
                        continue
                    labels.append((i, precinct_name(t)))
                break
        if header_row is None:
            continue
        race = None
        for row in rows[rows.index(header_row) + 1:]:
            c0 = str(row[0] or "").strip()
            pflag = str(row[1] or "").strip() if len(row) > 1 else ""
            vals = {i: num(row[i]) for i, _ in labels}
            vals = {i: v for i, v in vals.items() if v is not None}
            if c0 and not vals:
                race = c0
                continue
            if race is None or not c0 or not vals:
                continue
            office, district = resolve_office(race)
            rparty = pflag.upper() if pflag.upper() in ("DEM", "REP") else party
            for i, pct in labels:
                v = num(row[i])
                if v is None:
                    continue
                if phase == "early":
                    recs.append(mk(county, pct, office, c0, rparty, v, v, "",
                                   district=district))
                elif phase == "total":
                    recs.append(mk(county, pct, office, c0, rparty, v, "", "",
                                   district=district))
                    recs[-1]["_total_only"] = True
                else:
                    recs.append(mk(county, pct, office, c0, rparty, v, "", v,
                                   district=district))
    return recs


# ---------------------------------------------------------------------------
# newton: 'VOTING BOX' tables; one file per (party x early/election day)
# ---------------------------------------------------------------------------
def newton(sheets, county, party):
    phase = "early" if re.search(r"early", SOURCE_NAME.get("name", ""), re.I) \
        else "election"
    recs = []
    for name, rows in sheets:
        labels = {}
        for row in rows:
            c0 = str(row[0] or "").strip()
            if c0.upper().startswith("VOTING BOX"):
                for i in range(1, len(row)):
                    nv = num(row[i])
                    if nv is not None:
                        labels[i] = str(int(nv))
                break
        if not labels:
            continue
        race = None
        for row in rows:
            c0 = str(row[0] or "").strip()
            if c0.upper().startswith(("TOTAL BALLOTS", "VOTING BOX")):
                continue
            vals = {i: num(row[i]) for i in labels}
            vals = {i: v for i, v in vals.items() if v is not None}
            if c0 and not vals:
                race = c0
                continue
            if race is None or not c0 or not vals:
                continue
            office, district = resolve_office(race)
            for i, v in vals.items():
                if phase == "early":
                    recs.append(mk(county, labels[i], office, c0, party, v, v,
                                   "", district=district))
                else:
                    recs.append(mk(county, labels[i], office, c0, party, v, "",
                                   v, district=district))
    return recs


# ---------------------------------------------------------------------------
# jasper: candidate-column table under merged office banners. The main file
# (with the same columns) carries totals; the '-early' file carries early votes.
# ---------------------------------------------------------------------------
def jasper(sheets, county, party):
    phase = "early" if re.search(r"early", SOURCE_NAME.get("name", ""), re.I) \
        else "total"
    recs = []
    for name, rows in sheets:
        candidates = None
        for ri, row in enumerate(rows):
            if str(row[0] or "").strip().upper().startswith("PRECINCT"):
                banner_row = rows[ri - 1] if ri > 0 else None
                cand_row = row
                block_cols = [i for i, v in enumerate(cand_row)
                              if str(v or "").strip().upper().startswith("PRECINCT")]
                cols = []
                for bi, bstart in enumerate(block_cols):
                    bend = block_cols[bi + 1] if bi + 1 < len(block_cols) else len(cand_row)
                    banner = ""
                    for i in range(bstart, bend):
                        tb = str(banner_row[i] or "").strip() if banner_row else ""
                        if tb and tb.upper() != "NONE":
                            banner = tb
                        cand = str(cand_row[i] or "").strip()
                        if cand.upper() in ("FOR", "AGAINST"):
                            continue
                        if cand and not cand.upper().startswith("PRECINCT"):
                            cols.append((i, banner, cand))
                candidates = cols
                break
        if candidates is None:
            continue
        for row in rows:
            c0 = str(row[0] or "").strip()
            if not c0 or c0.upper() in ("ABST", "TOTAL") or num(c0) is None:
                continue
            for i, banner, cand in candidates:
                v = num(row[i])
                if v is None:
                    continue
                office, district = jasper_office(banner)
                if phase == "early":
                    recs.append(mk(county, c0, office, cand, party, v, v, "",
                                   district=district))
                else:
                    rr = mk(county, c0, office, cand, party, v, "",
                            v, district=district)
                    rr["_total_only"] = True
                    recs.append(rr)
    return recs


HANDLERS.update({
    "waller": waller,
    "rockwall": rockwall,
    "newton": newton,
    "jasper": jasper,
})


# ---------------------------------------------------------------------------

def total_or_blank(a, b):
    a = 0 if a == "" else a
    b = 0 if b == "" else b
    return a + b


def merge_phase_rows(recs):
    """Combine records for the same (precinct, office, district, party,
    candidate) split across early/election-day source files.

    A record flagged _total_only (jasper main file: the votes are the full
    total, with the early file adding the early breakdown) keeps its vote
    count; otherwise the phases are complementary and votes = ev + ed."""
    out = {}
    for r in recs:
        key = (r["precinct"], r["office"], r["district"], r["party"],
               r["candidate"])
        k = out.get(key)
        if k is None:
            out[key] = dict(r)
            continue
        if r.get("_total_only"):
            k["votes"] = r["votes"]
            k["_total_only"] = True
        elif k.get("_total_only"):
            pass
        else:
            k["votes"] = total_or_blank(k["votes"], r["votes"])
        k["early_voting"] = total_or_blank(k["early_voting"], r["early_voting"])
        k["election_day"] = total_or_blank(k["election_day"], r["election_day"])
    for k in out.values():
        t = k.pop("_total_only", None)
        if t and k["early_voting"] != "" and not k["election_day"]:
            try:
                k["election_day"] = int(k["votes"]) - int(k["early_voting"])
            except (TypeError, ValueError):
                pass
        elif t is None and k["early_voting"] != "" and k["election_day"] != "":
            # phase-split files: the two records are complementary
            try:
                k["votes"] = int(k["early_voting"]) + int(k["election_day"])
            except (TypeError, ValueError):
                pass
    return list(out.values())


def dedupe_rows(recs):
    seen = set()
    out = []
    for r in recs:
        key = (r["precinct"], r["office"], r["district"], r["party"],
               r["candidate"], r["votes"], r.get("early_voting"),
               r.get("election_day"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def party_of_source(src, rows):
    """Party from the filename (the 2014 sources are file-per-party)."""
    bn = os.path.basename(src).upper()
    if "DEMOCRAT" in bn or "_DEM" in bn or "DEM " in bn or re.search(r"\bDEM", bn):
        return "DEM"
    if "REPUBLICAN" in bn or "_REP" in bn or re.search(r"\bREP", bn):
        return "REP"
    return ""


def run_county(county, out, sources):
    title = county.replace("_", " ").title()
    recs, notes = parse_sources(county, sources)
    if not recs:
        print(f"-- {county}: wide parse failed: {notes}")
        return 0
    recs = dedupe_rows(merge_phase_rows(recs))
    write_county_csv(out, title, recs, FIELDNAMES)
    print(f"wrote {out}: {len(recs)} wide rows")
    for n in notes:
        print("   note:", n)
    return len(recs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--county", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("sources", nargs="+")
    args = ap.parse_args()
    run_county(args.county, args.out, args.sources)


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Generic column-label block parser: header rows carry the precinct labels for
# one or two phases; race labels in col0 (often ALL CAPS), candidates below.
# ---------------------------------------------------------------------------
def label_blocks(rows, county, party, phase_cols, skip_total_re=None):
    """phase_cols: callable(header_row) -> {col: (phase, precinct_label)}.
    Returns records."""
    recs = []
    race = None
    labels = None
    for row in rows:
        c0 = str(row[0] or "").strip() if row else ""
        mapping = phase_cols(row) if phase_cols else None
        vals = {i: num(row[i]) for i in (mapping or {})}
        vals = {i: v for i, v in vals.items() if v is not None}
        if mapping:
            labels = mapping
            if c0 and c0.upper() not in ("",) and not re.match(
                    r"^(?:US|UNITED)", c0.upper()) is None:
                race = c0
            continue
        if not c0:
            continue
        if not vals:
            race = c0
            continue
        if race is None:
            race = c0
            continue
        office, district = resolve_office(race)
        for i, (phase, pct) in (labels or {}).items():
            v = num(row[i])
            if v is None:
                continue
            if phase == "early":
                recs.append(mk(county, pct, office, c0, party, v, v, "",
                               district=district))
            elif phase == "total":
                recs.append(mk(county, pct, office, c0, party, v, "", "",
                               district=district))
                recs[-1]["_total_only"] = True
            else:
                recs.append(mk(county, pct, office, c0, party, v, "", v,
                               district=district))
    return [r for r in recs if not SKIP_ROW_RE.match(
        str(r["candidate"]).replace(" Votes:", "").strip())]


# ---------------------------------------------------------------------------
# rains: 'RACE | PCT 101 ... | TOTALS' header; two files (early / election day)
# ---------------------------------------------------------------------------
def rains(sheets, county, party):
    phase = "early" if re.search(r"early", SOURCE_NAME.get("name", ""), re.I) \
        else "election"
    recs = []
    for name, rows in sheets:
        labels = None
        for row in rows:
            if str(row[0] or "").strip().upper().startswith("RACE"):
                labels = [(i, str(precinct_name(str(row[i]).strip())))
                          for i in range(1, len(row))
                          if num(row[i]) is None and
                          str(row[i]).strip().upper() not in ("TOTALS", "TOTAL", "NONE", "")
                          and num(row[i]) is None] \
                    if True else []
                labels = [(i, precinct_name(str(row[i]).strip()))
                          for i in range(1, len(row))
                          if str(row[i]).strip() not in ("",)
                          and str(row[i]).strip().upper() not in ("TOTALS", "TOTAL", "NONE")]
                break
        if labels is None:
            labels = [(i, label) for i, label in (labels or [])]
        if not labels:
            continue
        seen = set()
        race = None
        for row in rows:
            c0 = str(row[0] or "").strip()
            if not c0 or c0 == 'None':
                continue
            u0 = c0.upper()
            if u0.startswith(("RACE",)):
                continue
            nv = any(num(row[i]) is not None for i, _ in labels)
            if not nv:
                race = c0
                continue
            if race is None:
                race = c0
                continue
            office, district = resolve_office(race)
            key = (c0.upper(), tuple(sorted(labels)))
            for i, pct in labels:
                v = num(row[i])
                if v is None:
                    continue
                ev, ed = (v, "") if phase == "early" else ("", v)
                cand_party = party
                if not cand_party:
                    look = cand_office_map().get(name_key_s(c0))
                    if look:
                        cand_party = look[0][2]
                recs.append(mk(county, pct, office, c0, cand_party, v, ev, ed,
                               district=district))
    return recs


# ---------------------------------------------------------------------------
# falls: header 'PCT 101' pairs (EARLY, ELECTION), race rows col0, cand col1
# ---------------------------------------------------------------------------
def falls(sheets, county, party):
    recs = []
    for name, rows in sheets:
        pct_labels = []   # row index with 'PCT ###' labels
        ph_labels = []
        for ri, row in enumerate(rows):
            if any(str(row[i] or "").strip().upper().startswith("PCT ")
                   for i in range(min(len(row), 28))):
                pct_labels = [(i, precinct_name(str(row[i]).strip()[4:]))
                              for i in range(len(row))
                              if str(row[i] or "").strip().upper().startswith("PCT ")]
                # next row carries EARLY/ELECTION markers per column
                ph = rows[ri + 1] if ri + 1 < len(rows) else []
                ph_labels = [(i, col) for i in range(len(row))
                             if (col := str(ph[i] or "").strip().upper()) in ("EARLY", "ELECTION")]
                break
        if not pct_labels:
            continue
        colphase = {}
        for i, col in ph_labels:
            colphase[i] = col
        race = None
        for row in rows:
            c0 = str(row[0] or "").strip()
            cand = str(row[1] if len(row) > 1 else "").strip() if not c0 else c0
            if not cand:
                continue
            vals = [(i, num(row[i])) for i in colphase]
            vals = [(i, v) for i, v in vals if v is not None]
            if not vals:
                race = c0
                continue
            office, district = resolve_office(race)
            ev = sum(v for i, v in vals if colphase[i] == "EARLY")
            ed = sum(v for i, v in vals if colphase[i] == "ELECTION")
            for i, v in vals:
                recs.append(mk(county, dict(pct_labels).get(i, ""), office, cand,
                               party, v,
                               v if colphase[i] == "EARLY" else "",
                               v if colphase[i] == "ELECTION" else "",
                               district=district))
    return recs


# ---------------------------------------------------------------------------
# franklin: EV 101..402 | EV TOTAL | ED 101..402 | ED TOTAL | FINAL
# ---------------------------------------------------------------------------
def franklin(sheets, county, party):
    recs = []
    for name, rows in sheets:
        evc, edc, ev_total, ed_total, finalc = [], [], None, None, None
        for row in rows:
            for i, c in enumerate(row):
                t = str(c or "").strip().upper()
                if t.startswith("EV ") and re.search(r"\d", t):
                    evc.append((i, precinct_name(t.split()[1])))
                elif t.startswith("ED ") and re.search(r"\d", t):
                    edc.append((i, precinct_name(t.split()[1])))
                elif t == "EV TOTAL":
                    ev_total = i
                elif t == "ED TOTAL":
                    ed_total = i
                elif t == "FINAL":
                    finalc = i
            if evc or edc:
                break
        race = None
        for row in rows:
            c0 = str(row[0] or "").strip()
            if not c0:
                continue
            if not any(num(row[i]) is not None for i, _ in evc + edc):
                race = c0
                continue
            if race is None:
                race = c0
                continue
            office, district = resolve_office(race)
            cols = [(i, pct, "early") for i, pct in evc] + \
                [(i, pct, "election") for i, pct in edc]
            for i, pct, ph in cols:
                v = num(row[i])
                if v is None:
                    continue
                ev, ed = (v, "") if ph == "early" else ("", v)
                recs.append(mk(county, pct, office, c0, party, v, ev, ed,
                               district=district))
    return cottle_surnames(recs)


# ---------------------------------------------------------------------------
# kimble: columns 'EV PCT n' / 'ED PCT n' / 'HAND COUNT PCT n'; final
# 'EARLY VOTE' and 'TOTALS' columns carry summaries (ignored)
# ---------------------------------------------------------------------------
def kimble(sheets, county, party):
    recs = []
    for name, rows in sheets:
        evc, edc = [], []
        for row in rows:
            for i, c in enumerate(row):
                t = str(c or "").strip().upper()
                m = re.match(r"^(EV|ED)\s+PCT[. ]*\s*(\d+)", t)
                if m:
                    (evc if m.group(1) == "EV" else edc).append(
                        (i, m.group(2)))
            if evc:
                break
        race = None
        for row in rows:
            c0 = str(row[0] or "").strip()
            if not c0:
                continue
            if not any(num(row[i]) is not None for i, _ in evc + edc):
                race = c0
                continue
            if race is None:
                race = c0
                continue
            office, district = resolve_office(race)
            for i, pct in evc:
                v = num(row[i])
                if v is None:
                    continue
                recs.append(mk(county, pct, office, c0, party, v, v, "",
                               district=district))
            for i, pct in edc:
                v = num(row[i]) or 0
                recs.append(mk(county, pct, office, c0, party, v, "", v,
                               district=district))
    return recs


# ---------------------------------------------------------------------------
# hansford: sheet 'Sheet1' of each file = election-day or early votes; the
# office label spans col0, 'CANDIDATES' col2 header row lists precinct numbers
# ---------------------------------------------------------------------------
def hansford(sheets, county, party):
    phase = "early" if re.search(r"early", SOURCE_NAME.get("name", ""), re.I) \
        else "election"
    recs = []
    for name, rows in sheets:
        labels = []
        for ri, row in enumerate(rows):
            c0 = str(row[0] or "").strip()
            if c0.startswith(("NAME OF OFFICE",)):
                hdr = rows[ri + 3] if ri + 3 < len(rows) else row
                for i in range(3, len(row)):
                    nv = num(row[i]) if False else None
                # precinct numbers live on the row carrying '1','2',... in col3+
                break
        # find the labels row: a row whose col3/4 are numeric and col0 empty
        for ri, row in enumerate(rows):
            if str(row[0] or "").strip():
                continue
            nums = [(i, num(row[i])) for i in range(3, len(row))]
            nums = [(i, v) for i, v in nums if v is not None and i <= 14]
            if len(nums) >= 5:
                labels = [(i, str(v)) for i, v in nums
                          if str(v) not in ("0",)]
                for i, v in nums:
                    if v == 0 and i <= 14:
                        pass
                labels = [(i, str(v)) for i, v in nums if v != 0 or i == 3]
                break
        if not labels:
            continue
        labels = [(i, v) for i, v in labels if v != "TOTAL"]
        race = None
        for row in rows:
            c0 = str(row[0] or "").strip()
            cand = str(row[2] or "").strip() if len(row) > 2 else ""
            if c0 and c0.lower() not in ("name of office",):
                race = c0
                continue
            if race is None or not cand or cand.lower() in ("candidates",):
                continue
            office, district = resolve_office(race)
            for i, pct in labels:
                v = num(row[i])
                if v is None:
                    continue
                ev, ed = (v, "") if phase == "early" else ("", v)
                recs.append(mk(county, pct, office, cand, party, v, ev, ed,
                               district=district))
    return recs


# ---------------------------------------------------------------------------
# hood: EARLY section (PAPER col1 + Pct 1..16 cols 2-16) then ELECTION DAY
# section (Early Vote col1 + Pct cols 2-16); TOTALS col17 in each section
# ---------------------------------------------------------------------------
def hood(sheets, county, party):
    recs = []
    for name, rows in sheets:
        phase = "early"
        labels = {}
        race = None
        for row in rows:
            c0 = str(row[0] or "").strip()
            u0 = c0.upper()
            if u0.startswith("ELECTION DAY"):
                phase = "election"
                race = None
                labels = {}
                continue
            if u0.startswith("EARLY VOTING"):
                phase = "early"
                continue
            # header rows: col0 empty, Pct labels in cols 2..16
            if not c0 and any(str(row[i] or "").strip().upper().startswith("PCT")
                              for i in range(2, min(len(row), 18))):
                labels = {}
                for i in range(1, min(len(row), 18)):
                    t = str(row[i] or "").strip()
                    tl = t.upper()
                    if tl.startswith("TOTAL"):
                        continue
                    if tl.startswith("PCT"):
                        labels[i] = (phase, precinct_name(t[3:].lstrip())
                                     if phase == "early" else
                                     precinct_name(t[3:].lstrip()))
                continue
            vals = [num(row[i]) for i in labels]
            vals = [v for v in vals if v is not None]
            if not vals or not c0:
                if c0:
                    race = c0
                continue
            if race is None:
                race = c0
                continue
            if u0 in ("YES", "NO"):
                cand_t = "For" if u0 == "YES" else "Against"
            else:
                cand_t = c0
            office, district = resolve_office(race)
            for i, (ph, pct) in labels.items():
                v = num(row[i])
                if v is None:
                    continue
                if ph == "early":
                    recs.append(mk(county, pct, office, cand_t, party, v, v,
                                   "", district=district))
                else:
                    recs.append(mk(county, pct, office, cand_t, party, v, "",
                                   v, district=district))
    return recs


# ---------------------------------------------------------------------------
# hockley: blocks separated by blank rows; the first row of each block repeats
# the precinct numbers in cols 1..6; candidate rows follow
# ---------------------------------------------------------------------------
def cells_missing(row, labels):
    return any(i >= len(row) for i in labels)


def hockley(sheets, county, party):
    phase = "early" if re.search(r"^EARLY$", SOURCE_NAME.get("name", "") + "|",
                                 re.I) and re.search(r"early", name, re.I) \
        else None
    recs = []
    for name, rows in sheets:
        lname = name.lower()
        if "combined" in lname:
            continue  # the COMBINED sheets repeat the election-day numbers
        if "early" in lname:
            ph_list = ["early"]
        elif "election" in lname:
            ph_list = ["election"]
        else:
            continue
        for name2, phases in ((name, ph_list),):
            race = None
            labels = {}
            pending = False
            for ri, row in enumerate(rows):
                c0 = str(row[0] or "").strip()
                if not c0:
                    pending = True
                    continue
                cells = [num(row[i]) for i in range(1, min(len(row), 19))]
                cells = [v for v in cells if v is not None]
                if pending and c0 and OFFICE_LEAD_WORDS.match(c0):
                    race = c0
                    labels = {}
                    for i in range(1, min(len(row), 19)):
                        v = num(row[i])
                        if v is not None:
                            labels[i] = str(int(v)) if v == int(v) else str(v)
                    pending = False
                    continue
                if c0 and OFFICE_LEAD_WORDS.match(c0) and all(
                        isinstance(num(row.get(i, 0)), int)
                        for i in labels if i < len(row)) and not cells_missing(row, labels):
                    pass
                if race is None or not c0:
                    continue
                office, district = resolve_office(race)
                for i, pct in labels.items():
                    v = num(row[i])
                    if v is None:
                        continue
                    for ph in phases:
                        if ph == "early":
                            recs.append(mk(county, pct, office, c0, party, v,
                                           v, "", district=district))
                        elif ph == "election":
                            recs.append(mk(county, pct, office, c0, party, v,
                                           "", v, district=district))
                        else:
                            recs.append(mk(county, pct, office, c0, party, v,
                                           "", "", district=district))
                            recs[-1]["_total_only"] = True
                pending = False
    return recs


OFFICE_LEAD_WORDS = re.compile(
    r"^(?:US|U\.S\.|UNITED|GOVERNOR|LIEUTENANT|ATTORNEY|COMPTROLLER|"
    r"COMMISSIONER|RAILROAD|CHIEF JUSTICE|JUSTICE|JUDGE|STATE SENATOR|"
    r"STATE REPRESENT|STATE REP|DISTRICT|COUNTY|CLERK|TREASURER|SHERIFF|"
    r"CONSTABLE|JUSTICE OF|PROP|PROPOSITION|SUPREME|COURT|MEMBER|DEM|REP ).*$",
    re.I)


def armstrong_candidate_cols(header):
    """row0 of the armstrong sheet: race names and candidate names mixed;
    a column is a candidate when its text is not an office-lead word."""
    cols = []
    race = None
    for i in range(1, len(header)):
        t = str(header[i] or "").strip()
        if not t or t.upper() == "NONE":
            continue
        t2 = re.sub(r"CHIEF\s*JUSTICE", "CHIEF JUSTICE", t, flags=re.I)
        if OFFICE_LEAD_WORDS.match(t2):
            race = t
            continue
        cols.append((i, race, t))
    return cols


def armstrong(sheets, county, party):
    recs = []
    for name, rows in sheets:
        header = rows[0] if rows else []
        cols = armstrong_candidate_cols(header)
        if not cols:
            continue
        phase = None
        for row in rows[1:]:
            c0 = str(row[0] or "").strip() if row else ""
            lu = c0.lower()
            if lu.startswith("early"):
                phase = "early"
                continue
            if lu.startswith("election") and "day" in lu and "total" not in lu:
                phase = "election"
                continue
            if lu.startswith(("total", "grand")):
                phase = None
                continue
            m = re.match(r"precinct\s+([\w&/-]+)", c0, re.I)
            if not m:
                continue
            pct = precinct_name(m.group(1))
            for i, race, cand in cols:
                v = num(row[i])
                if v is None:
                    continue
                if phase == "early":
                    recs.append(mk(county, pct, race, cand, party, v, v, "")
                                ) if False else None
                    recs.append(mk_p(race, county, pct, cand, party, v, v, ""))
                else:
                    recs.append(mk_p(race, county, pct, cand, party, v, "", v))
    # races go through resolve_office at the end
    for r in recs:
        if r["_raw_office"]:
            o, d = resolve_office(r["_raw_office"])
            r["office"], r["district"], r["_raw_office"] = o, d or r["district"], ""
    for r in recs:
        r.pop("_raw_office", None)
    return recs


def mk_p(raw_office, county, pct, cand, party, votes, ev, ed):
    r = mk(county, pct, "@", cand, party, votes, ev, ed)
    r["_raw_office"] = raw_office
    return r


# ---------------------------------------------------------------------------
# wichita: 'Box #' header row (box numbers on every other column), phase labels
# below, repeated blocks; race rows uppercase col0, candidate rows below
# ---------------------------------------------------------------------------
def wichita(sheets, county, party):
    recs = []
    for name, rows in sheets:
        boxes = []
        for row in rows:
            if str(row[0] or "").strip().upper().startswith("BOX"):
                # box numbers appear on the even columns of this row
                for i in range(1, len(row)):
                    nv = num(row[i])
                    if nv is not None and str(row[i]).strip():
                        boxes.append((i, str(int(nv))))
                break
        if not boxes:
            continue
        # phase labels row: 'Elec Day'/'Early' alternating
        phases = {}
        for row in rows:
            lu = str(row[1] or "").strip().lower()
            if lu.startswith(("early", "elec")):
                for i, box in boxes:
                    # each box occupies two columns (early, elec day)
                    phases[i] = "early"
                    phases[i + 1] = "election"
                break
        if not phases:
            continue
        race = None
        for row in rows:
            c0 = str(row[0] or "").strip()
            if c0.upper().startswith("BOX"):
                continue
            vals = [(i, num(row[i])) for i, _ in boxes]
            vals = [(i, v) for i, v in vals if v is not None]
            if c0 and not vals:
                race = c0
                continue
            if race is None or not c0 or not vals:
                continue
            office, district = resolve_office(race)
            for i, _ in boxes:
                box = dict(boxes)[i]
                ev = num(row[i]) or 0
                ed = num(row.get(i + 1, i + 1)) if False else (num(row[i + 1]) if i + 1 < len(row) else 0) or 0
                recs.append(mk(county, box, office, c0, party, ev + ed, ev, ed,
                               district=district))
    return recs


# ---------------------------------------------------------------------------
# shackelford: single '2014 Primary-Rep' style sheet: race rows carry the
# precinct labels; EARLY cols 1..7, 'Early Total' col, ELECTION DAY block after
# ---------------------------------------------------------------------------
def shackelford(sheets, county, party):
    """The '2014 Primary-Rep' sheet: race rows (ALL CAPS) carry the precinct
    numbers; data rows start with the candidate; EARLY votes in cols 1..7,
    ELECTION DAY votes in cols 9..15 ('Early Total' col 8)."""
    recs = []
    for name, rows in sheets:
        if not re.search(r"2014", name):
            continue
        race = None
        for row in rows:
            c0 = str(row[0] or "").strip()
            if not c0:
                continue
            labs = [(i, str(row[i]).strip().replace(".0", ""))
                    for i in range(1, len(row))
                    if re.fullmatch(r"\d+(\.0)?", str(row[i] or "").strip())]
            nums = [i for i, _ in labs]
            if OFFICE_LEAD_WORDS.match(c0):
                race = c0
                if not nums:
                    continue
            if race is None:
                continue
            early_start = next((i for i in range(1, len(row))
                                if str(row[i] or "").strip().upper().startswith("EARLY")), 1)
            office, district = resolve_office(race)
            ev = sum((num(row[i]) or 0) for i in range(1, 8)
                     if num(row[i]) is not None)
            ed = sum((num(row[i]) or 0) for i in range(9, 16)
                     if num(row[i]) is not None)
            # the race row itself carries no votes; skip it
            if skip_row(c0, [1]) or (num(row[1]) is None and num(row[9]) is None):
                continue
            cand = " ".join(str(r).strip() for r in [c0])
            recs.append(mk(county, "", office, c0, party, ev + ed, ev, ed,
                           district=district))
    return recs


COTTLE_RACE_RE = re.compile(
    r"^(?:US SENATOR|US REP|GOVERNOR|LT GOVERNOR|ATTNY GENERAL|COMPTROLLER|"
    r"COMM GLO|AGRICULTURE|RAILROAD COMM|CH JUSTICE SC|JUSTICE #\d|"
    r"APPEALS #\s*\d|JP|DEM CHAIR|PROP \d)", re.I)


def cottle(sheets, county, party):
    recs = []
    for name, rows in sheets:
        race = None
        for row in rows:
            c0 = str(row[0] or "").strip()
            if not c0 or c0.upper().startswith(("DEM CANDIDATES", "EV & ED")):
                continue
            if c0.upper() == "AGRICULTURE":
                race = "COMM OF AG"
                continue
            if COTTLE_RACE_RE.match(c0) or OFFICE_LEAD_WORDS.match(c0):
                race = c0
                continue
            if race is None or not c0:
                continue
            office, district = resolve_office(race)
            ev = sum((num(row[i]) or 0) for i in range(7, 12) if i < len(row))
            ed = sum((num(row[i]) or 0) for i in range(1, 6) if i < len(row))
            tot = num(row[-1]) if len(row) else None
            tot = tot if tot not in (None, 0) else ev + ed
            recs.append(mk(county, "", office, c0, party, tot, ev, ed,
                           district=district))
    return cottle_surnames(recs)


def cottle_surnames(recs):
    """Cottle reports candidates by surname only; restore the full names the
    county-level baseline uses when the surname is unambiguous for the
    canonical (office, district) key."""
    from verify_2014 import office_key
    from collections import defaultdict
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir,
                        "2014", "20140304__tx__primary__county.csv")
    index = defaultdict(dict)
    with open(base) as fh:
        for row in csvmod.DictReader(fh):
            c = (row["candidate"] or "").strip()
            if not c or c == "Total":
                continue
            votes = (row["votes"] or "").replace(",", "").strip()
            if votes and not votes.isdigit() and " " in votes:
                continue
            parts = [tk for tk in name_key(c).split()
                     if tk.upper() not in ("III", "JR", "II", "SR", "IV")]
            if parts:
                okey = office_key((row["office"] or "").strip(),
                                  (row["district"] or "").strip())
                index[parts[-1]][(okey, c)] = 1
    for r in recs:
        if " " in r["candidate"]:
            continue
        parts = [tk for tk in name_key(r["candidate"]).split()
                 if tk.upper() not in ("III", "JR", "II", "SR", "IV")]
        surname = parts[-1] if parts else ""
        if not surname:
            continue
        okey = office_key(r["office"], r["district"] or "")
        cands = sorted({c for (ok, c) in index.get(surname, {})
                        if ok == okey})
        if len(cands) == 1:
            r["candidate"] = cands[0]
            continue
        # office-only fallback (fills in a district the source omitted)
        cands2 = sorted({c for (ok, c) in index.get(surname, {})
                         if ok[0] == okey[0]})
        if len(cands2) == 1:
            r["candidate"] = cands2[0]
            dists = sorted({ok[1] for (ok, c) in index.get(surname, {})
                            if c == cands2[0]})
            if len(dists) == 1 and not (r["district"] or "").strip():
                r["district"] = dists[0]
    return recs


# ---------------------------------------------------------------------------
# cass: sheets EARLY (early total & per-precinct), GRAND (election day),
# TOTALS (grand total per precinct); skip RUN-OFF. Race labels share their row
# with the first candidate.
# ---------------------------------------------------------------------------
def cass(sheets, county, party):
    recs = []
    for name, rows in sheets:
        lname = name.lower()
        if "run-off" in lname or "runoff" in lname:
            continue
        if "summary" in lname or re.match(r"totals?", lname.strip()) or "total " in lname:
            phase = "total"
        elif lname.startswith("early"):
            phase = "early"
        else:
            phase = "election"
        labels = []
        for row in rows:
            if str(row[1] or "").strip().upper().startswith("CANDIDATE"):
                for i in range(2, len(row)):
                    t = str(row[i] or "").strip()
                    if not t:
                        continue
                    if re.match(r"^total", t, re.I):
                        continue
                    if re.match(r"\s*\d", t):
                        labels.append((i, precinct_name(re.sub(r"\s+", " ", t))))
                break
        if not labels:
            continue
        race = None
        for row in rows:
            c0 = str(row[0] or "").strip()
            if not c0:
                continue
            if re.search(r"PRIMARY ELECTION|RUN-OFF", c0, re.I):
                continue
            vals = [(i, num(row[i])) for i, _ in labels]
            vals = [(i, v) for i, v in vals if v is not None]
            shared = False
            if c0:
                # any nonempty col0 row in these sheets is a race label, which
                # shares its row with the first candidate
                race = c0
                shared = True
                if not vals:
                    continue
                cand = str(row[1] if len(row) > 1 else "").strip()
                if not cand:
                    continue
            if race is None or not vals:
                continue
            if not shared:
                cand = c0 or str(row[1] if len(row) > 1 else "").strip()
            office, district = resolve_office(race)
            for i, pct in labels:
                v = num(row[i])
                if v is None:
                    continue
                if phase == "early":
                    recs.append(mk(county, pct, office, cand, party, v, v, "",
                                   district=district))
                elif phase == "total":
                    recs.append(mk(county, pct, office, cand, party, v, "", "",
                                   district=district))
                    recs[-1]["_total_only"] = True
                else:
                    recs.append(mk(county, pct, office, cand, party, v, "", v,
                                   district=district))
    return cottle_surnames(recs)


# ---------------------------------------------------------------------------
# culberson: 2-row header; office blocks col0 / candidates col1; ED pct cols
# 2..5, EV pct cols 6..9; totals columns to the right are skipped. The race
# label shares its row with the first candidate.
# ---------------------------------------------------------------------------
def culberson(sheets, county, party):
    recs = []
    for name, rows in sheets:
        labels = []
        for ri, row in enumerate(rows):
            c0 = str(row[0] or "").strip()
            if c0.lower() == "office" or str(row[1] or "").strip().lower() == "candidate":
                phrow = rows[ri - 1] if ri > 0 else None
                groups = {}
                if phrow:
                    cur = None
                    for i in range(1, min(len(phrow), 14)):
                        t = str(phrow[i] or "").strip()
                        if t and "day" in t.lower():
                            cur = "election"
                        if t and t and "early" in t.lower():
                            cur = "early"
                        if cur:
                            groups[i] = cur
                pctlabels = {}
                for i in range(2, min(len(row), 14)):
                    t = str(row[i] or "").strip()
                    if t.lower().startswith("pct") and re.search(r"\d", t):
                        ph = groups.get(i, groups.get(i - 4, "election"))
                        pctlabels[i] = (ph, precinct_name(t))
                labels = sorted(pctlabels.items())
                break
        if not labels:
            continue
        race = None
        for row in rows:
            c0 = str(row[0] or "").strip()
            cand = str(row[1] or "").strip()
            if c0.lower() in ("office", "candidate", "total", "turnout", "county"):
                continue
            if c0:
                # the race label sits in col0; it shares its row with the
                # first candidate
                race = c0
            if race is None or not cand:
                continue
            office, district = resolve_office(race)
            for i, (ph, pct) in labels:
                v = num(row[i])
                if v is None:
                    continue
                if ph == "early":
                    recs.append(mk(county, pct, office, cand, party, v, v, "",
                                   district=district))
                else:
                    recs.append(mk(county, pct, office, cand, party, v, "", v,
                                   district=district))
    return cottle_surnames(recs)


# ---------------------------------------------------------------------------
# panola: race rows uppercase col0; candidate rows col0 with 'EARLY'/'PRECINCT'
# markers in col4; precinct votes follow with a TOTAL final column
# ---------------------------------------------------------------------------
def panola(sheets, county, party):
    recs = []
    for name, rows in sheets:
        labels = []
        for row in rows:
            if any(str(row[i] or "").strip().upper().startswith("PRECINCTS")
                   for i in range(0, 8)):
                pos = next(i for i in range(0, len(row))
                           if str(row[i] or "").strip().upper().startswith("PRECINCTS"))
                start = pos + 2
                for i in range(start, len(row)):
                    t = str(row[i] or "").strip()
                    if t == "TOTAL":
                        break
                    nv = num(row[i])
                    if nv is not None:
                        labels.append((i, str(int(nv))))
                break
        if not labels:
            continue
        race = None
        last_cand = None
        for row in rows:
            c0 = str(row[0] or "").strip()
            mark = str(row[4] or "").strip().upper() if len(row) > 4 else ""
            if c0 and not mark and not any(num(row[i]) is not None
                                           for i, _ in labels):
                race = c0
                last_cand = None
                continue
            if mark in ("EARLY", "PRECINCT", "ABSENTEE", "EARLY VOTING"):
                cand = c0
                last_cand = cand
                office, district = resolve_office(race)
                for i, pct in labels:
                    v = num(row[i])
                    if v is None:
                        continue
                    if mark.startswith("EARLY"):
                        recs.append(mk(county, pct, office, cand, party, v, v,
                                       "", district=district))
                    else:
                        recs.append(mk(county, pct, office, cand, party, v, "",
                                       v, district=district))
    return cottle_surnames(recs)


HANDLERS.update({
    "cottle": cottle,
    "cass": cass,
    "culberson": culberson,
    "panola": panola,
    "rains": rains,
    "falls": falls,
    "franklin": franklin,
    "kimble": kimble,
    "hansford": hansford,
    "hood": hood,
    "hockley": hockley,
    "armstrong": armstrong,
    "wichita": wichita,
    "shackelford": shackelford,
})
