#!/usr/bin/env python3
"""Parse transposed county-canvass tables (Newton County 2026 primary): voting
boxes as columns, candidates as rows, office titles between race groups.

Header: a 'Voting Box <ids> ... Total' row whose ids may wrap onto nearby lines
('11, 13,' / '21' above/below). Data rows: candidate label + one value per box;
the label is often split across the lines above and below the value row.
Race titles: office lines with at most one number ('Federal', 'US Senator',
'State' + 'Governor' are joined with neighbors).

Usage:
  uv run python3 python-parsers/parse_2026_transposed.py -c COUNTY --party DEM \\
        -o OUT.csv SOURCE.pdf ...
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

TITLE_RE = re.compile(
    r"(SENAT|REPRESENTATIV|GOVERNOR|JUDGE(|MENT)|COURT(?!NEY)|COMMISSION|BOARD|PROP|ATTORNEY|"
    r"SHERIFF|CLERK|TREASURER|CONSTABLE|CHAIR|COMPTROLLER|LAND|FEDERAL)", re.I)

NUMBERS_RE = re.compile(r"\b\d[\d,]*\b")
INT_RE = re.compile(r"\d[\d,]*")


def load_pages(pdf_path):
    if str(pdf_path).endswith(".txt"):
        with open(pdf_path) as fh:
            blocks = fh.read().split("\n\n")
        for page_text in blocks:
            lines = []
            for raw in page_text.split("\n"):
                ws = []
                x = 60.0
                prev_end = 0
                for m in re.finditer(r"\S+", raw):
                    t = m.group(0)
                    gap_chars = len(raw[prev_end:m.start()])
                    if ws:
                        x += 7.5 * gap_chars
                    ws.append({"text": t, "x0": float(x),
                               "x1": float(x + 6.4 * len(t)), "top": 0.0,
                               "x1_raw": x})
                    x += 6.4 * len(t)
                    prev_end = m.start()
                if ws:
                    lines.append((" ".join(w["text"] for w in ws).strip(), ws))
            yield lines
        return
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=1.5, y_tolerance=3,
                                       keep_blank_chars=False)
            rows = defaultdict(list)
            for w in words:
                rows[round(w["top"] / 4)].append(w)
            lines = [sorted(v, key=lambda w: w["x0"]) for _, v in sorted(rows.items())]
            yield [(" ".join(w["text"] for w in ws).strip(), ws) for ws in lines]


def main():
    import os as _os
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--county", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--party", default="NON")
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--trace", action="store_true")
    args = ap.parse_args()
    party = {"R": "REP", "D": "DEM", "REP": "REP", "DEM": "DEM"}.get(
        args.party.upper() if args.party else "", None) or args.party.upper()

    records = []
    warnings = []

    def is_name_frag(txt):
        """A short, digit-free line that is part of a wrapped candidate name."""
        return (txt and len(txt) < 40 and not re.search(r"\d", txt)
                and not TITLE_RE.search(txt)
                and not re.match(r"^\s*(registered|ballots|page)\b", txt.lower()))

    SECTION_RE = re.compile(r"^(Early Vote|Election Day|Grand Totals|Early|Total)$", re.I)
    for pdf_path in args.sources:
        col_ids = None        # [(x_center, id)]
        header_first_x = None
        last_name = None
        race = None           # (office, district) or None
        state = "pre"         # pre | title | data
        section = "Grand Totals"   # 'Early Vote' | 'Election Day' | 'Grand Totals'
        # (default 'Grand Totals': files without section banners emit everything)
        file_party = None

        for page in load_pages(pdf_path):
            n = len(page)
            i = 0
            consumed_frag = set()
            last_trigger = None
            header_pairs = []
            # section header + party are declared on the page's banner rows
            for t, _ws in page[:8]:
                m = SECTION_RE.fullmatch(t.strip())
                if m:
                    section = m.group(1)
                if re.search(r"Democratic Primary Canvass", t, re.I):
                    file_party = "DEM"
                elif re.search(r"Republican Primary Canvass", t, re.I):
                    file_party = "REP"
            # view marker (BBM / EV / ED): which vote-method view this page shows
            view_method = None
            for t, _ws in page[:8]:
                tok = t.upper()
                if re.search(r"\bBBM\b", tok):
                    view_method = "mail"
                elif re.search(r"(?:^|\s)EV(?=\b|$)", tok):
                    view_method = "early_voting"
                elif re.search(r"(?:^|\s)ED(?=\b|$)", tok):
                    view_method = "election_day"
                elif re.search(r"Early (Vote|)", t, re.I) and view_method is None:
                    view_method = "early_voting"
                elif re.search(r"Election Day", t, re.I) and view_method is None:
                    view_method = "election_day"
            emitting = section is not None and "Total" in section
            page_party = party if party != "NON" else (file_party or party)

            def has_values(idx):
                if idx < 0 or idx >= n:
                    return False
                _, ws = page[idx]
                cnt = 0
                for w in ws:
                    if INT_RE.fullmatch(w["text"]):
                        cnt += 1
                return cnt >= 3

            while i < n:
                txt, ws = page[i]
                low = txt.lower()
                if not txt:
                    i += 1
                    continue

                id_tokens = [w["text"].strip(",.") for w in ws
                             if re.fullmatch(r"(?i)(?:PCT|PRECINCT|BOX)\W*#?\d+",
                                             w["text"].strip(",."))
                             or re.fullmatch(r"\d+", w["text"].strip(",."))
                             or re.fullmatch(r"(?i)(BBM|ABSENTEE|MAIL|EARLY VOTE|EARLY|LIMITED)", w["text"].strip(",."))]
                pct_tokens = [w for w in ws
                              if re.fullmatch(r"(?i)(?:PCT|PRECINCT|BOX)\W*#?\d+",
                                              w["text"].strip(",."))]
                if re.search(r"\bVoting Box\b", low, re.I) or len(pct_tokens) >= 3:
                    if _os.environ.get("TR"):
                        print("HDR", i, txt[:40], file=sys.stderr)
                    if last_trigger is not None and i - last_trigger <= 3:
                        pairs = header_pairs  # continuation of the same header
                    else:
                        pairs = []
                    last_trigger = i
                    header_pairs = pairs
                    for w in ws:
                        t = w["text"].strip(",.")
                        mt = re.fullmatch(r"(?i)(?:PCT|PRECINCT|BOX)\W*#?(\d+)", t)
                        tt = mt.group(1) if mt else (t if re.fullmatch(r"\d+", t) else None)
                        if not tt and re.fullmatch(r"(?i)(BBM|ABSENTEE|MAIL|LIMITED)", t):
                            tt = t
                        if tt and tt.lower() != "total":
                            pairs.append(((w["x0"] + w["x1"]) / 2, tt))
                    # also collect id fragments from the neighbouring lines
                    # (wrapped ids like '11, 13,' / '21' or 'PCT5...')
                    for k in (i - 1, i + 1):
                        if 0 <= k < n:
                            t2 = page[k][0]
                            if t2 and (re.fullmatch(r"[\d, ]+", t2) or
                                       len(re.findall(r"(?i)(?:PCT|PRECINCT|BOX)\W*\d+",
                                                      t2)) >= 2):
                                for w in page[k][1]:
                                    t3 = w["text"].strip(",.")
                                    mt = (re.fullmatch(r"(?i)(?:PCT|PRECINCT|BOX)\W*#?(\d+)", t3)
                                          or re.fullmatch(r"(?i)(BBM|ABSENTEE|MAIL|LIMITED)", t3))
                                    tt = (mt.group(1) or mt.group(0)) if mt else (t3 if re.fullmatch(r"\d+", t3) else None)
                                    if tt and tt.lower() != "total":
                                        pairs.append(((w["x0"] + w["x1"]) / 2, tt))
                    if len(pairs) >= 3 and emitting:
                        col_ids = pairs
                        header_first_x = min(x for x, _ in col_ids)
                        race = None
                        state = "data"
                    i += 1
                    continue

                if state in ("pre",) or col_ids is None or not emitting:
                    i += 1
                    continue

                if re.match(r"^\s*(registered voters|ballots counted|early vote)\b", low) \
                        or re.match(r"^\s*page\b", low, re.I):
                    i += 1
                    continue

                # office title?
                numcnt = len(NUMBERS_RE.findall(txt))
                if TITLE_RE.search(txt) and (numcnt == 0 or
                                             (numcnt <= 1 and not INT_RE.fullmatch(txt.split()[-1]))):
                    title_parts = [txt]
                    j = i + 1
                    while j < n:
                        t2, _ws2 = page[j]
                        if not t2:
                            j += 1
                            continue
                        if re.match(r"^\s*page\b", t2.lower()):
                            break
                        # a title-continuation line: short, ≤1 number, no values
                        if (has_values(j) or len(NUMBERS_RE.findall(t2)) > 1):
                            break
                        if TITLE_RE.search(t2) or is_name_frag(t2) or len(t2) <= 40:
                            if len(NUMBERS_RE.findall(t2)) == 0 and (
                                    TITLE_RE.search(t2) or len(t2) <= 40):
                                title_parts.append(t2)
                                j += 1
                                continue
                        break
                    title = " ".join(title_parts)
                    norm = normalize_office(title)
                    race = norm if norm else (
                        re.sub(r"\s+", " ", title.replace("#", " ")).strip(), "")
                    i = j
                    continue

                # data row?
                values = [w for w in ws if INT_RE.fullmatch(w["text"].rstrip(".,"))
                          and w["x1"] > header_first_x - 8]
                own_label = [w for w in ws
                             if w["x1"] <= header_first_x - 8
                             and w["text"].strip(",.")]
                if not values:
                    i += 1
                    continue
                # does the row two lines ahead start a label-less value line?
                # (then the line after ours belongs to THAT row, not to us)
                own_label_of = lambda idx: [w for w in page[idx][1]
                                            if w["x1"] <= header_first_x - 8
                                            and w["text"].strip(",.")]
                two_ahead_unlabeled = (i + 2 < n and has_values(i + 2)
                                       and page[i + 2][1]
                                       and not own_label_of(i + 2))
                name_src = list(own_label)
                if i > 0 and i - 1 not in consumed_frag and is_name_frag(page[i - 1][0])                         and not has_values(i - 1):
                    name_src = page[i - 1][1] + name_src
                    consumed_frag.add(i - 1)
                if i + 1 < n and i + 1 not in consumed_frag and is_name_frag(page[i + 1][0])                         and not has_values(i + 1) and not two_ahead_unlabeled:
                    label_tokens = [w["text"].strip('",.') for w in own_label]
                    # a single-token label is the middle part of a wrapped name;
                    # a complete (>=2 token) label leaves the fragment to the next
                    # row, where it sits as that row's leading part
                    if len(label_tokens) <= 1:
                        name_src = name_src + page[i + 1][1]
                        consumed_frag.add(i + 1)
                label_text = " ".join(w["text"] for w in sorted(name_src, key=lambda w: (w["top"], w["x0"]))).strip()
                vals = {}
                for w in values:
                    x = (w["x0"] + w["x1"]) / 2
                    best, bestd = None, None
                    for x_col, pid in col_ids:
                        d = abs(x - x_col)
                        if bestd is None or d < bestd:
                            bestd, best = d, pid
                    if bestd is None or bestd > 26:
                        warnings.append(f"{pdf_path}: value {w['text']} unaligned "
                                        f"in {label_text[:26]!r}")
                        continue
                    vals[best] = w["text"].replace(",", "")
                # Panola-style: a row whose label is (partly) a vote-method
                # token ('EARLY' / 'ABSENTEE' / 'PRECINCT') continues the
                # previous candidate's rows under that method
                row_view = None
                method_word = None
                for tok, meth in (("EARLY", "early_voting"), ("ABSENTEE", "absentee"),
                                  ("PRECINCT", "election_day")):
                    if re.fullmatch(r"(?i)" + tok, label_text.strip()):
                        method_word = tok
                        row_view = meth
                        break
                if label_text:
                    if _os.environ.get("TR"):
                        print("ROW", i, label_text[:40], len(vals), "vals", vals.get("1"),
                              file=sys.stderr)
                    name = re.sub(r"\s+", " ", label_text).strip()
                    if method_word:
                        # strip the method word ('Yes' + 'EARLY' -> 'Yes'); a
                        # label that is only the method word reuses the
                        # previous candidate's name
                        name = re.sub(r"\s*(?i)" + method_word + r"\s*", " ", " " + name + " ").strip()
                        if re.fullmatch(r"(?i)" + method_word, name):
                            name = (last_name or name)
                        elif not name:
                            name = (last_name or name)
                    last_name = name
                    office, district = race if race else ("", "")
                    for pid, v in vals.items():
                        if str(pid).lower() == "total":
                            continue
                        prec = precinct_name(str(pid))
                        records.append({
                            "precinct": prec, "office": office,
                            "district": district, "party": page_party, "candidate": name,
                            "votes": v, "_view": (row_view or view_method),
                        })
                i += 1

    # merge per-view records (a BBM/EV/ED-titled view of the same race): the
    # views' values become the breakdown columns and votes = the sum
    merged = {}
    for rec in records:
        view = rec.pop("_view", None)
        k = (rec["precinct"], rec["office"], rec.get("district") or "",
             rec["party"], rec["candidate"])
        g = merged.setdefault(k, {"rec": rec, "views": {}})
        if view:
            g["views"][view] = rec["votes"]
        else:
            g["views"]["votes"] = rec["votes"]
    out = []
    for k, g in merged.items():
        rec = dict(g["rec"])
        total = 0
        for view, v in g["views"].items():
            try:
                n = int(v or 0)
            except ValueError:
                n = 0
            if view in ("absentee", "early_voting", "election_day",
                        "provisional", "limited"):
                rec[view] = str(n)
                if view == "absentee":
                    pass
            total += n
        if not rec.get("votes") or not g["views"].get("votes"):
            rec["votes"] = "" if False else str(total)
        out.append(rec)
    records = out

    write_county_csv(args.out, args.county, records, FIELDNAMES)
    print(f"{args.county}: wrote {len(records)} rows -> {args.out}")
    c = __import__("collections").Counter(w.split(":")[-1][:44] for w in warnings)
    for w, n in c.most_common(6):
        print(f"  WARN {n}x {w}")


if __name__ == "__main__":
    main()