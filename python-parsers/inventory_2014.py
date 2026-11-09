#!/usr/bin/env python3
"""Inventory of March 4, 2014 primary source files vs already-converted
precinct CSVs.

Classifies each source in ~/code/openelections-sources-tx/2014/primary into
(county, party, format) and emits 2014/primary_2014_inventory.json plus a
summary of remaining work by format.

Run:  uv run python3 python-parsers/inventory_2014.py
"""
import json
import os
import re
import sys

SRC = os.path.expanduser("~/code/openelections-sources-tx/2014/primary")
OUT = os.path.join(os.path.dirname(__file__), "..", "2014", "primary_2014_inventory.json")
DONE_DIR = os.path.join(os.path.dirname(__file__), "..", "2014", "counties")

def norm_county(s):
    s = s.replace("_COUNTY", "").replace("_", " ").strip().lower()
    return s.replace(" ", "_")

RUNOFF_RE = re.compile(r"run\s*off|runoff", re.I)

# filename prefixes that fall outside the standard _COUNTY-2014_... pattern
SPECIAL = {
    "20140311_tx_jointprimary_bexar_precinct.pdf": None,  # separate March 11 special
    "bailey_tx_2014_primary.pdf": ("bailey", None),
    "coke_tx_2014_primary.pdf": ("coke", None),
    "hockley_tx_2014_primary.pdf": ("hockley", None),
    "gillespie_tx_2014_dem_march_primary_election_results_early_voting.pdf": ("gillespie", "DEM"),
    "gillespie_tx_2014_dem_march_primary_election_day_results.pdf": ("gillespie", "DEM"),
    "gillespie_tx_2014_rep_march_primary_election_day_results.pdf": ("gillespie", "REP"),
    "gillespie_tx_2014_rep_march_primary_election_results_early_voting.pdf": ("gillespie", "REP"),
    "grimes_tx_2014_primary_democraticpctreports.pdf": ("grimes", "DEM"),
    "grimes_tx_2014_primary_republicanprecinct.pdf": ("grimes", "REP"),
    "harrisson": None,
}
COMANCHE_RE = re.compile(r"^Comanche TX (March 4|May 27), 2014 (DEM|REP) Primary( Run Off)? (ED|EV)\.pdf$", re.I)
KERR_RE = re.compile(r"^Kerr TX 2014 primary (demo|rep)-final-precinct\.pdf$", re.I)
KIMBLE_RE = re.compile(r"^Kimble TX REPUBLICAN PRIMARY MAR 4, 2014\.xlsx$", re.I)
OLDHAM_RE = re.compile(r"^Oldham TX (\d\d-\d\d-\d\d) (REPUBLICAN PRIMARY|.*RUNOFF.*)(.*)$", re.I)
HARRISON_SPECIAL_RE = re.compile(r"^HARRISON_COUNTY-2014_Democratic_Party_Primary_Election_3414_342014-", re.I)
LIBERTY_RE = re.compile(r"^LIBERTY_COUNTY-2014_PRIMARY_ELECTION_3414_342014-", re.I)
MARION_X_RE = re.compile(r"^MARION_COUNTY-2014_(Democratic|Republican)_Party_Primary.*342014[_0-9]*-", re.I)
BELL_RE = re.compile(r"^BELL_COUNTY-2014_Bell_County_Primary_Election__342014-", re.I)

STANDARD_RE = re.compile(
    r"^([A-Z_]+)_COUNTY-2014_(Democratic|Republican)_Party_Primary.*-\s*(.+)$", re.I)

