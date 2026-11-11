#!/usr/bin/env python3
"""'Canvass — Total Voters' PDF grids (jim_hogg, llano).

These canvass pages print the candidate names as ROTATED column headers
(reading down the page), interleaved with 'Ballots/Voters' and 'Cast'
subheader words at different x positions on the same layout lines. The data
rows are horizontal: 'precinct, Early, Election, Total, Registered,
Percent, <one count per candidate column>'.

The parse uses the pdftotext -bbox word stream: header-name words are
clustered by x-overlap across the page's header band (each cluster = one
candidate column; wrapped parts of one name have overlapping x ranges,
while per-word exclusion drops the rotated fixed headers, subheaders and
running-'Totals' labels); data rows are read per y-band and each integer
assigned to the nearest candidate column by x position.
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from helpers_2026 import write_county_csv, normalize_office, precinct_name  # noqa: E402
from parse_2012_asc import _base, expand_2012  # noqa: E402
import verify_2012 as V  # noqa: E402

FIELDNAMES = ["county", "precinct", "office", "district", "party", "candidate", "votes"]

XH = '{http://www.w3.org/1999/xhtml}'


def bbox_pages(source):
    """List of pages; each page is a list of (x, y, x1, y1, text)."""
    r = subprocess.run(["pdftotext", "-bbox", source, "-"],
                       capture_output=True, timeout=300)
    import xml.etree.ElementTree as ET
    root = ET.fromstring(r.stdout.decode("utf-8", errors="replace"))
    pages = []
    for pel in root.iter():
        if pel.tag == XH + 'page':
            page = []
            for w in pel.iter():
                if w.tag == XH + 'word':
                    page.append((float(w.get('xMin')), float(w.get('yMin')),
                                 float(w.get('xMax')), float(w.get('yMax')),
                                 (w.text or '').strip()))
            pages.append(page)
    return pages


def _char_positions(line):
    return [(m.start(), m.group(0)) for m in re.finditer(r"\S+", line)]


def parse_canvass(county, sources, party_default=None):
    """Per page: race title line ('President DEM -'), fixed column header
    ('Precinct/Early/...'), candidate name columns (rotated words), then
    data rows. Precinct-only rows (< 999) accepted; rows beginning with a
    4-digit running total ('1101 ...') are the running-'Totals' rows and are
    skipped."""
    out = []
    for src in sources:
        party = _base.party_from_filename(src, party_default or "")
        import subprocess
        txt = subprocess.run(["pdftotext", "-layout", src, "-"],
                             capture_output=True, timeout=300) \
            .stdout.decode("latin-1", errors="replace")
        for ptxt in txt.split("\x0c"):
            cur_race = None
            cand_cols = []
            fixed = {}
            data_rows = []
            for line in ptxt.splitlines():
                toks = _char_positions(line)
                if re.search(r"\d{4}-\d\d-\d\d", line) \
                        or "Total Number" in line \
                        or "Precincts Reporting" in line \
                        or ("Page " in line and " of " in line):
                    continue
                m = re.match(r"^\s*([A-Z][^\-]{2,60})\s-\s*$", line)
                if m and not re.search(r"Voters|Official|Ballot|County|Number",
                                       line, re.I) and re.search(
                        r"President|Senator|Representative|Commissioner|Justice|"
                        r"Judge|Board|Court|Attorney", line, re.I):
                    cur_race = m.group(1).strip()
                    cand_cols = []
                    fixed = {}
                    data_rows = []
                    continue
                if not cur_race:
                    continue
                if re.search(r"Precinct\s+(Absentee|Early)", line):
                    fixed = {}
                    for st, t in toks:
                        lt = t.lower()
                        if lt in ("absentee", "early", "election", "total",
                                  "registered", "percent"):
                            fixed[lt] = (st, st + len(t) - 1)
                    continue
                if re.search(r"Ballots\s+Ballots|Cast\s+Cast", line):
                    continue
                m2 = re.match(r"^\s*(\d{{1,3}}|Totals)\b", line)
                if m2:
                    if re.fullmatch(r"\d{{1,3}}", m2.group(1)):
                        data_rows.append(line)
                    continue
                if toks and not re.fullmatch(r"[\d,]+", toks[0][1]) \
                        and "Vote For" not in line \
                        and not re.search(r"Ballots|Cast Votes|Over Votes|"
                                          r"Under Votes|Totals", line, re.I):
                    txt2 = " ".join(t for _s, t in toks)
                    if re.search(r"[A-Za-z]", txt2) and len(txt2) < 52:
                        for st, t in toks:
                            lo, hi = st, st + len(t) - 1
                            merged = False
                            for col in cand_cols:
                                if lo <= col["x1"] + 2 and hi >= col["x0"] - 2:
                                    col["x0"] = min(col["x0"], lo)
                                    col["x1"] = max(col["x1"], hi)
                                    col["words"].append((lo, t))
                                    merged = True
                                    break
                            if not merged:
                                cand_cols.append({"x0": lo, "x1": hi,
                                                  "words": [(lo, t)]})
            if not cand_cols or not data_rows:
                continue
            cols = [(r_["x0"], re.sub(r"\s+", " ",
                    ' '.join(t for _s, t in sorted(r_["words"],
                                                   key=lambda w: w[0]))).strip())
                    for r_ in sorted(cand_cols, key=lambda r_: r_["x0"])]
            cols = [(x, n) for x, n in cols
                    if n and re.sub(r"\s+", "", n)[:9].lower()
                    not in ('totals', 'continued') and not re.fullmatch(r"\d+", n)]
            if not cols:
                continue
            for line in data_rows:
                toks = _char_positions(line)
                pct = precinct_name(toks[0][1])
                if pct.lower().startswith('total'):
                    continue
                pstart = fixed.get("percent", (10 ** 6, 10 ** 6))[0]
                cvals = [(st, int(t.replace(",", ""))) for st, t in toks
                         if re.fullmatch(r"\d{1,4}", t, re.I) and st >= pstart]
                if len(cvals) != len(cols):
                    continue
                for (x0, cname), v in zip(cols, cvals):
                    out.append({"precinct": pct, "race": cur_race,
                                "candidate": cname, "votes": v,
                                "party": party})
    return out


def load_baseline_names():
    """(party, name_key) -> raw SOS candidate name."""
    import csv as _csv
    path = HERE + os.sep + os.pardir + os.sep + '2012' + os.sep + \
        '20120529__tx__primary__county.csv'
    out = {}
    with open(path) as fh:
        for r in _csv.DictReader(fh):
            c = (r['candidate'] or '').strip()
            if not c or c == 'Total':
                continue
            out[((r['party'] or '').strip().upper(), V.name_key_2012(c))] = c
    return out


def fix_names(county, out, party):
    """Cluster names read y-ascending (rotated) may be reversed ('Romney
    Mitt'); rotations/reversals matching the SOS name per party are
    rewritten to the SOS spelling."""
    names = load_baseline_names()
    n = 0
    for r in out:
        cand = r['candidate']
        toks = cand.split()
        if 1 < len(toks) <= 3:
            try_rots = [toks[i:] + toks[:i] for i in range(len(toks))]
            try_rots += [list(reversed(toks))]
            try_rots += [(list(reversed(toks))[i:] + list(reversed(toks))[:i])
                         for i in range(len(toks))]
            party2 = r['party'] or party
            for rot in try_rots:
                k = V.name_key_2012(' '.join(rot))
                if (party2, k) in names:
                    if cand != names[(party2, k)]:
                        r['candidate'] = names[(party2, k)]
                        n += 1
                    break
    return n


def _norm_race(race, party=None):
    race = re.sub(r"\s+", " ", race).strip()
    race = re.sub(r"[,\s]+(DEM|REP|De|Re)m?ocratic?\b|\s+De(mocratic)?\b|\s+Re(publican)?\b$",
                  "", race, flags=re.I).strip()
    race = re.sub(r"\s+(DEM|REP)\s*$", "", race, flags=re.I)
    race = expand_2012(race)
    res = normalize_office(race)
    return (res[0], res[1] if len(res) > 1 else "") if res else (race.title(), "")


def run_county(county, out, sources, party_default=None):
    recs = parse_canvass(county, sources)
    if not recs:
        print(f"-- {county}: canvass parse found nothing")
        return 0
    fix_names(county, recs, party_default)
    rows = []
    for r in recs:
        office, district = _norm_race(r['race'])
        rows.append({"county": county, "precinct": r['precinct'],
                     "office": office, "district": district,
                     "party": r['party'] or party_default or None,
                     "candidate": r['candidate'], "votes": r['votes']})
    write_county_csv(out, county, rows, FIELDNAMES)
    print(f"wrote {out}: {len(rows)} rows")
    return len(rows)
