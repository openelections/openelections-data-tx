#!/usr/bin/env python3
"""Parse 'box x box' election report tables (Caldwell, Ellis, Limestone etc.,
March 3 2026 Texas primary): race blocks with one column per candidate and one
row per precinct, parsed from word coordinates (pdfplumber).

Block (one vertical 'strip' of races):
  * race title line(s) — may hold TWO race titles side by side (two-panel
    landscape pages), each possibly wrapped vertically with mid-word breaks,
    ending at a 'VOTE FOR' line
  * candidate/label header fragments (multi-line) above the data rows
  * data rows: 'PCT 100 <counts>', 'Precinct 101 <counts>', '1001 <counts>'
  * a 'Totals'-prefixed row ends the block (headers usually repeat between
    pages)

At the end of a strip: the strip's numeric columns are discovered by clustering
x centers of the rows' integer tokens; each race title segment claims the
columns right of its x start up to the next title segment; header fragments
are assigned to the nearest claimed column; Total/Over/Under/Contest columns
are skipped.

Usage:
  uv run python3 python-parsers/parse_2026_box_table.py -c COUNTY -o OUT.csv SOURCE.pdf ...
"""

import argparse
import re
import sys
import os
from collections import defaultdict

import pdfplumber

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers_2026 import normalize_office, precinct_name, write_county_csv  # noqa: E402

FIELDNAMES = ["county", "precinct", "office", "district", "party", "candidate",
              "votes", "absentee", "early_voting", "election_day", "provisional", "limited"]

COUNT_RE = re.compile(r"(?:\d[\d,]*)(?:\.\d+)?%")
SPECIAL_LABEL = re.compile(r"TOTAL|OVERVOTE|UNDERVOTE|CONTEST|CAST|ABSEN|EARLY|ELECTION|TURNOUT|REGISTERED|REJECT|BALLOTS", re.I)


def is_junk_line(txt):
    low = txt.lower()
    for frag in ("statistics", "registered voters", "ballots cast", "voter turnout",
                 "precinct by precinct", "box x box", "primary election",
                 "official results", "unofficial results", "final results",
                 "electionware", "report generated", "custom table report"):
        if frag in low:
            return True
    if re.match(r"^\s*\d+\s+/\s+\d+", txt):
        return True
    if re.search(r"\bcounty,?(?:\s+of)?\s+texas\b", low) and not COUNT_RE.search(txt):
        return True
    if re.match(r"^\s*[a-z ]+county[,]?\s*$", low):
        return True
    if "march" in low and "2026" in low:
        return True
    return False


PARTY_IN_TITLE = re.compile(r"^(?:\(([RDNL])\)\s*|([A-Z]{2,3})\s+)((?:U\.?S\.?|UNITED)?.*)$", re.I)


def is_race_title(txt):
    if COUNT_RE.search(txt) or not txt:
        return False
    if not re.search(r"(SENAT|REPRESENTATIV|GOVERNOR|JUDGE|COURT|COMMISSION|BOARD|"
                     r"PROP|ATTORNEY|SHERIFF|CLERK|TREASURER|CONSTABLE|CHAIR|"
                     r"COMPTROLLER|GENERAL LAND|LAND OFFICE)", txt, re.I):
        return False
    return len(txt) <= 90


def is_title_continuation(txt):
    if COUNT_RE.search(txt) or not txt:
        return False
    if re.match(r"^\s*vote for", txt, re.I):
        return False
    return bool(re.search(r"(SENAT|REPRESENTATIV|GOVERNOR|JUDGE|COURT\b|COMMISSION|BOARD|"
                          r"PROP|ATTORNEY|DISTRICT|SHERIFF|CLERK|TREASURER|CONSTABLE|CHAIR|"
                          r"OFFICE|GENERAL LAND|STATE|MEMBER)", txt, re.I)) and len(txt) <= 70


def strip_party(txt):
    """Strip a leading 'REP '/'DEM '/'(R) ' marker; return (title, party)."""
    party = None
    m = re.match(r"^\(([RDNL])\)\s*(.*)$", txt, re.I)
    if m:
        return m.group(2).strip(), {"R": "REP", "D": "DEM", "N": "NON", "L": "LIB"}[m.group(1).upper()]
    m = re.match(r"^(REPUB|REPUBLICAN|REP|DEMO|DEMOC|DEMOCRATIC|DEM|NON|NONPARTISAN|LIB|GRN)[A-Z. ]", txt, re.I)
    if m:
        code = m.group(1).upper()
        party = {"REPUB": "REP", "REPUBLICAN": "REP", "REP": "REP",
                 "DEMO": "DEM", "DEMOC": "DEM", "DEMOCRATIC": "DEM", "DEM": "DEM",
                 "NON": "NON", "NONPARTISAN": "NON", "LIB": "LIB", "GRN": "GRN"}.get(code, code[:3])
        return txt[m.end(1):].strip(), party
    # suffix-style titles: 'United States Senator - Republican Party - Vote for One'
    if party is None:
        if re.search(r"REPUBLICAN\b", txt, re.I):
            party = "REP"
        elif re.search(r"DEMOCRATIC\b", txt, re.I):
            party = "DEM"
        elif re.search(r"NONPARTISAN\b", txt, re.I):
            party = "NON"
    return txt.strip(), party


