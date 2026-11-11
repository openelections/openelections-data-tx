#!/usr/bin/env python3
"""Text-format handlers for the May 29, 2012 primary sources that are not
the standard Hart 'detail vote totals' CSV:

- bell: fixed columns (county date election .., precinct, reg, office,
  candidate, party, two vote columns)
- collin / el_paso / guadalupe: quoted phase rows
  (precinct, reg, race, seq, candidate, party, phase, votes); the 'Total'
  phase row holds the votes
- sutton: an EL30A text report inside an HTM file

The standard Hart CSV counties (cooke, fannin, grimes, marion, lampasas,
san_patricio, concho, waller, zapata xls) go through parse_2012_excel via
the magic-sniffing text loader added to load_sheets.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from helpers_2026 import normalize_office, precinct_name, write_county_csv  # noqa: E402
from parse_2012_asc import _base, expand_2012  # noqa: E402

FIELDNAMES = ["county", "precinct", "office", "district", "party", "candidate", "votes"]


PHASE_RE = re.compile(r"^(TOTAL|POLLING|PAPER|MAIL|EARLY VOTING|EARLY EDAY|ELECTION DAY( TS| OS)?|ABSEN)", re.I)
PARTY_RE = re.compile(r"^(NP|DEM|REP|LIB|GRN|IND|CON)$", re.I)


def _phase_rows(sources, county, total_kw="TOTAL"):
    """'Total'-phase rows from quoted phase-row exports where the cell order
    varies (collin: pct, reg, race, no, cand, party, phase, votes; guadalupe:
    pct, reg, race, party, no, cand, phase, votes)."""
    import csv as _csv
    out = {}
    for src in sources:
        raw = open(src, "r", encoding="latin-1", errors="replace").read()
        for row in _csv.reader(raw.splitlines(), skipinitialspace=True):
            cells = [c.strip().strip('"') for c in row if str(c).strip() != ""]
            if len(cells) < 4:
                continue
            pi = [i for i, c in enumerate(cells) if i > 0 and PHASE_RE.match(c)]
            if not pi:
                continue
            p_idx = pi[0]
            votes = None
            for c in cells[p_idx + 1:]:
                if re.fullmatch(r"-?\d[\d,]*", c):
                    votes = int(c.replace(",", ""))
                    break
            if votes is None:
                continue
            texts = [c for c in cells[1:p_idx]
                     if not re.fullmatch(r"-?\d[\d,]*", c)
                     and not PARTY_RE.match(c)]
            if len(texts) < 2:
                continue
            race = re.sub(r"\s*[-–]-?\s*(DEMS?|REPS?)\s*$", "", texts[0], flags=re.I)
            cand = texts[-1]
            key = (precinct_name(cells[0]), race.strip(), cand.strip())
            out[key] = max(votes, out.get(key, 0))
    recs = [{"office": race, "district": "", "candidate": cand,
             "precinct": pct, "votes": v, "party": None, "party2": None}
            for (pct, race, cand), v in out.items()]
    return recs


def _norm_race(race, party):
    title = _base.clean_title(expand_2012(race), "")
    res = normalize_office(title)
    return (res[0], res[1] if len(res) > 1 else "") if res else (title, "")


def run_phase(county, out, sources, party_default=None):
    import parse_2014_asc as _asc
    recs = _phase_rows(sources, county)
    if not recs:
        print(f"-- {county}: phase rows found nothing")
        return 0
    rows = []
    for r in recs:
        office, district = _norm_race(r["office"], None)
        party = r["party"] or party_default or None
        rows.append({"county": county, "precinct": r["precinct"],
                     "office": office, "district": district, "party": party,
                     "candidate": r["candidate"], "votes": r["votes"]})
    write_county_csv(out, county, rows, FIELDNAMES)
    print(f"wrote {out}: {len(rows)} rows")
    return len(rows)


def run_bell(county, out, sources, party_default=None):
    import csv as _csv
    import parse_2014_asc as _asc
    rows = []
    two_col = None
    for src in sources:
        for row in _csv.reader(open(src, encoding="latin-1", errors="replace")):
            if len(row) < 12:
                continue
            pct, reg = row[5].strip(), row[6].strip()
            office, cand, pty = row[7].strip(), row[8].strip(), row[9].strip()
            v1, v2 = row[10].strip(), row[11].strip()
            if not re.fullmatch(r"-?\d[\d,]*", v2 or ""):
                continue
            votes = int((v1 or 0).replace(",", "")) + int(v2.replace(",", ""))
            if two_col is None:
                two_col = True
            office_n, district = _norm_race(office, None)
            rows.append({"county": county, "precinct": precinct_name(pct),
                         "office": office_n, "district": district,
                         "party": pty or party_default or None,
                         "candidate": cand, "votes": votes})
    if not rows:
        print(f"-- {county}: bell rows found nothing")
        return 0
    write_county_csv(out, county, rows, FIELDNAMES)
    print(f"wrote {out}: {len(rows)} rows")
    return len(rows)


def run_sutton(county, out, sources, party_default=None):
    import parse_2012_el30 as el30
    import io as _io
    all_rows = []
    for src in sources:
        raw = open(src, "r", encoding="latin-1", errors="replace").read()
        txt = re.sub(r"<[^>]+>", "", raw)             # strip html tags
        txt = txt.replace("&nbsp;", " ").replace("&amp;", "&")
        lines = [l + "\n" for l in txt.split("\n")]
        path_like = el30.read_text_lines(src) if False else None
        # feed the EL30A line walker with the stripped text
        prev = el30.read_text_lines
        el30.read_text_lines = lambda p, _lines=lines: _lines
        try:
            all_rows += el30.parse_file(src)
        finally:
            el30.read_text_lines = prev
    if not all_rows:
        print(f"-- {county}: sutton EL30A parse found nothing")
        return 0
    rows = []
    for precinct, title, cand, votes, party in all_rows:
        if precinct is None:
            continue
        if title.startswith("__STAT__:"):
            import parse_2012_excel as _px
            stat = title[len("__STAT__:"):].strip().upper()
            p2 = "REP" if "REPUBLICAN" in stat else ("DEM" if "DEMOCRATIC" in stat else "")
            rows.append({"county": county, "precinct": precinct,
                         "office": stat.title(), "district": "", "party": p2,
                         "candidate": stat.title(), "votes": votes})
            continue
        title_e = expand_2012(title)
        res = normalize_office(title_e)
        office, district = (res[0], res[1] if len(res) > 1 else "") \
            if res else (title_e.title(), "")
        if re.search(r"UNEX", title.upper()) and "UNEXPIRED" not in office.upper():
            office = office + " Unexpired Term"
        rows.append({"county": county, "precinct": precinct,
                     "office": office, "district": district,
                     "party": party or party_default or None,
                     "candidate": cand, "votes": votes})
    write_county_csv(out, county, rows, FIELDNAMES)
    print(f"wrote {out}: {len(rows)} rows")
    return len(rows)


HANDLERS = {
    "collin": run_phase, "el_paso": run_phase, "guadalupe": run_phase,
    "bell": run_bell, "sutton": run_sutton,
}


def run_county(county, out, sources, party_default=None):
    fn = HANDLERS.get(county.lower().replace(" ", "_"), run_phase)
    return fn(county, out, sources, party_default)
