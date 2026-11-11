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