def precinct_pid(txt):
    m = re.match(r"^(?:PCT\.?\s*#?\s*|PRECINCT\s+|BOX\s+)?(\d[\d/\-]*)\s", txt, re.I)
    if not m:
        return None
    if not re.match(r"^\d", txt[m.end(1):].strip()):
        return None
    return m.group(1)


def load_pdf_lines(pdf_path):
    """Yield per-page line lists. Text sidecars (.txt, from OCR) are converted
    to synthetic word dicts; whitespace runs become x-gap-separated words."""
    if str(pdf_path).endswith(".txt"):
        with open(pdf_path) as fh:
            blocks = fh.read().split("\n\n")
        for page_text in blocks:
            lines = []
            for raw in page_text.split("\n"):
                words = []
                x = 60.0
                prev_end = 0
                for m in re.finditer(r"\S+", raw):
                    t = m.group(0)
                    gap_chars = len(raw[prev_end:m.start()])
                    if words:
                        x += 7.5 * gap_chars
                    words.append({"text": t, "x0": float(x),
                                  "x1": float(x + 6.4 * len(t)), "top": 0.0})
                    x += 6.4 * len(t)
                    prev_end = m.start()
                if words:
                    lines.append(words)
            yield lines
        return
    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages
        for page in pages:
            words = page.extract_words(x_tolerance=1.5, y_tolerance=3,
                                       keep_blank_chars=False)
            lines = defaultdict(list)
            for w in words:
                lines[round(w["top"] / 4)].append(w)
            yield [sorted(v, key=lambda w: w["x0"]) for _, v in sorted(lines.items())]


def line_text(ws):
    return " ".join(w["text"] for w in ws).strip()


def split_segments(ws, gap=26):
    """Split a line's words into x-gap-separated segments."""
    segs = []
    cur = []
    prev_x1 = None
    for w in ws:
        if prev_x1 is not None and w["x0"] - prev_x1 > gap:
            segs.append(cur)
            cur = []
        cur.append(w)
        prev_x1 = w["x1"]
    if cur:
        segs.append(cur)
    return segs


def seg_range(seg):
    return min(w["x0"] for w in seg), max(w["x1"] for w in seg)


def join_title(parts):
    out = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if out.endswith("-") or (p and p[0].islower()):
            out += p
        elif re.search(r"[A-Z]$", out) and len(out.rsplit(" ", 1)[-1]) <= 2:
            out += p
        else:
            out += " " + p
    return out.strip()


def assemble_name(frags):
    frags = sorted(frags, key=lambda w: (round(w["top"]), w["x0"]))
    name = ""
    for w in frags:
        t = w["text"]
        if name and t and t[0].islower() and len(t) <= 5:
            name += t
        else:
            name += ("" if not name else " ") + t
    return name


def cluster_numeric(tokens):
    """Cluster numeric tokens (x0, x1) by center proximity; sorted output."""
    toks = sorted(((t[0] + t[1]) / 2, t) for t in tokens)
    clusters = []
    for ccx, (x0, x1, text) in toks:
        if clusters and abs(ccx - (clusters[-1]["x0"] + clusters[-1]["x1"]) / 2) <= 9:
            c = clusters[-1]
            c["x0"] = min(c["x0"], x0)
            c["x1"] = max(c["x1"], x1)
        else:
            clusters.append({"x0": x0, "x1": x1})
    return clusters


