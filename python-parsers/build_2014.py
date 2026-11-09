#!/usr/bin/env python3
"""Batch driver for the 2014 primary precinct project.

Reads 2014/primary_2014_inventory.json, processes counties by format family
(currently "asc"), writes 2014/counties/20140304__tx__primary__<county>__precinct.csv,
then verifies each against the county baseline (verify_2014). Emits
2014/20140304__verification_report.json and prints a summary.

Usage:
  uv run python3 python-parsers/build_2014.py asc            # all asc counties
  uv run python3 python-parsers/build_2014.py asc --only angelina,bexar
  uv run python3 python-parsers/build_2014.py asc --continue # skip already-written
"""
import argparse
import csv
import importlib
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
SRC = os.path.expanduser("~/code/openelections-sources-tx/2014/primary")
INV = os.path.join(ROOT, "2014", "primary_2014_inventory.json")
OUTDIR = os.path.join(ROOT, "2014", "counties")

sys.path.insert(0, HERE)


def slug_from_sources(paths):
    return None  # unused


def county_title(county):
    return county.replace("_", " ").title()


def out_path(county):
    return os.path.join(OUTDIR, f"20140304__tx__primary__{county}__precinct.csv")


def done_counties_from_files():
    done = set()
    if not os.path.isdir(OUTDIR):
        return done
    for fn in os.listdir(OUTDIR):
        if fn.startswith("20140304") and fn.endswith("__precinct.csv"):
            c = fn.replace("20140304__tx__primary__", "").replace("__precinct.csv", "")
            if "__" not in c:
                done.add(c)
    return done


EXCEL_COUNTY_NAMES = {}


def county_names():
    import csv
    names = {}
    for county, title in EXCEL_COUNTY_NAMES.items():
        names[county] = title
    return names


PARTY_SLUG = {"DEM": "democratic", "REP": "republican"}


def out_path(county, party=None):
    if party in PARTY_SLUG:
        return os.path.join(OUTDIR,
                            f"20140304__tx__primary__{PARTY_SLUG[party]}__{county}__precinct.csv")
    return os.path.join(OUTDIR, f"20140304__tx__primary__{county}__precinct.csv")


def sources_for_county(county, exts=("xls", "xlsx", "xlsm")):
    srcs = []
    parties = set()
    for e in inv_entries:
        if e.get("skip") or e["county"] != county:
            continue
        fpath = os.path.join(SRC, e["file"])
        if not fpath.lower().endswith(tuple("." + x for x in exts)):
            continue
        srcs.append(fpath)
        if e.get("party"):
            parties.add(e["party"])
        else:
            parties.add("UNK")
    return srcs, parties


def run_excel(counties):
    sys.path.insert(0, SRC)
    import parse_2014_excel as xl
    import repair_2014 as rp
    from verify_2014 import load_baseline, verify

    cand, totals, corrupt = load_baseline()
    rmap = rp.build_map()
    report = {}
    for county in counties:
        srcs, parties = sources_for_county(county)
        party = next(iter(parties)) if len(parties) == 1 and "UNK" not in parties else None
        title = county_title(county)
        op = out_path(county, party)
        if os.path.exists(op) and os.path.getsize(op) > 200:
            print(f"-- {county}: output exists, skipping")
            continue
        if not srcs:
            print(f"-- {county}: no excel sources")
            continue
        print(f"== {county}: {len(srcs)} sources")
        try:
            n = xl.run_county(title, op, srcs)
            if not n:
                import parse_2014_wide as w
                n = w.run_county(title, op, srcs)
            if not n:
                report[county] = {"error": f"parse produced no rows (sources: {[os.path.basename(p) for p in srcs]})"}
                print("   !! nothing parsed")
                continue
        except Exception as ex:
            report[county] = {"error": f"parse failed: {ex}"}
            print(f"   !! parse error: {ex}")
            continue
        # if the deduped sources turned out to cover a single party only,
        # move the output to the party-prefixed conventional name
        with open(op) as fh:
            rows = list(csv.DictReader(fh))
        pset = {r.get("party") or "" for r in rows}
        if len(pset) == 1:
            only = next(iter(pset))
            if only in ("DEM", "REP"):
                newop = out_path(county, only)
                os.replace(op, newop)
                print(f"   single-party data ({only}); renamed to {os.path.basename(newop)}")
                op = newop
        try:
            rp.repair_file(op, rmap)
            res = verify(op, cand, totals, corrupt)
        except Exception as ex:
            report[county] = {"error": f"verify failed: {ex}"}
            print(f"   !! verify error: {ex}")
            continue
        res["sources"] = [os.path.basename(p) for p in srcs]
        report[county] = res
        print(f"   rows={res.get('rows')} missing={len(res.get('offices_missing', []))} "
              f"total_mm={len(res.get('total_mismatch', []))} cand_mm={len(res.get('candidate_mismatch', []))}")
    return report


