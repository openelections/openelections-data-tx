#!/usr/bin/env python3
"""Parse the May 29, 2012 primary PDF 'Precinct Report' exports (text layer
via pdftotext -layout): per-precinct blocks with candidate rows carrying
(count, pct%) vote pairs whose LAST pair is the Total column.

Counties: bee, cherokee, coke, denton, gray, jim_wells, willacy, jack
(and canvass-style counties jim_hogg/llano via parse_canvass).

Usage:
  uv run python3 python-parsers/parse_2012_pdf.py -c Bee \
      -o 2012/counties/20120529__tx__primary__bee__precinct.csv SRC...
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from helpers_2026 import normalize_office, precinct_name, write_county_csv  # noqa: E402
from parse_2012_asc import _base, expand_2012  # noqa: E402
from verify_2012 import name_key_2012  # noqa: E402

FIELDNAMES = ["county", "precinct", "office", "district", "party", "candidate", "votes"]

SKIP_RE = re.compile(r"Cast Votes|Over Votes|Under Votes|Registered Voters|Ballots Cast"
                     r"|Total Votes|Voters :|Precincts Reporting|Run Date|Election Date"
                     r"|Total Number|Page \d+ of|Vote For", re.I)


def pdf_text(path, layout=True):
    args = ["pdftotext"]
    if layout:
        args.append("-layout")
    args.append(path)
    args.append("-")
    r = subprocess.run(args, capture_output=True, timeout=120)
    return r.stdout.decode("latin-1", errors="replace")


def pdf_page_count(path):
    try:
        r = subprocess.run(["pdfinfo", path], capture_output=True, timeout=60)
        m = re.search(r"Pages:\s+(\d+)", r.stdout.decode())
        return int(m.group(1)) if m else 1
    except Exception:
        return 999


RACE_RE = re.compile(r"^([^,]*?)(?:,\s*Vote For\s*\d+)?\s*((?:De|Re)mocratic Party|\bDEM\b|\bREP\b)?[,\s]*$", re.I)


def _norm_race(race, party=None):
    race = re.sub(r"\s+", " ", race).strip()
    m = re.match(r"^(.*?),?\s*Vote For\s*\d+", race, re.I)
    if m:
        race = m.group(1)
    race = re.sub(r"\s+De(mocratic)?\s+Party$|\s+Re(publican)?\s+Party$", "", race, flags=re.I)
    race = re.sub(r"\s(Democratic|Republican)\s+Party", "", race, flags=re.I)
    race = re.sub(r"[,\s]*(DEM|REP)$", "", race, flags=re.I)
    race = expand_2012(race)
    res = normalize_office(race)
    return (res[0], res[1] if len(res) > 1 else "") if res else (race.title(), "")


def _party_of(race, filename_party):
    m = re.search(r"\b(DEM|REP)\b", race, re.I)
    if m:
        return m.group(1).upper()
    m2 = re.search(r"(De|Re)mocratic", race, re.I)
    if m2:
        return m2.group(0).upper()[:3] if False else ("DEM" if m2.group(1).lower().startswith("de") else "REP")
    return filename_party


XH_NS = '{http://www.w3.org/1999/xhtml}'


def bbox_words(source):
    """(page_no, x, y, text) words from pdftotext -bbox XML."""
    import xml.etree.ElementTree as ET
    r = subprocess.run(["pdftotext", "-bbox", source, "-"],
                       capture_output=True, timeout=300)
    root = ET.fromstring(r.stdout.decode("utf-8", errors="replace"))
    out = []
    page = 0
    for el in root.iter():
        if el.tag == XH_NS + 'page':
            page += 1
        elif el.tag == XH_NS + 'word':
            try:
                out.append((page, float(el.get('xMin')), float(el.get('yMin')),
                            float(el.get('xMax')), float(el.get('yMax')),
                            el.text or ''))
            except (TypeError, ValueError):
                continue
    return out


def _lines(words, tol=3.0):
    """5-tuples (x, y, x1, y1, text) of one page -> [(y, [words])] where
    the words share the same y band."""
    ws = sorted(words, key=lambda w: (round(w[1], 1), w[0]))
    out = []
    for w in ws:
        if out and abs(w[1] - out[-1][0][1]) < tol:
            out[-1].append(w)
        else:
            out.append([w])
    return [(l[0][1], l) for l in out]


def parse_canvass(county, sources, party_default=None):
    """'Canvass — Total Voters' grids (jim_hogg, llano): pages where the
    visual columns are candidate headers (rotated text lines) above the
    data rows; each data row = precinct + 6 fixed numbers + one integer per
    candidate column. Candidate headers are clustered by x-overlap in the
    header band between the race title and the first data row."""
    import parse_2014_asc as _asc
    out = []
    for src in sources:
        party = _asc.party_from_filename(src, party_default or "")
        pages = {}
        for pg, x, y, x1, y1, t in bbox_words(src):
            pages.setdefault(pg, []).append((x, y, x1, y1, (t or '').strip()))
        for pg in sorted(pages):
            wds = pages[pg]
            lines = _lines(wds)
            FIXED = {'precinct', 'absentee', 'early', 'election', 'total',
                     'registered', 'percent', 'ballots', 'cast', 'voters',
                     'turnout'}
            data_y = None
            for y, l in lines:
                ints = sum(1 for w in l if re.fullmatch(r"\d{1,4}", w[4], re.I))
                if ints >= 5 and re.fullmatch(r"\d{1,4}", l[0][4], re.I):
                    data_y = y
                    break
            race_title = None
            race_y = None
            for y, l in lines:
                if y >= (data_y or 0):
                    break
                txt = ' '.join(w[4] for w in l)
                m = re.match(r"^([A-Z][^\-]{2,60})\s-\s*$", txt.strip())
                if m and not re.search(r"Voters|Official|Page\b|Ballot|County|Number",
                                       txt, re.I) and re.search(
                        r"President|Senator|Representative|Commissioner|Justice|"
                        r"Judge|Board|Court|Attorney", txt, re.I):
                    race_title = m.group(1).strip()
                    race_y = y
            if not race_title:
                continue
            region = [w for w in wds if w[1] > race_y + 1
                      and (data_y is None or w[1] < data_y)
                      and w[4].lower() not in FIXED
                      and not re.fullmatch(r"[\d.,%]+", w[4])]
            # cluster by x-overlap
            clusters = []
            for w in sorted(region, key=lambda w: w[0]):
                if clusters and w[0] - clusters[-1]['x1'] <= 14:
                    clusters[-1]['x1'] = max(clusters[-1]['x1'], w[2])
                    clusters[-1]['words'].append(w)
                else:
                    clusters.append({'x0': w[0], 'x1': w[2], 'words': [w]})
            cols = []
            for c in clusters:
                ws = sorted(c['words'], key=lambda w: w[1])
                txt = re.sub(r"\s+", " ", ' '.join(w[4] for w in ws)).strip()
                if txt and txt[:6].lower() not in ('totals', 'continu') \
                        and not re.fullmatch(r"\d+", txt):
                    cols.append((c['x0'], txt))
            if not cols:
                continue
            for y, l in lines:
                if y < (data_y or 0):
                    continue
                toks = [(w[0], w[4]) for w in l]
                if not toks or not re.fullmatch(r"\d{1,4}", toks[0][1], re.I):
                    continue
                pct = precinct_name(toks[0][1])
                if pct.lower().startswith('total'):
                    continue
                pcts = [t for _x, t in toks if re.fullmatch(r"[\d,]+%", t)]
                cvals = [int(t.replace(",", "")) for _x, t in toks
                         if re.fullmatch(r"\d{1,4}", t, re.I) and _x > 430][:len(cols)]
                if len(cvals) < len(cols):
                    continue
                for (cx, cname), v in zip(cols, cvals):
                    out.append({"precinct": pct, "race": race_title,
                                "candidate": cname, "votes": v, "party": party})
    return out


def parse_report_raw(county, source, party_default=None):
    """raw-mode fallback for exports whose wide tables lose columns in
    -layout mode (cherokee's RR Unexpired race etc.): raw puts counts BEFORE
    the name, per-page headers give column order."""
    txt = pdf_text(source, layout=False)
    out = []
    cur_pct = None
    cur_race = None
    col0_is_total = False
    for line in txt.splitlines():
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^Precinct\s+(?:NO\.?\s*)?([A-Z0-9/ -]+?)\s*(?:-.*|\(.*\))?$", s, re.I)
        if m:
            cur_pct = precinct_name(m.group(1))
            cur_race = None
            continue
        if "Vote For" in s and "Votes" not in s and len(s) < 90:
            cur_race = s
            continue
        if re.search(r"Party\s+Candidate", s) or "Vote For" in s:
            col0_is_total = bool(re.search(r"Party\s+Candidate\s+(Total|Cast)", s, re.I))
            if re.search(r"Vote For", s) and re.search(r"\bDEM\b|\bREP\b", s):
                cur_race = s
            continue
        if cur_pct is None or cur_race is None or SKIP_RE.search(s):
            continue
        toks = s.split()
        counts = [int(t.replace(",", "")) for t in toks
                  if re.fullmatch(r"[\d,]+", t)]
        name_toks = [t for t in toks if not re.fullmatch(r"[\d,]+|\d[\d.,]*%", t)
                     or re.fullmatch(r"[A-Za-z]{2,}", t) and False]
        name_toks = [t for t in toks if not re.fullmatch(r"[\d,%]+", t)]
        if not counts or not name_toks or len(counts) > 8:
            continue
        votes = counts[0] if col0_is_total else counts[-1]
        cand = " ".join(name_toks)
        if not re.search(r"[A-Za-z]{2}", cand):
            continue
        out.append({"precinct": cur_pct, "race": cur_race, "candidate": cand,
                    "votes": votes, "party": party_default or ""})
    return out


def parse_report(county, sources, party_default=None):
    """Precinct-Report per-precinct blocks."""
    out = []
    for src in sources:
        party = _base.party_from_filename(src, party_default or "")
        txt = pdf_text(src)
        cur_pct = None
        cur_race = None
        for line in txt.splitlines():
            s = line.rstrip()
            m = re.match(r"^\s*Precinct\s+(?:NO\.?\s*)?([A-Z0-9/ -]+?)\s*(?:-.*|(\(.*\))|)$",
                         s, re.I) if s.strip().lower().startswith("precinct") else None
            if m:
                cur_pct = precinct_name(m.group(1))
                cur_race = None
                continue
            # race headers: 'President DEM, Vote For 1' / '.. Vote For 1 Democratic Party'
            if cur_pct is not None and "Vote For" in s:
                cur_race = s.strip()
                continue
            if SKIP_RE.search(s) and "Vote For" not in s:
                continue
            # candidate row: indented name + count/pct pairs
            m2 = re.match(r"^\s{2,}(\S.*?)\s*((?:[\d,]+\s+[\d.]+%\s*)+)$", s)
            if not m2:
                continue
            cand = m2.group(1).strip()
            numbers = re.findall(r"([\d,]+)\s+[\d.]+%", m2.group(2))
            if not numbers or cur_pct is None or cur_race is None:
                continue
            votes = int(numbers[-1].replace(",", ""))
            out.append({"precinct": cur_pct, "race": cur_race, "candidate": cand,
                        "votes": votes, "party": party})
    return out


def run_county(county, out, sources, party_default=None):
    recs = parse_report(county, sources)
    if not recs:
        recs = parse_canvass(county, sources, party_default)
        if recs:
            print('  canvass-grid parse used')
    if recs:
        # wrapped-table fallback: raw rows for (precinct, race, cand) keys
        # missing from the layout parse
        seen = {(r["precinct"], name_key_2012(r["candidate"])) for r in recs}
        extra = []
        for src in sources:
            for r in parse_report_raw(county, src,
                                      _base.party_from_filename(src, party_default or "")):
                k = (r["precinct"], name_key_2012(r["candidate"]))
                if k not in seen:
                    seen.add(k)
                    extra.append(r)
        if extra:
            print(f"  raw fallback added {len(extra)} rows")
            recs += extra
    if not recs:
        print(f"-- {county}: pdf precinct-report parse found nothing")
        return 0
    # dedupe identical page blocks across duplicate files
    seen = {}
    for r in recs:
        k = (r["precinct"], r["race"], name_key_2012(r["candidate"]))
        if k in seen and seen[k] != r["votes"]:
            pass  # keep first: duplicate files carry identical tables
        seen.setdefault(k, r["votes"])
    rows = []
    for r in recs:
        party = _party_of(r["race"], r["party"] or party_default or "")
        office, district = _norm_race(r["race"])
        if re.search(r"UNEX", r["race"].upper()) and not re.search(
                r"UNEXPIRED", (office + " " + district).upper()):
            office = office + " Unexpired Term"
        k = (r["precinct"], r["race"], name_key_2012(r["candidate"]))
        if seen.get(k) != r["votes"]:
            continue
        seen.pop(k, None)
        rows.append({"county": county, "precinct": r["precinct"],
                     "office": office, "district": district, "party": party,
                     "candidate": r["candidate"], "votes": r["votes"]})
    write_county_csv(out, county, rows, FIELDNAMES)
    print(f"wrote {out}: {len(rows)} rows")
    return len(rows)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--county", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--party", default=None)
    a = ap.parse_args()
    run_county(a.county, a.out, a.sources, a.party)


if __name__ == "__main__":
    main()
