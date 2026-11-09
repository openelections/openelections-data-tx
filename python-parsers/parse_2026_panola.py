#!/usr/bin/env python3
"""Parse the Panola County 2026 primary canvass reports (PaddleOCR API jsonl):
candidate/proposition blocks of three method rows (EARLY / ABSENTEE /
PRECINCT), each with one count per precinct column (19 columns, one often
blank) plus a bold total, followed by a faint per-precinct subtotal row.

Document stream (tables + divs interleaved in reading order per page):
  [faint subtotal row: all ints, no label]        -> skipped
  'Proposition 11' style div                      -> race title
  'Tom Baker' boxed single-cell row               -> current label
  'EARLY  <19 ints>  <total>' / [label]+EARLY...  -> method row for label
  'ABSENTEE ...'  ('PRECINCT' = election day)
One block spans page breaks: method rows at a page top attach to the previous
title/label.

Usage:
  uv run python3 python-parsers/parse_2026_panola.py -c COUNTY -o OUT.csv
        canvass-dem.api.jsonl canvass-rep.api.jsonl
"""

import argparse
import html
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers_2026 import normalize_office, clean_candidate, precinct_name, write_county_csv  # noqa: E402

FIELDNAMES = ["county", "precinct", "office", "district", "party", "candidate",
              "votes", "absentee", "early_voting", "election_day", "provisional", "limited"]

TD_RE = re.compile(r"<td([^>]*)>(.*?)</td>", re.S)
TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
TABLE_RE = re.compile(r"<table[^>]*>(.*?)</table>", re.S)
DIV_RE = re.compile(r"<div[^>]*>(.*?)</div>", re.S)
METHODS = {"EARLY": "early_voting", "ABSENTEE": "absentee",
           "PRECINCT": "election_day", "ELECTION": "election_day"}
INT_RE = re.compile(r"^[\d,]+$")


def unesc(s):
    return html.unescape(s).replace("\\n", "\n")


def clean(s):
    return re.sub(r"\s+", " ", unesc(re.sub(r"<img[^>]*>", "", s))).strip()


def rows_of(page_md):
    tables = list(TABLE_RE.finditer(page_md))
    divs = list(DIV_RE.finditer(page_md))
    events = sorted(
        [(m.start(), "table", i) for i, m in enumerate(tables)] +
        [(m.start(), "div", i) for i, m in enumerate(divs)])
    for _, kind, i in events:
        if kind == "div":
            d = divs[i].group(1)
            m_src = re.search(r'src="([^"]+)"', d)
            if m_src:
                yield ("img", m_src.group(1))
            for part in unesc(re.sub(r"<img[^>]+>", "", d)).split("\n"):
                part = clean(part)
                if part:
                    yield ("div", part)
            continue
        for tr in TR_RE.finditer(tables[i].group(1)):
            cells = [clean(m.group(2)) for m in TD_RE.finditer(tr.group(1))]
            yield ("row", [c for c in cells])


IMG_CACHE = {}
OCR_LOCAL = None


def get_ocr_local():
    global OCR_LOCAL
    if OCR_LOCAL is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ocr_local", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "ocr_2026.py"))
        OCR_LOCAL = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(OCR_LOCAL)
        OCR_LOCAL._init_worker("en")
    return OCR_LOCAL


def handle_img(state, rel, images, data, warnings):
    """A boxed race block rendered as an image: download, OCR locally, and
    attach any method rows to the current (race, label)."""
    url = images.get(rel, rel)
    name = os.path.basename(rel)
    path = IMG_CACHE.get(name)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "ocr_txt", "imgs", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            subprocess.run(["curl", "-sS", "--max-time", "120", url, "-o", path],
                           capture_output=True)
        IMG_CACHE[name] = path
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        warnings.append(f"img {name}: download failed")
        return
    try:
        lines = get_ocr_local()._ocr_png(path)
    except Exception as e:  # noqa: BLE001
        warnings.append(f"img {name}: OCR failed: {e!r}")
        return
    for line in (lines or []):
        t = re.sub(r"\s+", " ", line).strip()
        m = re.match(r"^(.*?)[\s]+(EARLY|ABSENTEE|PRECINCT)\b(.*)$", t, re.I) \
            if t else None
        if not m:
            continue
        label_part, meth, rest = m.group(1).strip(), m.group(2).upper(), m.group(3)
        key = (state.get("race"), label_part or state.get("label"))
        if key[0] is None:
            warnings.append(f"img {name}: method row without race")
            continue
        vals = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", rest)]
        if not vals:
            continue
        if label_part:
            state["label"] = label_part
        slot = data.setdefault(key, {}).setdefault(METHODS[meth], [])
        if len(vals) > len(slot):
            slot[:] = vals
        else:
            slot += [0] * (len(vals) - len(slot))