def parse_strip(strip, records, warnings, pdf_path, default_party=None):
    title_segs = strip["title_segs"]
    if not title_segs:
        return
    # --- numeric column discovery (excluding the pid token of each row)
    tokens = []
    for pid, ws in strip["data_rows"]:
        start = 0
        for w in ws:
            if re.fullmatch(r"\d[\d,]*", w["text"]):
                start = 1
                break
        # tokens: all integer words except the first numeric one (the pid)
        dropped = False
        for w in ws:
            if re.fullmatch(r"\d[\d,]*", w["text"]) and not dropped:
                dropped = True
                continue
            if re.fullmatch(r"\d[\d,]*", w["text"]):
                tokens.append((w["x0"], w["x1"], w["text"]))
    clusters = cluster_numeric(tokens)
    if not clusters:
        warnings.append("%s: strip with no numeric columns" % (pdf_path,))
        return
    # --- label each column from the header fragments
    by_col = defaultdict(list)
    for ws in strip["header_rows"]:
        for w in ws:
            cx = (w["x0"] + w["x1"]) / 2
            best, bestd = None, None
            for i, c in enumerate(clusters):
                ccx = (c["x0"] + c["x1"]) / 2
                d = abs(cx - ccx)
                if bestd is None or d < bestd:
                    bestd, best = d, i
            if best is not None and bestd <= (clusters[best]["x1"] - clusters[best]["x0"]) / 2 + 55:
                by_col[best].append(w)
    col_label = {}
    col_candidate = {}
    col_special = set()
    for i, c in enumerate(clusters):
        name = assemble_name(by_col.get(i, []))
        col_label[i] = name
        if name and SPECIAL_LABEL.search(name):
            col_special.add(i)
        elif name:
            col_candidate[i] = name
        else:
            warnings.append("%s: unlabeled column at x=%d" % (pdf_path, round(c["x0"])))
            col_special.add(i)
    # --- pane split. Anchor: party-marker words (a bare 'DEM'/'REP' per pane,
    # from marker rows or leading a title line).
    pane_starts = []
    for ws in strip.get("marker_rows", []) + [seg["words"] for seg in title_segs]:
        for w in ws:
            if re.fullmatch(r"(?:DEM|REP|NON|LIB|GRN)\b", w["text"], re.I):
                x = round(w["x0"])
                if not pane_starts or all(abs(x - p) > 12 for p in pane_starts):
                    pane_starts.append(x)
    pane_starts.sort()
    cols_all = sorted(range(len(clusters)), key=lambda j: clusters[j]["x0"])
    panes = []
    if pane_starts:
        for k, px in enumerate(pane_starts):
            lo = -10**9 if k == 0 else pane_starts[k] - 25
            nxt = pane_starts[1] - 25 if k == 0 and len(pane_starts) > 1 else (
                pane_starts[k + 1] - 25 if k + 1 < len(pane_starts) else 10**9)
            colpane = [i for i in cols_all if lo <= clusters[i]["x0"] < nxt]
            if colpane:
                panes.append(colpane)
    else:
        # fallback: each pane's columns run through its first 'CONTEST' column
        cur_cols = []
        for i in cols_all:
            cur_cols.append(i)
            if i in col_special and "CONTEST" in col_label[i].upper():
                panes.append(cur_cols)
                cur_cols = []
        if cur_cols:
            panes.append(cur_cols)
    pane_meta = []
    for cols in panes:
        cands = [i for i in cols if i in col_candidate]
        if not cands:
            continue
        pane_meta.append({
            "cols": cols,
            "x0": clusters[cols[0]]["x0"],
            "x1": clusters[cols[-1]]["x1"],
            "start": (pane_starts[k2] if False else None),
            "title": "",
            "party": None,
            "cands": cands,
        })
    if not pane_meta:
        return
    # record each pane's marker start for title assignment
    if pane_starts:
        for k2, px in enumerate(pane_starts):
            nxt = pane_starts[k2 + 1] if k2 + 1 < len(pane_starts) else 10**9
            colpane = [i for i in cols_all
                       if pane_starts[k2] - 25 <= clusters[i]["x0"] < nxt - 25]
            if colpane and any(pm["cols"] == colpane for pm in pane_meta):
                for pm in pane_meta:
                    if pm["cols"] == colpane:
                        pm["start"] = px
    # --- assign title fragments to panes by word x
    pane_frags = defaultdict(list)
    starts = [pm["start"] if pm["start"] is not None else pm["x0"] for pm in pane_meta]
    for seg in title_segs:
        for w in seg["words"]:
            cx = (w["x0"] + w["x1"]) / 2
            best = 0
            for pi, px in enumerate(starts):
                if cx >= px - 25:
                    best = max(best, pi)
            pane_frags[best].append(w)
    for pi, pm in enumerate(pane_meta):
        joined = join_title([w["text"] for w in sorted(pane_frags[pi],
                            key=lambda w: (round(w["top"]), w["x0"]))])
        title, party = strip_party(joined)
        pm["title"] = title
        pm["party"] = party or default_party
        if not title:
            warnings.append("%s: pane without title (cols %d..%d)" % (
                pdf_path, pm["x0"], pm["x1"]))
    # --- emit rows
    for pid, ws in strip["data_rows"]:
        vals = {}
        unassigned = []
        dropped = False
        for w in ws:
            if re.fullmatch(r"\d[\d,]*", w["text"]) and not dropped:
                dropped = True
                continue
            text = w["text"]
            if not re.fullmatch(r"\d[\d,]*", text):
                continue
            cx = (w["x0"] + w["x1"]) / 2
            best, bestd = None, None
            for i, c in enumerate(clusters):
                ccx = (c["x0"] + c["x1"]) / 2
                d = abs(cx - ccx)
                if bestd is None or d < bestd:
                    bestd, best = d, i
            if best is None or bestd > 12 or best in vals:
                unassigned.append(text)
                continue
            vals[best] = int(text.replace(",", ""))
        prec = precinct_name(pid) if pid else None
        if prec is None:
            continue
        for pi, pm in enumerate(pane_meta):
            if not pm["title"]:
                continue
            norm = normalize_office(pm["title"])
            office, district = norm if norm else (
                re.sub(r"\s+", " ", pm["title"].replace("#", " ")).strip(), "")
            party = pm["party"] or "NON"
            for i in pm["cands"]:
                if i in vals:
                    records.append({
                        "precinct": prec, "office": office, "district": district,
                        "party": party, "candidate": col_candidate[i],
                        "votes": str(vals[i]),
                    })
        if unassigned:
            warnings.append("%s: %r: unassigned values %s" % (
                pdf_path, prec, unassigned[:4]))


