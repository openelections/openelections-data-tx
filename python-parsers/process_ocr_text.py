#!/usr/bin/env python3
"""Process one OCR'd county report text: pick the parser whose signature fits,
parse, repair against the SOS baseline, verify, and copy to 2026/counties.

Usage: uv run python3 python-parsers/process_ocr_text.py <ocr.txt ...> [--force]
"""

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)


def sign(text):
    """Return which report family the text looks like."""
    for re_, name in (
        (r"Election Summary Report", "summary-only"),
        (r"Cumulative Results Report", "cumulative"),
        (r"Precinct Results Report.*Official Results", "hart"),
        (r"(?:Democratic|Republican)[- ]?Party[- ]?Primary Election", "transposed"),
        (r"\bbox x box\b", "box"),
        (r"Canvass Results Report", "box"),
        (r"Custom Table Report", "box"),
        (r"Summary Results Report|Election Summary Report", "dominion"),
    ):
        if re.search(re_, text, re.I):
            return name
    return "unknown"


def slug(county):
    return county.lower().replace(" ", "_")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--party", default="NON")
    args = ap.parse_args()
    by_county = {}
    for f in args.files:
        base = os.path.basename(f)
        txt = open(f, errors="replace").read()
        # county name from the file name or text
        county = None
        m = re.search(r"([A-Z][A-Z _]+?)(?:_COUNTY)?[-_ ]?2026", base)
        if m:
            county = m.group(1).replace("_", " ").strip().title()
        else:
            m = re.search(r"([A-Za-z ]+?)\s+County", txt[:4000])
            county = m.group(1).strip().title() if m else None
        if not county:
            print("!! no county:", base)
            continue
        fam = sign(txt)
        by_county.setdefault(county, []).append((f, fam))
        print(f"{base[:58]:58} -> {county} [{fam}]")

    for county, items in sorted(by_county.items()):
        cslug = slug(county)
        out = f"2026/counties/20260303__tx__primary__{cslug}__precinct.csv"
        outs = []
        if {"cumulative", "summary-only"} & {fam for _, fam in items}:
            print(f"== {county}: cumulative-only source; skipping")
            continue
        for f, fam in items:
            parser = {
                "hart": "python-parsers/parse_2026_hart.py",
                "dominion": "python-parsers/parse_2026_dominion.py",
                "transposed": "python-parsers/parse_2026_transposed.py",
                "box": "python-parsers/parse_2026_box_table.py",
                "unknown": None,
            }[fam]
            if parser is None:
                print(f"== {county}: unknown format; skipping {os.path.basename(f)}")
                continue
            tmp = f"/tmp/tx2026/out/{cslug}_{os.path.basename(f)}.parsed.csv"
            cmd = ["uv", "run", "python3", parser, "-c", county, "-o", tmp]
            if os.path.basename(parser).endswith("transposed.py"):
                cmd += ["--party", args.party]
            else:
                cmd += ["--party", args.party]
            cmd.append(f)
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 60:
                print(f"   !! parse failed for {os.path.basename(f)}: {r.stdout[-120:]}{r.stderr[-200:]}")
                continue
            if fam in ("hart", "dominion"):
                # OCR'd per-method headers reconstruct unreliably; keep votes only
                import csv as _csv
                with open(tmp) as tf:
                    _rows = list(_csv.DictReader(tf))
                    _fields = list(_rows[0].keys())
                for _r in _rows:
                    for _c in ("absentee", "early_voting", "election_day",
                               "provisional", "limited"):
                        _r[_c] = ""
                with open(tmp, "w", newline="") as tf:
                    w = _csv.DictWriter(tf, fieldnames=_fields, lineterminator="\n")
                    w.writeheader(); w.writerows(_rows)
            outs.append(tmp)
        if not outs:
            print(f"== {county}: no parseable source")
            continue
        with open(out, "w") as fh:
            first = True
            for t in sorted(outs):
                with open(t) as tf:
                    lines = tf.read().splitlines()
                if first:
                    fh.write("\n".join(lines) + "\n")
                    first = False
                else:
                    fh.write("\n".join(lines[1:]) + "\n")
        subprocess.run(["uv", "run", "python3", "python-parsers/repair_2026.py", out],
                       capture_output=True, text=True)
        v = subprocess.run(["uv", "run", "python3", "python-parsers/verify_2026.py", out,
                            "--json-report", "/tmp/tx2026/last.json", "--quiet"],
                           capture_output=True, text=True)
        import json
        try:
            d = json.load(open("/tmp/tx2026/last.json"))
            mm = sum(1 for x in d["diffs"] if x[7] == "mismatch")
            cov = sum(1 for x in d["diffs"] if x[7] == "no precinct coverage")
            nb = sum(1 for x in d["diffs"] if x[7] == "not in baseline")
            rows = list(d["files"].values())[0]
            print(f"== {county}: OUT {len(rows['precincts'])} precincts, "
                  f"{rows['rows']} rows; mismatch={mm} nocov={cov} extra={nb}")
        except Exception as e:
            print(f"== {county}: verification failed: {v.stdout[-300:]}")


if __name__ == "__main__":
    main()