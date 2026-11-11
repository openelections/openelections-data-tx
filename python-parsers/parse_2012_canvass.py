#!/usr/bin/env python3
"""'Canvass — Total Voters' PDF grids (jim_hogg, llano): those pages print
candidate names as vertical (rotated) column headers; the data rows are
horizontal. Parsed from the pdftotext -bbox word stream: header words are
clustered by x-overlap (wrapped names merge), data rows read per y-band."""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from helpers_2026 import (write_county_csv, normalize_office,  # noqa: E402
                          precinct_name)
from parse_2012_asc import _base, expand_2012  # noqa: E402
import verify_2012 as V  # noqa: E402

FIELDNAMES = ["county", "precinct", "office", "district", "party", "candidate", "votes"]


def bbox_words(source):
    """(x, y, x1, y1, text) words of one page, plus page numbers as a list
    of (page, words). One list per page in the document order."""
    r = subprocess.run(["pdftotext", "-bbox", source, "-"],
                       capture_output=True, timeout=300)
    import xml.etree.ElementTree as ET
    root = ET.fromstring(r.stdout.decode("utf-8", errors="replace"))
    XH = '{http://www.w3.org/1999/xhtml}'
    pages = []
    page = 0
    for pel in root.iter():
        if pel.tag != XH + 'page':
            continue
        page += 1
        wds = []
        for w in pel.iter():
            if w.tag == XH + 'word':
                wds.append((float(w.get('xMin')), float(w.get('yMin')),
                            float(w.get('xMax')), float(w.get('yMax')),
                            (w.text or '').strip()))
        pages.append(wds)
    return pages


def _char_positions(line):
    return [(m.start(), m.group(0)) for m in re.finditer(r"\S+", line)]


def parse_canvass(county, sources, party_default=None):
    """Per page: race title line ('President -'), a fixed-column header line
    ('Precinct/Absentee/...'), then (rotated) candidate name columns, then
    data rows 'precinct + 6 fixed + N candidate ints'. Values read by
    character position; candidate headers clustered by x-overlap."""
    out = []
    for src in sources:
        party = _base.party_from_filename(src, party_default or "")
        import subprocess
        txt = subprocess.run(["pdftotext", "-layout", "-nopgbrk", src, "-"],
                             capture_output=True, timeout=300) \
            .stdout.decode("latin-1", errors="replace")
        for ptxt in txt.split("\x0c"):
            cur_race = None
            cand_ranges = []
            fixed = {}
            data_rows = []
            for line in ptxt.splitlines():
                toks = _char_positions(line)
                if re.search(r"\d{4}-\d\d-\d\d", line) \
                        or "Total Number of Voters" in line \
                        or "Precincts Reporting" in line \
                        or "Page " in line and " of " in line:
                    continue
                if not cur_race:
                    m = re.match(r"^\s*([A-Z][^\-]{2,60})\s-\s*$", line)
                    if m and not re.search(r"Voters|Official|Ballot|County|Number",
                                           line, re.I) and re.search(
                            r"President|Senator|Representative|Commissioner|Justice|"
                            r"Judge|Board|Court|Attorney", line, re.I):
                        cur_race = m.group(1).strip()
                        cand_ranges = []
                        fixed = {}
                        data_rows = []
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
                if re.match(r"^\s*(\d{1,4}|Totals)\b", line):
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
                            for rng in cand_ranges:
                                if lo <= rng[1] + 2 and hi >= rng[0] - 2:
                                    rng[0] = min(rng[0], lo)
                                    rng[1] = max(rng[1], hi)
                                    rng[2].append((lo, t))
                                    merged = True
                                    break
                            if not merged:
                                cand_ranges.append([lo, hi, [(lo, t)]])
            if not cand_ranges or not data_rows:
                continue
            cols = [(r[0], re.sub(r"\s+", " ",
                    ' '.join(t for _s, t in sorted(r[2], key=lambda x: x[0]))).strip())
                    for r in sorted(cand_ranges, key=lambda r: r[0])]
            cols = [(x, n) for x, n in cols
                    if n and n[:6].lower() not in ('totals', 'continu')
                    and not re.fullmatch(r"\d+", n)]
            if not cols:
                continue
            for line in data_rows:
                toks = _char_positions(line)
                if not toks or not re.fullmatch(r"\d{1,4}", toks[0][1], re.I):
                    continue
                pct = precinct_name(toks[0][1])
                if pct.lower().startswith('total'):
                    continue
                pstart = fixed.get("percent", (10 ** 6, 10 ** 6))[0]
                # candidate values ordered by x map 1:1 to the name columns
                # (which are also x-ordered); the running-'Totals' column sits
                # right of the last name and has no header
                ints_all = [(st, int(t.replace(",", ""))) for st, t in toks
                            if re.fullmatch(r"\d{1,4}", t, re.I)]
                # the first int is the precinct
                vals = ints_all[1:]
                # drop the fixed columns: absentee/early/election/total are
                # the first 4 ints after precinct whose x sit left of the
                # leftmost name anchor (cols[0][0]); the 'registered' value
                # also sits left (x < cols[0][0]); if a value lands right of
                # the rightmost name anchor (x > cols[-1][0]) it is the
                # running-'Totals' column (no header) — skipped
                cvals = [v for xst, v in vals if xst >= cols[0][0] - 20
                         and xst <= cols[-1][0] + 40]
                if len(cvals) != len(cols):
                    continue
                for (cx, cname), v in zip(cols, cvals):
                    out.append({"precinct": pct, "race": cur_race,
                                "candidate": cname,
                                "votes": v, "party": party})
    return out




def load_baseline_names():
    """(party, name_key) -> raw SOS candidate name."""
    path = HERE + os.sep + os.pardir + os.sep + '2012' + os.sep + \
        '20120529__tx__primary__county.csv'
    import csv as _csv
    out = {}
    with open(path) as fh:
        for r in _csv.DictReader(fh):
            c = (r["candidate"] or "").strip()
            if not c or c == "Total":
                continue
            out[((r["party"] or "").strip().upper(), V.name_key_2012(c))] = c
    return out


def fix_names(county, out, party):
    """Candidate clusters whose y-order text is REVERSED (or otherwise
    mismatched) get the SOS order when the reversed/multi-rotation version
    matches uniquely."""
    names = load_baseline_names()
    n = 0
    for r in out:
        cand = r["candidate"]
        toks = cand.split()
        if 1 < len(toks) <= 3:
            party = r["party"] or party
            for rot in ([toks[i:] + toks[:i] for i in range(len(toks))]
                        + [list(reversed(toks))]
                        + [(list(reversed(toks))[i:] + list(reversed(toks))[:i])
                           for i in range(len(toks))]):
                k = V.name_key_2012(" ".join(rot))
                if (party, k) in names:
                    if cand != names[(party, k)]:
                        r["candidate"] = names[(party, k)]
                        n += 1
                    break
    return n


def _norm_race(race, party=None):
    race = re.sub(r"\s+", " ", race).strip()
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
        office, district = _norm_race(r["race"])
        rows.append({"county": county, "precinct": r["precinct"],
                     "office": office, "district": district,
                     "party": r["party"] or party_default or None,
                     "candidate": r["candidate"], "votes": r["votes"]})
    write_county_csv(out, county, rows, FIELDNAMES)
    print(f"wrote {out}: {len(rows)} rows")
    return len(rows)
