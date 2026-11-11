#!/usr/bin/env python3
"""Inventory of the May 29, 2012 primary source files vs already-converted
precinct CSVs.

Classifies each source in ~/code/openelections-sources-tx/2012/primary into
(county, party, format) and emits 2012/primary_2012_inventory.json plus a
summary of remaining work by format.

Run:  uv run python3 python-parsers/inventory_2012.py
"""
import json
import os
import re

SRC = os.path.expanduser("~/code/openelections-sources-tx/2012/primary")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "2012", "primary_2012_inventory.json")
DONE_DIR = os.path.join(HERE, os.pardir, "2012", "counties")

RUNOFF_RE = re.compile(r"run\s*off|runoff", re.I)

SPECIAL = {
    "bandera_county-2011_constitutional_amendment_election_1182011-detailvotetotals11.08.xls":
        (None, None, None, "2011 amendment election"),
    "coke tx 2012 primary.pdf": ("coke", None, None, None),
    "comanche tx may 29, 2012 dem primary election ed.pdf": ("comanche", "DEM", "ed", None),
    "comanche tx may 29, 2012 dem primary election ev.pdf": ("comanche", "DEM", "ev", None),
    "comanche tx may 29, 2012 rep primary election ed.pdf": ("comanche", "REP", "ed", None),
    "comanche tx may 29, 2012 rep primary election ev.pdf": ("comanche", "REP", "ev", None),
    "cochran county rep primary(early).xls": ("cochran", "REP", "early", None),
    "ellis tx 120529 primary final election results": ("ellis", None, None, None),
    "fisher tx 2012 primary demo.pdf": ("fisher", "DEM", None, None),
    "fisher tx 2012 primary repub.pdf": ("fisher", "REP", None, None),
}

COUNTY_RE = re.compile(r"^(?P<county>[A-Z_]+?)_COUNTY-(?P<rest>.+)$", re.I)

GROUP_EXTS = {
    "asc": ("asc", "001", "lst", "wrk", "cvs", "alg", "al2", "v5"),
    "excel": ("xls", "xlsx", "xlsm", "xlsb"),
    "text": ("csv", "txt", "tsv", "htm"),
    "pdf": ("pdf",),
    "docx": ("docx",),
    "doc": ("doc",),
    "zip": ("zip",),
}


def classify(fname):
    """Return (county, party, variant, skip_reason)."""
    f = fname
    low = f.lower()
    if RUNOFF_RE.search(f):
        return None, None, None, "runoff"
    if low in SPECIAL:
        county, party, variant, skip = SPECIAL[low]
        return county, party, variant, skip
    m = COUNTY_RE.match(f)
    if not m:
        return None, None, None, "unrecognized"
    county = m.group("county").replace("_", " ").strip().lower().replace(" ", "_")
    rest = m.group("rest").lower()
    party = None
    if re.search(r"democrati|_dem_|[^a-z]dem[^a-z]", rest):
        party = "DEM"
    elif re.search(r"republican|[^a-z]rep[^a-z]|rep primary", rest):
        party = "REP"
    return county, party, None, None


def file_format(fname):
    low = fname.lower()
    ext = os.path.splitext(low)[1].lstrip(".")
    full = os.path.join(SRC, fname)
    if not ext:
        if os.path.isdir(full):
            return "unknown"
        with open(full, "rb") as fh:
            head = fh.read(16)
        if head[:2] == b"PK":
            return "zip"
        if head[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            return "excel"
        return "unknown"
    for g, exts in GROUP_EXTS.items():
        if ext in exts:
            return g
    return "unknown"


def main():
    rows = []
    for fname in sorted(os.listdir(SRC)):
        county, party, variant, skip = classify(fname)
        if skip:
            rows.append({"file": fname, "skip": skip})
            continue
        rows.append({"file": fname, "county": county, "party": party,
                     "format": file_format(fname), "variant": variant})

    counties = {}
    for e in rows:
        if e.get("skip"):
            continue
        c = counties.setdefault(e["county"], {"parties": {}})
        c["parties"].setdefault(e["party"] or "UNK", []).append(
            {k: e[k] for k in ("file", "format", "variant")})

    done = set()
    for fn in os.listdir(DONE_DIR) if os.path.isdir(DONE_DIR) else []:
        if fn.startswith("20120529") and "__precinct" in fn:
            c = fn.replace("20120529__tx__primary__", "").replace("__precinct.csv", "")
            if "__" in c:
                party, county = c.split("__", 1)
                done.add(f"{county}:{party.upper()}")
            else:
                done.update({f"{c}:DEM", f"{c}:REP", f"{c}:UNK"})

    remaining = {}
    county_status = {}
    for county, info in sorted(counties.items()):
        ps = {}
        for p, files in info["parties"].items():
            need = [(f["file"], f["format"]) for f in files]
            ps[p] = need
        info["done"] = {p: f"{county}:{p}" in done for p in ("DEM", "REP", "UNK")}
        todo = {}
        for p, files in ps.items():
            if info["done"][p]:
                continue
            for fn, fmt in files:
                todo.setdefault(fmt, []).append(fn)
        county_status[county] = info["parties"].keys()
        for fmt, files in todo.items():
            remaining.setdefault(fmt, set()).add(county)

    with open(OUT, "w") as fh:
        json.dump({"entries": rows, "counties": counties}, fh, indent=1)
    print(f"total sources: {len(rows)}")
    print(f"skipped: {sum(1 for e in rows if e.get('skip'))}")
    print(f"counties with sources: {len(counties)}")
    print("\nremaining work by format:")
    for fmt, cs in sorted(remaining.items()):
        print(f"  {fmt:8s} {len(cs):3d} counties: {', '.join(sorted(cs))}")
    unrec = [e["file"] for e in rows if e.get("skip") == "unrecognized"]
    if unrec:
        print("unrecognized:", unrec)


if __name__ == "__main__":
    main()