def classify(fname):
    """Return (county, party, ext, variant, skip_reason) or None."""
    f = fname
    low = f.lower()
    ext = os.path.splitext(low)[1].lstrip(".")
    if RUNOFF_RE.search(f):
        return None, None, ext, None, "runoff"
    m = COMANCHE_RE.match(f)
    if m:
        if "May 27" in f or "Run Off" in f:
            return None, None, ext, None, "runoff"
        return "comanche", m.group(2).upper(), ext, "ed" if m.group(4) == "ED" else "ev", None
    if OLDHAM_RE.match(f):
        if "052714" in f:
            return None, None, ext, None, "runoff"
        return "oldham", "REP", ext, None, None
    if KERR_RE.match(f):
        party = "DEM" if m and False else ("DEM" if f.lower().startswith("kerr tx 2014 primary demo") else "REP")
        return "kerr", party, ext, None, None
    if KIMBLE_RE.match(f):
        return "kimble", "REP", ext, None, None
    if low in SPECIAL:
        spec = SPECIAL[low]
        if spec is None:
            return None, None, ext, None, "out of scope"
        return spec[0], spec[1], ext, "early" if "early" in low else None, None
    if low.startswith("gillespie tx"):
        party = "DEM" if "dem" in low else "REP"
        variant = "ev" if "early" in low else "ed"
        return "gillespie", party, ext, variant, None
    if low.startswith("grimes tx 2014 primary"):
        party = "DEM" if "democratic" in low else "REP"
        return "grimes", party, ext, None, None
    if BELL_RE.match(f):
        return "bell", None, ext, None, None
    if HARRISON_SPECIAL_RE.match(f):
        party = "DEM" if "dem" in low else "REP"
        return "harrison", party, ext, None, None
    if LIBERTY_RE.match(f):
        return "liberty", None, ext, None, None
    if MARION_X_RE.match(f):
        party = "DEM" if "democratic" in low else "REP"
        variant = "dup" if "3420-342014_3420" in low or "3 4 13" in low else None
        return "marion", party, ext, variant, None
    m = STANDARD_RE.match(f)
    if m:
        county = norm_county(m.group(1))
        party = "DEM" if m.group(2).lower().startswith("dem") else "REP"
        return county, party, ext, None, None
    return None, None, ext, None, "unrecognized"


def main():
    entries = []
    for fname in sorted(os.listdir(SRC)):
        county, party, ext, variant, skip = classify(fname)
        if skip:
            entries.append({"file": fname, "skip": skip})
            continue
        ext = ext or "noext"
        if ext in ("asc", "001", "lst", "wrk"):
            fmt = "asc"
        elif ext in ("xls", "xlsx", "chm"):
            fmt = "excel"
        elif ext in ("csv", "txt", "htm"):
            fmt = "text"
        elif ext == "pdf":
            fmt = "pdf"
        elif ext == "docx":
            fmt = "docx"
        elif ext in ("doc", "exe", "zip", "shs", "wrk", "lst"):
            fmt = ext
        else:
            fmt = "noext"
        entries.append({
            "file": fname, "county": county, "party": party,
            "format": fmt, "variant": variant,
        })

    done = set()
    for fn in os.listdir(DONE_DIR):
        if fn.startswith("20140304") and "__precinct.csv" in fn:
            c = fn.replace("20140304__tx__primary__", "").replace("__precinct.csv", "")
            if "__" in c:  # e.g. republican__dallam -> party-suffixed partial
                party, county = c.split("__", 1)
                done.add(f"{county}:{party.upper()}")
            else:
                done.add(f"{c}:DEM")
                done.add(f"{c}:REP")

    counties = {}
    for e in entries:
        if e.get("skip"):
            continue
        key = e["county"]
        c = counties.setdefault(key, {"parties": {}})
        party = e["party"] or "UNK"
        c["parties"].setdefault(party, []).append(
            {k: e[k] for k in ("file", "format", "variant")})

    remaining = {}
    for county, info in sorted(counties.items()):
        info["done"] = {p: f"{county}:{p}" in done for p in ("DEM", "REP")}
        for p in ("DEM", "REP"):
            if p in info["parties"] and not info["done"][p]:
                fmts = sorted({f["format"] for f in info["parties"][p]})
                for fmt in fmts:
                    remaining.setdefault(fmt, set()).add(county)
        for p in ("UNK",):
            if p in info["parties"]:
                info["done"][p] = f"{county}:{'DEM' if 'dem' in county else 'UNK'}" in done

    fmt_summary = {fmt: sorted(v) for fmt, v in sorted(remaining.items())}
    with open(OUT, "w") as f:
        json.dump({"entries": entries, "counties": counties}, f, indent=1)
    print(f"total sources: {len(entries)}")
    print(f"skipped: {sum(1 for e in entries if e.get('skip'))} (runoff/out-of-scope)")
    print(f"counties with sources: {len(counties)}")
    full = [c for c, i in counties.items() if all(i["done"].get(p, False) for p in ("DEM", "REP") if p in i["parties"])]
    print(f"fully converted: {len(full)}")
    print("\nremaining work by format:")
    for fmt, cs in fmt_summary.items():
        print(f"  {fmt:8s} {len(cs):3d} counties: {', '.join(cs)}")


if __name__ == "__main__":
    main()
