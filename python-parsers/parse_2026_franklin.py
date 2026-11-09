#!/usr/bin/env python3
"""Parse Franklin County 2026 primary reports: candidates as rows, one column
per (precinct, vote-method). Header words repeat group labels:

  ABBM 101 ... ABBM 402  ABBM TOTAL  EV-P 101 ... EV-P TOTAL  ABBM/EV TOTAL
  ED 101 ... ED TOTAL  GRAND TOTAL

(the block may wrap or split its label baselines, so the parser collects ids
per group from the words and positions totals by formula).

Value order in every data row: ab ids, ABBM TOTAL, ev ids, EV-P TOTAL,
ABBM/EV TOTAL, ed ids, ED TOTAL, GRAND TOTAL.

Emits one row per (precinct, candidate): votes = ABBM+EV-P+ED for that
precinct, plus breakdown columns. Party from filename ('_dem'/'_rep').

Rows extracted with pdfplumber (pdftotext truncates rows on later pages of
these wide tables).

Usage:
  uv run python3 python-parsers/parse_2026_franklin.py -c COUNTY -o OUT.csv
        SOURCE-dem.pdf SOURCE-rep.pdf
"""

import argparse
import os
import re
import sys

import pdfplumber

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers_2026 import normalize_office, clean_candidate, precinct_name, write_county_csv  # noqa: E402

FIELDNAMES = ["county", "precinct", "office", "district", "party", "candidate",
              "votes", "absentee", "early_voting", "election_day", "provisional", "limited"]

SKIP_RE = re.compile(
    r"(FRANKLIN COUNTY|MARCH 3|OFFICIAL ELECTION|OFFICAL ELECTION|"
    r"REGISTERED VOTER|ABBM = ABSENTEE|EV-P = EARLY|ED = ELECTION|= ABSENTEE BALLOT)", re.I)


def page_lines(pdf_path):
    """Lines per page as lists of words (dicts with x0/x1/top/text), baselines
    separated by a small top tolerance."""
    with pdfplumber.open(pdf_path) as pdf:
        for pg in pdf.pages:
            cells = pg.extract_words(x_tolerance=1.0)
            cells.sort(key=lambda c: (c['top'], c['x0']))
            cur, prev_top = [], None
            for c in cells:
                if prev_top is None or c['top'] - prev_top <= 2.5:
                    cur.append(c)
                    prev_top = c['top'] if prev_top is None else max(prev_top, c['top'])
                else:
                    cur.sort(key=lambda cc: cc['x0'])
                    yield cur
                    cur, prev_top = [c], c['top']
            if cur:
                cur.sort(key=lambda cc: cc['x0'])
                yield cur


def parse_header(block_text, prev):
    """Update layout from consecutive header lines (already joined). Returns
    layout dict or prev layout."""
    toks = block_text.split()
    ids = {"a": [], "e": [], "d": []}
    cur = None
    for t in toks:
        up = t.upper().replace("-", "")
        if up in ("ABBM", "EVP", "ED", "GRAND") or up in ("ABBM/EV",):
            cur = {"ABBM": "a", "EVP": "e", "ED": "d", "GRAND": "g",
                   "ABBM/EV": "x"}[up]
            continue
        if up == "TOTAL":
            continue
        if cur in ids:
            ids[cur].append(t)
    n = len(ids["a"])
    if n and len(ids["e"]) == n and len(ids["d"]) == n:
        return {
            "precincts": [precinct_name(t) for t in ids["a"]],
            "n": n,
            "nvals": 3 * n + 5,
        }
    return prev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--county", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("sources", nargs="+")
    args = ap.parse_args()

    records, warnings = [], []
    for src in args.sources:
        base = os.path.basename(src).lower()
        party = "REP" if "_rep" in base else "DEM" if "_dem" in base else "NA"
        layout = None
        title = None
        acc = None
        for words in page_lines(src):
            txt = " ".join(w['text'] for w in words)
            if re.search(r"\bABBM\b|\bEV-P\b|\bABBM/EV\b|\bABB-M/EV\b", txt, re.I) or \
               (re.fullmatch(r"(?:GRAND\s+TOTAL|TOTAL\s*)+", txt, re.I) and len(words) >= 3):
                acc = (acc or "") + " " + txt if acc is not None else txt
                # try each time; keep layout once ids seen
                new_layout = parse_header(acc, layout)
                if acc is not None and "GRAND" in acc.upper() and new_layout:
                    layout = new_layout
                    acc = None
                continue
            # legend/footer lines
            if SKIP_RE.search(txt):
                continue
            ints = [w for w in words if re.fullmatch(r"\d[\d,]*", w['text'])]
            if layout is None or False:
                if not ints and re.search(r"[A-Z]", txt):
                    title = txt
                continue
            nvals = layout["nvals"]
            if len(ints) == nvals:
                name = " ".join(w['text'] for w in words if w['x1'] <= ints[0]['x0'])
                if not name:
                    name = txt[: txt.find(ints[0]['text'])].strip()
                if re.match(r"^no\.? of voters", name, re.I) or \
                   re.match(r"^provisionals? cast", name, re.I):
                    continue
                if not name:
                    warnings.append(f"unnamed row: {txt!r}")
                    continue
                vals = [int(w['text'].replace(",", "")) for w in ints]
                n = layout["n"]
                ab, ev, ed = vals[0:n], vals[n + 1: 2 * n + 1], vals[2 * n + 3: 3 * n + 3]
                if not (len(ab) == len(ev) == len(ed) == len(layout["precincts"])):
                    warnings.append(f"slice mismatch: {txt!r}"
                                    f" ({len(ab)}/{len(ev)}/{len(ed)} n={n})")
                    continue
                norm = normalize_office(title or "")
                office, district = norm if norm else ((title or "").strip(), "")
                for i, pid in enumerate(layout["precincts"]):
                    records.append({
                        "precinct": pid,
                        "office": office,
                        "district": district,
                        "party": party,
                        "candidate": clean_candidate(name),
                        "votes": str(ab[i] + ev[i] + ed[i]),
                        "absentee": str(ab[i]),
                        "early_voting": str(ev[i]),
                        "election_day": str(ed[i]),
                    })
                title = None
            elif not ints:
                if re.fullmatch(r"[A-Z0-9 ,.'\"()/-]+", txt):
                    title = txt
            elif len(ints) <= 2 and len(words) <= 6:
                title = txt
            else:
                warnings.append(f"unparsed: {txt!r}")

    write_county_csv(args.out, args.county, records, FIELDNAMES)
    print(f"{args.county}: wrote {len(records)} rows -> {args.out} (warn {len(warnings)})")
    for wtxt in warnings[:10]:
        print("  WARN", wtxt)


if __name__ == "__main__":
    main()
