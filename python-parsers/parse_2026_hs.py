#!/usr/bin/env python3
"""Parse transposed county-canvass tables rendered as text sidecars by
ocr_api_2026 (Haskell / Panola style, March 3 2026 Texas primary): candidates
as rows, one column per voting box, one page-block per vote method (banner
'BBM' = absentee by mail, 'EV' = early voting, 'ED' = election day).

Page-block layout:
  Democratic Party Primary Election March 3, 2026 BBM
  PCT1 / PCT 1 ... PCT10 (one per line)
  TOTAL
  <race title lines>
  <candidate>  <n..>  <TOTAL>

Rows may split the label from its counts (label line + one count per line), and
may carry one extra zero before the total (OCR dup); both are normalized with a
sum check. Votes = BBM+EV+ED per box; breakdown columns emitted.

Usage:
  uv run python3 python-parsers/parse_2026_hs.py -c COUNTY -o OUT.csv
        SIDE-dem.ocr.txt SIDE-rep.ocr.txt
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
    r"(SENAT|REPRESENTATIV|GOVERNOR|JUDGE|COURT|COMMISSION|BOARD|PROP|ATTORNEY|"
    r"SHERIFF|CLERK|TREASURER|CONSTABLE|CHAIR|COMPTROLLER|LAND|FEDERAL|"
    r"JUSTICE|RAILROAD)", re.I)
SURVEY_RE = re.compile(r"^Survey\s*:", re.I)
PCT_RE = re.compile(r"(?i)^PCT?\.?\s*#?\s*(\d+)$")
METHOD_BANNER_RE = re.compile(r"\b(BBM|EV|ED)\b")


def load_blocks(path):
    text = open(path).read()
    return [b for b in re.split(r"\n\s*\n", text) if b.strip()]


def parse_file(path):
    """Return {(office, district, cand): {method: {pct: int}}}."""
    out = {}
    warnings = []
    lines_all = []
    for bl in load_blocks(path):
        lines_all.extend(l for l in bl.splitlines() if l.strip())
    BANNER_RE = re.compile(r"Primary Election.*\b(BBM|EV|ED)\b")
    ncols = None
    pcts = []
    method = None
    title = None
    pending_name = None
    pending_ints = []
    for t in lines_all:
        t = t.strip()
        mb = BANNER_RE.search(t)
        if mb:
            method = {"BBM": "absentee", "EV": "early_voting",
                      "ED": "election_day"}[mb.group(1).upper()]
            title = pending_name = None
            pending_ints = []
            pcts, ncols = [], None
            continue
        pm = PCT_RE.match(t)
        if method and pm and (ncols is None or len(pcts) < ncols - 1):
            pcts.append(int(pm.group(1)))
            continue
        if method and t.upper() == "TOTAL" and ncols is None:
            ncols = len(pcts) + 1
            continue
        if not method or ncols is None:
            continue
        if SURVEY_RE.match(t):
            continue

        def flush(name, ints):
            if not name or not ints:
                return
            n = ncols
            if len(ints) == n:
                pcts_v, tot = ints[:-1], ints[-1]
            elif len(ints) == n + 1:
                if ints[-2] == 0 and sum(ints[:n - 1]) == ints[-1]:
                    pcts_v, tot = ints[:n - 1], ints[-1]
                elif sum(ints[:n]) == ints[-1]:
                    pcts_v, tot = ints[:n], ints[-1]
                else:
                    warn(f"row {name!r}: {len(ints)} counts for {n} cols: {ints}")
                    return
            elif len(ints) == n - 1:
                # one count cell lost by OCR: find a zero slot that reconciles
                tot = ints[-1]
                for pos in range(n):
                    pcts_v = ints[:n - 2] + [0] + ints[n - 2:]
                    if pos < len(ints) - 1 and pcts_v[-1] == tot and \
                            sum(pcts_v[:-1]) == tot:
                        flush2(name, pcts_v)
                        return
                    pcts_v = ints[:pos] + [0] + ints[pos:]
                    if sum(pcts_v[:-1]) == ints[-1]:
                        flush2(name, pcts_v)
                        return
                warn(f"row {name!r}: {len(ints)} counts for {n} cols: {ints}")
                return
            else:
                warn(f"row {name!r}: {len(ints)} counts for {n} cols: {ints}")
                return
            norm = normalize_office(title or "") or (seg_title(title or ""), "")
            office, district = norm
            out.setdefault((office, district, clean_candidate(name)), {}).\
                setdefault(method, {}).\
                update({p: v for p, v in zip(pcts, pcts_v)})

        def flush2(name, pcts_v):
            norm = normalize_office(title or "") or (seg_title(title or ""), "")
            office, district = norm
            out.setdefault((office, district, clean_candidate(name)), {}).\
                setdefault(method, {}).\
                update({p: v for p, v in zip(pcts, pcts_v)})

        def warn(msg):
            warnings.append(msg)

        ints = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", t)]
        mrow = re.match(r"^(.*?)[\s]+((?:\d[\d,]*[\s]*)+)$", t)
        if mrow:
            name = seg_title(mrow.group(1))
            vals = [int(x.replace(",", "")) for x in
                    re.findall(r"\d[\d,]*", mrow.group(2))]
            if len(vals) == 1 and not is_count_row(vals, ncols) and \
                    not pending_name:
                # digit-bearing race title ('United States Rep. Dis. 19')
                title = t
                continue
            if pending_name is not None:
                pending_name2 = name
                pending_name = None
                flush(pending_name2, pending_ints + vals)
                continue
            flush(name, vals)
            continue
        if ints and pending_name is not None:
            pending_ints.extend(ints)
            if len(pending_ints) >= ncols - 1:
                flush(pending_name, pending_ints)
                pending_name, pending_ints = None, []
            continue
        if ints:
            pending_ints.extend(ints)   # counts arrived before their label?
            continue
        # non-numeric line: race title, or label of a split row
        if TITLE_RE.search(t) or re.match(r"^Yes\b|^No\b", t, re.I) is None and \
                len(t) < 60:
            pass
        title = t if TITLE_RE.search(t) else title
        if not TITLE_RE.search(t):
            if pending_name is None:
                pending_name = seg_title(t)
            else:
                warn(f"double label: {t!r} after {pending_name!r}")
    return out, warnings


def merge_name_variants(data):
    """The same candidate's name drifts between view pages (Carlyte/Carlyle,
    Rodriquez/Rodriguez); merge keys within one race when names are near
    matches and their method sets don't collide."""
    import difflib
    groups = {}
    for (office, district, cand), bymethod in data.items():
        groups.setdefault((office, district), []).append(
            (cand, bymethod))
    merged = 0
    for (office, district), entries in groups.items():
        if len(entries) < 2:
            continue
        combined = []   # list of [cand, bymethod]
        for cand, bymethod in entries:
            ck = re.sub(r"[^A-Za-z]", "", cand).lower()
            target = None
            for other in combined:
                ok = re.sub(r"[^A-Za-z]", "", other[0]).lower()
                if difflib.SequenceMatcher(None, ck, ok).ratio() >= 0.8:
                    clash = any(m in other[1] for m in bymethod)
                    if clash:
                        continue
                    target = other
                    break
            if target is None:
                combined.append([cand, dict(bymethod)])
            else:
                for meth, vals in bymethod.items():
                    tgt = target[1].setdefault(meth, {})
                    for p, v in vals.items():
                        tgt[p] = max(tgt.get(p, 0), v)
                merged += 1
        for cand, bymethod in entries:
            data.pop((office, district, cand), None)
        for cand, bymethod in combined:
            data[(office, district, cand)] = bymethod
    return merged


