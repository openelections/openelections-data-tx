#!/usr/bin/env python3
"""Parse 2014 Texas primary 180-char fixed-width ASC files (Hart/Texas SOS export)
into per-county precinct CSVs.

Layout (see docs in header of old python-parsers/asc.py prototypes; verified
against Bexar/Angelina March 2014 files):

  [0:4]    contest number
  [4:7]    candidate number
  [7:11]   precinct code
  [11:17]  total votes (6)
  [17:20]  party code (REP/DEM/blank)
  [20:27]  filler
  [27:83]  contest title (56)
  [83:121] candidate label (38)
  [121:151] precinct name (30)
  [151:181] extra (district name etc.)

Usage:
  uv run python3 python-parsers/parse_2014_asc.py -c Angelina \
      -o 2014/counties/20140304__tx__primary__angelina__precinct.csv SRC1.ASC SRC2.ASC

Multiple sources (e.g. main + early-vote exports) are merged: rows are keyed on
(contest, candidate#, precinct code) and appended; an exact duplicate row is
dropped only when (contest, candidate, precinct-key) was already seen with the
same candidate label -- otherwise rows accumulate and verification against the
county baseline catches over-counts.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers_2026 import normalize_office, precinct_name, write_county_csv  # noqa: E402

FIELDNAMES = ["county", "precinct", "office", "district", "party", "candidate",

              "votes"]
SKIP_LABELS = ("REGISTERED VOTERS", "BALLOTS CAST")


def clean_title(title, county=""):
    """Strip county report noise from a contest title before normalization."""
    t = title.strip()
    if county:
        t = re.sub(rf"\s*{re.escape(county)}\s+COUNTYWIDE\s*$", "", t, flags=re.I)
    t = re.sub(r"\s+COUNTYWIDE\s*$", "", t, flags=re.I)
    # trailing helper fragments: COMM PCT 1, JOP 1, UPT 2, etc.
    t = re.sub(r"\s+(COMM|COMMISSIONER|JOP|PCT)\s+(PCT|PLACE|PL|NO\.?)?\s*\d+\s*$", "", t, flags=re.I)
    # bare place abbreviations: 'P7', 'Pl. 4' -> 'PLACE 7' / 'PLACE 4'
    t = re.sub(r"\bP\.?L?\.?\s+(\d)", r"PLACE \1", t, flags=re.I)
    t = re.sub(r"\bP(\d)\b", r"PLACE \1", t, flags=re.I)
    t = re.sub(r"\bPL(\d)\b", r"PLACE \1", t, flags=re.I)
    t = re.sub(r"\s+$", "", t).strip(" ,")
    return t


def parse_lines(raw):
    """Auto-detect the layout per file: the 180-char 'NON' style (no
    breakdown columns) or the classic 208-char style (early/ED/provisional
    columns after the total)."""
    nonempty = [l for l in raw if l.strip()]
    if not nonempty:
        return [], []
    import statistics
    med = statistics.median(len(l) for l in nonempty[:200])
    layout = "208" if med >= 195 else "180"
    rows, bad = [], []
    for n, line in enumerate(raw, 1):
        if not line.strip():
            continue
        if layout == "208":
            if len(line) < 181:
                bad.append((n, len(line), line[:60]))
                continue
            try:
                votes = int(line[11:17])
            except ValueError:
                bad.append((n, -1, line[:50]))
                continue
            r = {
                "contest": line[0:4].strip(),
                "cand_no": line[4:7].strip(),
                "pct_code": line[7:11].strip(),
                "pct_name": line[151:181].strip(),
                "party": line[47:50].strip(),
                "title": line[57:113].strip(),
                "label": (line[113:151].strip() or line[57:113].strip()),
                "votes": votes,
                "early_voting": int(line[17:23] or 0),
                "election_day": int(line[23:29] or 0),
                "provisional": int(line[29:35] or 0),
            }
            skip = any(k in r["label"].upper() for k in SKIP_LABELS)
            r["skip"] = skip
            rows.append(r)
            continue
        if len(line) < 151:
            bad.append((n, len(line), line[:60]))
            continue
        votes_txt = line[11:17].strip()
        try:
            votes = int(votes_txt)
        except ValueError:
            bad.append((n, -1, line[:50]))
            continue
        title = line[27:83].strip()
        cand = line[83:121].strip()
        pct_code = line[7:11].strip()
        pct_name = line[121:151].strip()
        party_raw = line[17:20].strip()
        label = cand or title
        skip = any(k in label.upper() for k in SKIP_LABELS)
        rows.append({
            "contest": line[0:4].strip(),
            "cand_no": line[4:7].strip(),
            "pct_code": pct_code,
            "pct_name": pct_name,
            "party": party_raw,
            "title": title,
            "label": label,
            "skip": skip,
            "votes": votes,
        })
    return rows, bad


def party_from_filename(path, fallback=""):
    b = os.path.basename(path).lower()
    if "democratic" in b or "dem" in b:
        return "DEM"
    if "republican" in b or re.search(r"[^a-z]rep[^a-z]", b):
        return "REP"
    return fallback


def run_county(county, out, sources, party_default=None):
    all_rows, seen, seen_dup = [], {}, 0
    bad_total = []

    # Many county exports ship one identical file under both party names; the
    # rows themselves are labeled DEM/REP. Drop byte-identical inputs.
    import hashlib
    uniq_srcs = {}
    for src in sources:
        h = hashlib.md5(open(src, "rb").read()).hexdigest()
        if h in uniq_srcs:
            print(f"skipping {os.path.basename(src)} (identical to {uniq_srcs[h]})")
            continue
        uniq_srcs[h] = os.path.basename(src)
        party = party_from_filename(src, party_default or "")
        raw = open(src, encoding="latin-1").read().splitlines()
        rows, bad = parse_lines(raw)
        bad_total += [(os.path.basename(src),) + b for b in bad]
        n_before = len(all_rows)
        for r in rows:
            # Merge rows across sources: key on (party label if explicit,
            # contest, candidate, precinct, label). On a collision keep the
            # row with the LARGER vote count (e.g. Bexar ships a full export
            # plus an early-votes-only export of the same contests).
            eff = r["party"].upper()
            if eff not in ("DEM", "REP"):
                eff = ""
            key = (eff, r["contest"], r["cand_no"], r["pct_code"], r["label"])
            idx = seen.get(key)
            if idx is not None:
                if r["votes"] > all_rows[idx]["votes"]:
                    all_rows[idx] = r
                seen_dup += 1
                continue
            seen[key] = len(all_rows)
            if eff:
                r["eff_party"] = eff
            elif party:
                r["eff_party"] = party
            elif not r.get("eff_party"):
                r["eff_party"] = r["party"]
            all_rows.append(r)
        print(f"{os.path.basename(src)}: {len(rows)} lines, party={party} "
              f"({len(all_rows) - n_before} new rows, bad={len(bad)})")

    has_breakdown = any("early_voting" in r and str(r.get("early_voting")) != "" for r in all_rows)
    fieldnames = ["county", "precinct", "office", "district", "party", "candidate", "votes"]
    if has_breakdown:
        fieldnames += ["early_voting", "election_day", "provisional"]
    out_rows = []
    for r in all_rows:
        title = clean_title(r["title"], county)
        res = normalize_office(title)
        if res:
            office, district = res[0], (res[1] if len(res) > 1 else "")
        else:
            office, district = title.title(), ""
        rec = {
            "county": county,
            "precinct": precinct_name(r["pct_name"]) if r["pct_name"] else r["pct_code"].lstrip("0") or r["pct_code"],
            "office": office,
            "district": district,
            "party": r.get("eff_party", r["party"]),
            "candidate": r["label"],
            "votes": r["votes"],
        }
        if has_breakdown:
            rec["early_voting"] = r.get("early_voting", "")
            rec["election_day"] = r.get("election_day", "")
            rec["provisional"] = r.get("provisional", "")
        out_rows.append(rec)
    write_county_csv(out, county, out_rows, fieldnames)
    print(f"wrote {out}: {len(out_rows)} rows "
          f"({seen_dup} duplicate rows dropped, {len(bad_total)} bad lines)")
    for b in bad_total[:8]:
        print("  bad:", b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--county", required=True, help="County name (Title Case)")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--party", choices=("DEM", "REP"),
                    help="party for files whose name doesn't carry one")
    ap.add_argument("sources", nargs="+")
    args = ap.parse_args()
    run_county(args.county, args.out, args.sources, args.party)


if __name__ == "__main__":
    main()