def run_asc(counties):
    sys.path.insert(0, SRC)
    import parse_2014_asc as asc
    from verify_2014 import load_baseline, verify, load_precinct

    cand, totals, corrupt = load_baseline()
    report = {}
    full_names = {"bastrop": "Bastrop", "bexar": "Bexar", "chambers": "Chambers",
                  "dallam": "Dallam", "dallas": "Dallas", "fayette": "Fayette",
                  "hemphill": "Hemphill", "hidalgo": "Hidalgo", "jefferson": "Jefferson",
                  "lamar": "Lamar", "lamb": "Lamb", "lavaca": "Lavaca",
                  "midland": "Midland", "montague": "Montague", "moore": "Moore",
                  "palo_pinto": "Palo Pinto", "rusk": "Rusk", "san_jacinto": "San Jacinto",
                  "shelby": "Shelby", "stonewall": "Stonewall", "swisher": "Swisher",
                  "van_zandt": "Van Zandt", "washington": "Washington",
                  "williamson": "Williamson", "yoakum": "Yoakum",
                  "angelina": "Angelina"}
    for county in counties:
        title = full_names.get(county, county_title(county))
        op = out_path(county)
        if os.path.exists(op):
            print(f"-- {county}: output exists, skipping (use --force to rebuild)")
            continue
        srcs = []
        # map party -> list of files
        by_party = defaultdict(list)
        all_files = set()
        for e in inv_entries:
            if e.get("skip"):
                continue
            if e["county"] != county:
                continue
            fpath = os.path.join(SRC, e["file"])
            ext = fpath.lower().rsplit(".", 1)[-1]
            if ext not in ("asc", "001", "lst", "wrk"):
                continue
            if "canvass" in e["file"].lower() and False:
                continue
            all_files.add(fpath)
            if e["party"]:
                by_party[e["party"]].append(fpath)
            else:
                by_party["UNK"].append(fpath)
        if not all_files:
            print(f"-- {county}: no asc sources")
            continue
        # order: DEM files then REP then UNK (dedupe identical handled inside)
        ordered = [p for party in ("DEM", "REP", "UNK") for p in by_party.get(party, [])]
        print(f"== {county}: {len(ordered)} sources")
        try:
            asc.run_county(title, op, ordered)
        except Exception as ex:
            report[county] = {"error": f"parse failed: {ex}"}
            print(f"   !! parse error: {ex}")
            continue
        try:
            res = verify(op, cand, totals, corrupt)
        except Exception as ex:
            report[county] = {"error": f"verify failed: {ex}"}
            print(f"   !! verify error: {ex}")
            continue
        res["sources"] = [os.path.basename(p) for p in ordered]
        report[county] = res
        n_bad = len(res.get("total_mismatch", [])) + len(res.get("candidate_mismatch", []))
        print(f"   rows={res.get('rows')} missing_offices={len(res.get('offices_missing', []))} "
              f"total_mm={len(res.get('total_mismatch', []))} cand_mm={len(res.get('candidate_mismatch', []))}")
    return report


def load_inventory_entries():
    global inv_entries
    with open(INV) as fh:
        inv_entries = json.load(fh)["entries"]
    return inv_entries


def main():
    global inv_entries
    ap = argparse.ArgumentParser()
    ap.add_argument("group", choices=["asc", "excel"])
    ap.add_argument("--only")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    inv_entries = load_inventory_entries()

    counties = set()
    for e in inv_entries:
        if e.get("skip"):
            continue
        fpath = os.path.join(SRC, e["file"])
        ext = fpath.lower().rsplit(".", 1)[-1]
        if args.group == "asc" and ext in ("asc", "001", "lst", "wrk"):
            counties.add(e["county"])
        elif args.group == "excel" and ext in ("xls", "xlsx", "xlsm", "xlsb"):
            counties.add(e["county"])
    if args.only:
        want = {c.strip() for c in args.only.split(",")}
        counties &= want

    if args.group == "asc":
        report = run_asc(sorted(counties))
    elif args.group == "excel":
        report = run_excel(sorted(counties))
        rep_path = os.path.join(ROOT, "2014", "20140304__excel_report.json")
        with open(rep_path, "w") as fh:
            json.dump(report, fh, indent=1, default=str)
        print(f"report -> {rep_path}")
        ok = [c for c, r in sorted(report.items()) if not r.get("error")
              and not r.get("total_mismatch") and not r.get("candidate_mismatch")]
        print(f"fully verified: {len(ok)}: {ok}")
        problems = {c: r.get("error", f"{len(r.get('offices_missing', []))} missing, "
                              f"{len(r.get('candidate_mismatch', []))} cand_mm")
                    for c, r in sorted(report.items())
                    if r.get("error") or r.get("total_mismatch") or r.get("candidate_mismatch")}
        for c, why in problems.items():
            print(f"  {c}: {why}")
        return

    rep_path = os.path.join(ROOT, "2014", "20140304__asc_report.json")
    existing = {}
    if os.path.exists(rep_path):
        with open(rep_path) as fh:
            existing = json.load(fh)
    existing.update(report)
    with open(rep_path, "w") as fh:
        json.dump(existing, fh, indent=1, default=str)
    ok = [c for c, r in existing.items() if not r.get("error")
          and not r.get("total_mismatch") and not r.get("candidate_mismatch")]
    print(f"\nreport -> {rep_path}: {len(existing)} counties, "
          f"{len(ok)} fully verified: {ok}")


if __name__ == "__main__":
    main()