def seg_title(t):
    return re.sub(r"\s+", " ", t or "").strip(" ,")


def is_count_row(vals, ncols):
    return len(vals) == ncols or len(vals) == ncols + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--county", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("sources", nargs="+")
    args = ap.parse_args()
    records = []
    all_warnings = []
    for path in args.sources:
        _, warnings = parse_file(path)
        all_warnings.extend(f"{os.path.basename(path)}: {w}" for w in warnings)

    # data: {(office, district, cand): {method: {pct: int}}}
    parties = {}
    for path in args.sources:
        base = os.path.basename(path).lower()
        file_party = "REP" if "_rep" in base else "DEM"
        data, _ = parse_file(path)
        merge_name_variants(data)
        for (office, district, cand), bymethod in data.items():
            pcts = sorted({p for m in bymethod.values() for p in m})
            # canonical method set: each ballot's total = sum of its views
            for p in pcts:
                vals = {m: bymethod.get(m, {}).get(p, 0) for m in
                        ("absentee", "early_voting", "election_day")}
                votes = sum(vals.values())
                records.append({
                    "precinct": precinct_name(str(p)),
                    "office": office,
                    "district": district,
                    "party": file_party,
                    "candidate": cand,
                    "votes": str(votes),
                    "absentee": str(vals["absentee"]),
                    "early_voting": str(vals["early_voting"]),
                    "election_day": str(vals["election_day"]),
                })
    parties = None
    write_county_csv(args.out, args.county, records, FIELDNAMES)
    print(f"{args.county}: wrote {len(records)} rows -> {args.out} "
          f"(warn {len(all_warnings)})")
    for w in all_warnings[:12]:
        print("  WARN", w)


if __name__ == "__main__":
    main()