def parse_files(files, page_limit=None, default_party=None):
    records = []
    warnings = []
    for pdf_path in files:
        strip = {"title_segs": [], "header_rows": [], "data_rows": [], "marker_rows": []}
        state = "between"
        pane_seq = 0

        def end_strip():
            nonlocal strip, state, pane_seq
            if state == "indata" and strip["data_rows"]:
                parse_strip(strip, records, warnings, pdf_path, default_party)
            strip = {"title_segs": [], "header_rows": [], "data_rows": [], "marker_rows": []}
            state = "between"
            pane_seq = 0

        pages = load_pdf_lines(pdf_path)
        for lines in pages:
            for ws in lines:
                txt = line_text(ws)
                if not txt or is_junk_line(txt):
                    continue
                if is_race_title(txt):
                    if state in ("indata", "inheader"):
                        end_strip()
                    state = "intitle"
                    pane_seq += 1
                    for seg in split_segments(ws):
                        sx0, _sx1 = seg_range(seg)
                        stext, party_ = strip_party(line_text(seg))
                        strip["title_segs"].append({
                            "first": True, "x0": sx0, "x1": seg[-1]["x1"],
                            "words": seg,
                            "txt": stext, "party": party_,
                        })
                    continue
                if state == "intitle":
                    if re.match(r"^\s*vote for", txt, re.I):
                        state = "inheader"
                        continue
                    if is_title_continuation(txt):
                        for seg in split_segments(ws):
                            sx0, _sx1 = seg_range(seg)
                            stext, sparty = strip_party(line_text(seg))
                            strip["title_segs"].append({
                                "first": False, "x0": sx0, "x1": seg[-1]["x1"],
                                "words": seg,
                                "txt": stext, "party": sparty,
                            })
                        continue
                    state = "inheader"
                    # fall through to header handling
                if state in ("inheader", "indata", "intitle") and len(ws) >= 2 and all(
                        re.fullmatch(r"(?:DEM|REP|NON|LIB|GRN)", w["text"], re.I) for w in ws):
                    strip["marker_rows"].append(ws)
                    continue
                if state == "inheader" or state == "indata":
                    pid = precinct_pid(txt)
                    if pid is not None:
                        state = "indata"
                        strip["data_rows"].append((pid, ws))
                        continue
                    if state == "indata" and re.match(r"^\s*totals?\b|\btotal votes cast\b",
                                                      txt, re.I):
                        end_strip()
                        continue
                    if re.match(r"^\s*vote for", txt, re.I):
                        continue
                    if not re.search(r"\d", txt):
                        strip["header_rows"].append(ws)
                        continue
                    warnings.append(f"{pdf_path}: unhandled line: {txt[:70]!r}")
                # between: ignore
        if state == "indata" and strip["data_rows"]:
            parse_strip(strip, records, warnings, pdf_path)
    return records, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--county", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--page-limit", type=int, default=None)
    ap.add_argument("--party", default=None, help="default party when the strip's title lacks one")
    args = ap.parse_args()
    dp = None
    if args.party:
        dp = {"R": "REP", "D": "DEM", "REP": "REP", "DEM": "DEM"}.get(args.party.upper(), args.party.upper())
    records, warnings = parse_files(args.sources, page_limit=args.page_limit, default_party=dp)
    write_county_csv(args.out, args.county, records, FIELDNAMES)
    print(f"{args.county}: wrote {len(records)} rows -> {args.out}")
    from collections import Counter
    c = Counter(w.split(":", 1)[-1][:66] for w in warnings)
    for w, n in c.most_common(8):
        print(f"  WARN {n}x {w}")


if __name__ == "__main__":
    main()