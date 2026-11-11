#!/usr/bin/env python3
"""Batch driver for the May 29, 2012 primary precinct project.

Reads 2012/primary_2012_inventory.json, processes counties by format family
("asc", "excel", "text"), writes
2012/counties/20120529__tx__primary__<county>__precinct.csv
(with a party prefix when the county's sources cover a single party),
then verifies each against the county baseline (verify_2012). Merges results
into 2012/20120529__report.json.

Usage:
  uv run python3 python-parsers/build_2012.py asc [--only angelina,dallas] [--force]
  uv run python3 python-parsers/build_2012.py excel
  uv run python3 python-parsers/build_2012.py text
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
SRC = os.path.expanduser("~/code/openelections-sources-tx/2012/primary")
INV = os.path.join(ROOT, "2012", "primary_2012_inventory.json")
OUTDIR = os.path.join(ROOT, "2012", "counties")
REP_PATH = os.path.join(ROOT, "2012", "20120529__report.json")

sys.path.insert(0, HERE)

PARTY_SLUG = {"DEM": "democratic", "REP": "republican"}


def county_title(county):
    return county.replace("_", " ").title()


def out_path(county, party=None):
    if party in PARTY_SLUG:
        return os.path.join(OUTDIR,
                            f"20120529__tx__primary__{PARTY_SLUG[party]}__{county}__precinct.csv")
    return os.path.join(OUTDIR, f"20120529__tx__primary__{county}__precinct.csv")


def done_counties():
    """Map county -> set of party-slugs already written (incl. combined)."""
    done = defaultdict(set)
    if not os.path.isdir(OUTDIR):
        return done
    for fn in os.listdir(OUTDIR):
        if not fn.startswith("20120529") or "__precinct" not in fn:
            continue
        c = fn.replace("20120529__tx__primary__", "").replace("__precinct.csv", "")
        if "__" in c:
            party, county = c.split("__", 1)
            done[county].add(PARTY_SLUG.get(party.upper(), party.upper()))
        else:
            done[c].update({"DEM", "REP", "UNK"})
    return done


def sources_for(county, group, party=None):
    """Return dict party -> [file paths] for the requested format family."""
    by_party = defaultdict(list)
    for e in inv_entries:
        if e.get("skip") or e["county"] != county or e["format"] != group:
            continue
        fpath = os.path.join(SRC, e["file"])
        if os.path.isdir(fpath):
            continue
        by_party[e["party"] or "UNK"].append(fpath)
    return by_party


def parse_and_write(county, group, by_party, force=False):
    """Parse one county. Returns (out_file, single_party) or (None, reason)."""
    done = done_counties()
    parties = sorted(by_party)
    if parties == ["UNK"] or parties == [None]:
        single_party = None
    elif all(p in ("DEM", "REP") for p in parties):
        single_party = parties[0] if len(parties) == 1 else None
    else:
        single_party = None
    op = out_path(county, single_party)
    if not force and done.get(county):
        have = done[county]
        want_all = ("UNK" if single_party is None else single_party)
        if want_all in have or (single_party is None and {"DEM", "REP"} <= have):
            print(f"-- {county}: output exists, skipping")
            return None, "exists"
    if group == "asc":
        import parse_2012_asc as parser
        ordered = [p for party in ("DEM", "REP", "UNK") for p in by_party.get(party, [])]
        sources = ordered
        run = parser.run_county
    elif group == "excel":
        import parse_2012_excel as parser
        sources = [p for party in ("DEM", "REP", "UNK") for p in by_party.get(party, [])]
        run = parser.run_county
    elif group == "text":
        import parse_2012_text as parser
        sources = [p for party in ("DEM", "REP", "UNK") for p in by_party.get(party, [])]
        run = parser.run_county
    else:
        raise SystemExit(f"unknown group {group}")
    tmp_op = op + ".tmp"
    try:
        run(county_title(county), tmp_op, sources)
        if group == "excel" and (not os.path.exists(tmp_op)
                                 or os.path.getsize(tmp_op) < 200):
            import parse_2012_wide as wide
            run = wide.run_county
            run(county_title(county), tmp_op, sources)
    except Exception as ex:
        import traceback
        traceback.print_exc()
        return None, f"parse failed: {ex}"
    if not os.path.exists(tmp_op) or os.path.getsize(tmp_op) < 200:
        try:
            os.unlink(tmp_op)
        except OSError:
            pass
        return None, "no rows parsed"
    # merge/dedupe handled inside parsers; move tmp into place
    os.replace(tmp_op, op)
    return op, single_party


def finalize(county, op, single_party, res):
    """Set the party prefix on single-party output and return report entry."""
    if single_party is None:
        with open(op) as fh:
            rows = list(csv.DictReader(fh))
        pset = {(r.get("party") or "").strip() for r in rows}
        pset.discard("")
        if len(pset) == 1 and next(iter(pset)) in PARTY_SLUG:
            sp = next(iter(pset))
            newop = out_path(county, sp)
            os.replace(op, newop)
            op = newop
    res["file"] = os.path.basename(op)
    return res


def main():
    global inv_entries
    ap = argparse.ArgumentParser()
    ap.add_argument("group", choices=["asc", "excel", "text", "pdf", "doc", "docx", "zip", "unknown"])
    ap.add_argument("--only")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    with open(INV) as fh:
        inv_entries = json.load(fh)["entries"]

    counties = sorted({e["county"] for e in inv_entries
                       if not e.get("skip") and e.get("format") == args.group})
    if args.only:
        want = {c.strip() for c in args.only.split(",")}
        counties = [c for c in counties if c in want]

    from verify_2012 import load_baseline, verify
    cand, totals, corrupt = load_baseline()
    report = {}
    if os.path.exists(REP_PATH):
        with open(REP_PATH) as fh:
            report = json.load(fh)

    for county in counties:
        by_party = sources_for(county, args.group)
        if not by_party:
            continue
        print(f"== {county}: {sum(len(v) for v in by_party.values())} {args.group} sources "
              f"({', '.join(sorted(by_party))})")
        op, single_party = parse_and_write(county, args.group, by_party, args.force)
        if op is None:
            report[county] = {"format": args.group, "error": single_party}
            print(f"   -> {single_party}")
            continue
        try:
            res = verify(op, cand, totals, corrupt)
        except Exception as ex:
            import traceback
            traceback.print_exc()
            report[county] = {"format": args.group, "error": f"verify failed: {ex}"}
            continue
        res = finalize(county, op, single_party, res)
        res["format"] = args.group
        report[county] = res
        print(f"   -> {res['file']}: rows={res.get('rows')} "
              f"missing={len(res.get('offices_missing', []))} "
              f"total_mm={len(res.get('total_mismatch', []))} "
              f"total_diffs={len(res.get('total_row_diffs', []))} "
              f"cand_mm={len(res.get('candidate_mismatch', []))}")

    with open(REP_PATH, "w") as fh:
        json.dump(report, fh, indent=1, default=str)
    ok = [c for c, r in sorted(report.items())
          if r.get("format") == args.group and not r.get("error")
          and not r.get("total_mismatch") and not r.get("candidate_mismatch")]
    print(f"\nreport -> {REP_PATH}")
    print(f"{args.group}: {len(ok)} counties fully verified: {', '.join(ok)}")
    bad = {c: (r.get("error") or
               f"{len(r.get('offices_missing', []))} missing, "
               f"{len(r.get('total_mismatch', []))} total_mm, "
               f"{len(r.get('candidate_mismatch', []))} cand_mm")
           for c, r in sorted(report.items())
           if r.get("format") == args.group and (r.get("error") or r.get("total_mismatch")
                                                 or r.get("candidate_mismatch"))}
    for c, why in bad.items():
        print(f"  {c}: {why}")


if __name__ == "__main__":
    main()