RACE_DIV_RE = re.compile(
    r"(Proposi|SENAT|REPRESENTAT|GOVERNOR|JUDGE|COURT|COMMISSION|BOARD|ATTORNEY|"
    r"JUSTICE|LAND OFFICE|AGRICULTURE|COMPTROLLER|RAILROAD|Constable|"
    r"County Chair|Sheriff|Clerk|Treasurer|Justice of the Peace|District Clerk|"
    r"Tax Assessor)", re.I)


def parse_jsonl(path, file_party):
    """Return {(race, label): {method: [vals with positional blanks]}} +
    warnings."""
    data = {}
    warnings = []
    state = {"race": None, "label": None, "method": None}
    for raw in open(path):
        if not raw.strip():
            continue
        rec = json.loads(raw)
        for pg in rec["result"]["layoutParsingResults"]:
            images = pg.get("markdown", {}).get("images", {}) or {}
            for kind, payload in rows_of(pg["markdown"]["text"]):
                if kind == "img":
                    handle_img(state, payload, images, data, warnings)
                    continue
                if kind == "div":
                    text = clean(payload)
                    if text and not INT_RE.fullmatch(text) and RACE_DIV_RE.search(text) \
                            and len(text) < 100:
                        if state["race"] != text:
                            state["race"] = text
                            state["label"] = None
                    continue
                cells = payload
                nonblank = [c for c in cells if c]
                if not nonblank:
                    continue
                first = next((c for c in nonblank), None)
                # method row?
                mcell = next((c for c in nonblank if c.upper() in METHODS), None)
                if mcell is not None:
                    mi = cells.index(mcell)
                    pre = [c for c in cells[:mi] if c]
                    if pre:
                        state["label"] = pre[0]
                    method = METHODS[mcell.upper()]
                    vals = [int(c.replace(",", "")) if INT_RE.fullmatch(c) else 0
                            for c in cells[mi + 1:]]
                    if state["race"] is None or state["label"] is None:
                        warnings.append(f"method row without label: {nonblank[:4]}")
                        continue
                    slot = data.setdefault((state["race"], state["label"]), {}).setdefault(method, [])
                    if len(vals) > len(slot):
                        slot[:] = vals
                    else:
                        slot += [0] * (len(vals) - len(slot))
                    continue
                # all-int rows right after a method block = faint subtotals
                if all(INT_RE.fullmatch(c) for c in nonblank):
                    continue
                # single non-blank cell: race title or candidate label
                if len(nonblank) == 1:
                    text = nonblank[0]
                    if RACE_DIV_RE.search(text) and len(text) < 100:
                        if state["race"] != text:
                            state["race"] = text
                            state["label"] = None
                            state["method"] = None
                    else:
                        state["label"] = text
                    continue
                warnings.append(f"unparsed row: {nonblank[:4]}")
    return data, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--county", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("sources", nargs="+")
    args = ap.parse_args()
    records = []
    warnings = []
    for src in args.sources:
        base = os.path.basename(src).lower()
        party = "REP" if "_rep" in base else "DEM" if "_dem" in base else "NP"
        data, warns = parse_jsonl(src, party)
        warnings.extend(f"{os.path.basename(src)}: {w}" for w in warns)
        for (race, label), by_method in data.items():
            norm = normalize_office(race) or (clean(race), "")
            office, district = norm
            # last value of each row is the bold block total, not a precinct
            trimmed = {m: (v[:-1] if len(v) > 1 else v)
                       for m, v in by_method.items()}
            ncol = max((len(v) for v in trimmed.values()), default=0)
            for idx in range(ncol):
                vals = {method: (v[idx] if idx < len(v) else 0)
                        for method, v in trimmed.items()}
                total = sum(vals.values())
                records.append({
                    "precinct": precinct_name(str(idx + 1)),
                    "office": office,
                    "district": district,
                    "party": party,
                    "candidate": clean_candidate(label),
                    "votes": str(total),
                    "absentee": str(vals.get("absentee", 0)),
                    "early_voting": str(vals.get("early_voting", 0)),
                    "election_day": str(vals.get("election_day", 0)),
                })
    write_county_csv(args.out, args.county, records, FIELDNAMES)
    print(f"{args.county}: wrote {len(records)} rows -> {args.out} "
          f"(warn {len(warnings)})")
    for w in warnings[:12]:
        print("  WARN", w)


if __name__ == "__main__":
    main()
