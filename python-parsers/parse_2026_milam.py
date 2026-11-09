#!/usr/bin/env python3
"""Parse the Milam County 2026 primary 'Canvass Results Report' sidecar from
ocr_api_2026 (transposed canvass): each race block spans page-width chunks
that repeat the same precinct rows per column-chunk:

  <race title> - <REPUBLICAN|DEMOCRATIC> PARTY
  <candidate names, 'Precinct', 'Cast Votes', 'Undervotes', 'Overvotes',
   'Absentee Voting Ballots Cast', 'Early Voting Ballots Cast' label cells>
  <precinct id>  <counts...>
  Totals  <counts...>

Only the chunk whose labels include 'Cast Votes' carries per-candidate votes;
later chunks (Election Day / Total Ballots Cast / Registered Voters) are
race-level and skipped. Per-candidate method breakdowns aren't in the source.

Usage:
  uv run python3 python-parsers/parse_2026_milam.py -c COUNTY -o OUT.csv
        SIDE.ocr.txt [more...]
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers_2026 import normalize_office, clean_candidate, precinct_name, write_county_csv  # noqa: E402

FIELDNAMES = ["county", "precinct", "office", "district", "party", "candidate",
              "votes", "absentee", "early_voting", "election_day", "provisional", "limited"]

TITLE_RE = re.compile(
    r"(SENAT|REPRESENTAT|GOVERNOR|JUDGE|COURT|COMMISSION|BOARD|ATTORNEY|"
    r"JUSTICE|LAND OFFICE|AGRICULTURE|COMPTROLLER|RAILROAD|DISTRICT CLERK|"
    r"SHERIFF|TAX ASSESSOR|TREASURER|COUNTY CHAIR|CONSTABLE)", re.I)
NON_CAND = re.compile(
    r"^(Precinct|Total Ballots Cast|Registered Voters|Turnout Percentage|"
    r"Absentee Voting Ballots Cast|Early Voting Ballots Cast|Election Day "
    r"Voting Ballots Cast)$", re.I)

ROW_RE = re.compile(r"^(Totals|\d{1,3}[A-Z]?)\s+((?:\d[\d,]*\s*)+)$", re.I)


def blocks(path):
    for i, bl in enumerate(re.split(r"\n\s*\n", open(path).read())):
        lines = [l.strip() for l in bl.splitlines() if l.strip()]
        if lines:
            yield i, lines


_LOCAL_PAGES = {}


def page_title_local(path, page):
    """Local PaddleOCR of one page; return the race title line if present."""
    if path in _LOCAL_PAGES:
        return _LOCAL_PAGES.get(page)
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ocr_local", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "ocr_2026.py"))
        ocr_local = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ocr_local)
        if not hasattr(ocr_local, "_OCR") or ocr_local._OCR is None:
            ocr_local._init_worker("en")
        os.environ["TABLE_MODE"] = "0"
        ocr_local._DPI = 200
        import tempfile, subprocess
        with tempfile.TemporaryDirectory() as tmp:
            cmd = ["pdftoppm", "-png", "-r", "200",
                   path, os.path.join(tmp, "p")]
            subprocess.run(cmd, check=False, capture_output=True)
            pngs = sorted(f for f in os.listdir(tmp) if f.endswith(".png"))
            lines = ocr_local._ocr_png(os.path.join(tmp, pngs[page]))
    except Exception as e:  # noqa: BLE001
        return None
    title = None
    for line in (lines or []):
        t = re.sub(r"\s+", " ", line).strip()
        if re.search(r"PARTY\s*-?$", t, re.I) or TITLE_RE.search(t) and \
                re.fullmatch(r"[A-Z][A-Za-z0-9 ,.'&()/#-]{3,80}", t):
            title = t
            break
    _LOCAL_PAGES[path] = page
    _LOCAL_PAGES[page] = title
    return title


PAGE_JUNK = re.compile(
    r"^(Canvass Results Report|Milam County, Texas|Official Results|"
    r"OFFICIAL TALLY|2026-3-3 E|Ballots Cast|Run Time|Run Date|Page \d+|"
    r"\d?[0-9]:\d\d [AP]M|\d+/\d+/\d+|Texas|March 3, 2026)$", re.I)


def title_key(t):
    mm = re.search(r"(REPUBLICAN|DEMOCRATIC|NONPARTISAN)", t, re.I)
    party = {"REPUBLICAN": "REP", "DEMOCRATIC": "DEM",
             "NONPARTISAN": "NP"}.get(mm.group(1).upper() if mm else "X", "NP")
    return (re.sub(r"\s+", " ", t).strip(" -"), party)


def parse(path):
    """Return {(title, party): {"chunks": [(labels, rows)...]}} + warnings.
    A page's data chunk binds to that page's race title; when the API dropped
    the title, the chunk binds to the next title seen (each report page
    repeats its race's title, and the trailing columns continue the same
    race), recovering page-1 chunks whose titles were dropped."""
    races_meta = {}
    warnings = []
    pending_parts = None    # (labels, rows) awaiting a title
    for pageno, blk in blocks(path):
        title = None
        labels = []
        rows = []
        for t in blk:
            m = re.match(r"^((?:United States |State )?.{0,60}?)\s*-?\s*"
                         r"\s*((?:REPUBLICAN|DEMOCRATIC)?)\s*PARTY\s*$", t,
                         re.I)
            if m and TITLE_RE.search(t) and "Ballots Cast" not in t and \
                    "Registered" not in t:
                title = t
                continue
            if title is None:
                # chunk content before this page's (dropped) title
                mrow = ROW_RE.match(t)
                if mrow and re.match(r"^(Totals|\d{1,3})", mrow.group(1)):
                    rows.append((mrow.group(1),
                                 [int(x.replace(",", ""))
                                  for x in re.findall(r"\d[\d,]*",
                                                      mrow.group(2))]))
                elif not PAGE_JUNK.fullmatch(t) and not is_int_cell(t):
                    labels.append(t)
                continue
            # titled page
            if NON_CAND.fullmatch(t) or PAGE_JUNK.fullmatch(t):
                continue
            mrow = ROW_RE.match(t)
            if mrow and re.match(r"^(Totals|\d{1,3})", mrow.group(1)):
                rows.append((mrow.group(1),
                             [int(x.replace(",", ""))
                              for x in re.findall(r"\d[\d,]*", mrow.group(2))]))
            elif not is_int_cell(t) and len(t) < 60 and ROW_RE.match(t) is None:
                labels.append(t)
        # bind
        if title:
            if labels and rows:
                races_meta.setdefault(title_key(title), {"chunks": []}) \
                    ["chunks"].append((labels, rows))
            if pending_parts is not None:
                plabels, prows = pending_parts
                if plabels and prows:
                    races_meta.setdefault(title_key(title), {"chunks": []}) \
                        ["chunks"].append((plabels, prows))
                pending_parts = None
        elif (labels or rows) and pending_parts is None:
            pending_parts = (labels, rows)
    return races_meta, warnings


def is_int_cell(t):
    return bool(re.fullmatch(r"[\d,]{1,10}", t))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--county", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("sources", nargs="+")
    args = ap.parse_args()
    records = []
    warnings = []
    for path in args.sources:
        meta, warns = parse(path)
        warnings.extend(f"{os.path.basename(path)}: {w}" for w in warns)
        for (title, party), info in meta.items():
            norm = normalize_office(title) or (re.sub(r"\s+", " ", title), "")
            office, district = norm
            chunks = info["chunks"]
            cand_cols = None
            rows = None
            for labs, rows_ in chunks:
                if any(re.fullmatch(r"Cast Votes", l, re.I) for l in labs):
                    cand_cols, rows = labs, rows_
                    break
            if cand_cols is None:
                cand_cols, rows = chunks[0]
            labels = cand_cols
            # candidate columns: labels before 'Cast Votes'
            n_cand = 0
            for l in labels:
                if re.fullmatch(r"Cast Votes", l, re.I):
                    break
                n_cand += 1
            cands = labels[:n_cand]
            # trailing BC labels map to the last 2 ints
            tail = [l for l in labels[n_cand:]]
            for pid, vals in rows:
                if pid.lower() == "totals":
                    continue
                if len(vals) != len(labels):
                    if len(vals) > len(labels):
                        warnings.append(f"row {pid}: extra values"
                                        f" ({len(vals)} vs {len(labels)})")
                    continue
                for j, cand in enumerate(cands):
                    records.append({
                        "precinct": precinct_name(pid),
                        "office": office,
                        "district": district,
                        "party": party,
                        "candidate": clean_candidate(cand),
                        "votes": str(vals[j]),
                    })
    write_county_csv(args.out, args.county, records, FIELDNAMES)
    print(f"{args.county}: wrote {len(records)} rows -> {args.out} "
          f"(warn {len(warnings)})")
    for w in warnings[:10]:
        print("  WARN", w)


if __name__ == "__main__":
    main()
