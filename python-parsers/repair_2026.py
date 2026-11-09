#!/usr/bin/env python3
"""Repair candidate/office labels in the 2026 primary precinct CSVs using the
county-level SOS baseline. In order:
  1. candidate-name lookups: exact sorted-words, reversed-name rendering,
     compressed text, junk-word containment, office+name combo, reverse
     containment (missing initial), fuzzy 1-word variants. A match rewrites
     (office, district, candidate[, party]) to the baseline form.
  2. office text compression against the baseline office vocabulary (fixes
     word-wrap damage like 'Courtof' and strips '- Republican Party - Vote
     for One' tails, recovering the party from the tail)

Usage: uv run python3 python-parsers/repair_2026.py FILE.csv [FILE.csv ...]
"""

import csv
import re
import sys
import os
import difflib
import unicodedata
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers_2026 import load_county_baseline  # noqa: E402

JUNK_WORDS = {"DEM", "REP", "R", "D", "I", "COUNTY", "STATE", "THE", "OF",
              "PRECINCT", "PCT", "BOX", "NONPARTISAN", "LIB", "GRN",
              "COMMISSIONER", "COMPTROLLER", "COMPTROLLERS", "ATTORNEY", "GENERAL",
              "LAND", "RAILROAD", "SUPREME", "CHIEF", "JUSTICE", "COURT", "JUDGE",
              "DISTRICT", "SENATE", "SENATOR", "REPRESENTATIVE", "HOUSE", "BOARD",
              "EDUCATION", "GOVERNOR", "LIEUTENANT", "APPEALS", "PUBLIC",
              "ACCOUNTS", "OFFICE", "PROPOSITION", "UNEXPIRED", "TERM",
              "UNITED", "STATES", "CRIMINAL", "JUDICIAL", "PLACE", "PACES",
              "MULTICOUNTY", "AT", "LAW", "PROBATE", "COURTS", "APP", "AGRICULTURE",
              "CRIM", "CTOF", "RESENTATIVE", "COMMISS", "IONER", "PEACE", "UNEXP",
              "MEMBER", "REPRECIN", "SHERIFF", "ASSESSOR", "NUMBER", "COLLECTOR",
              "DA", "RJ", "REPJ", "REPC", "DEMOCRAT", "PRIMARY", "JUDGES",
              "REPRESE", "NTATIVE", "CT", "PRECINCTS", "JR", "SR", "II", "III", "IV",
              "MR", "MRS", "MD", "ESQ", "PHD", "DEMOCRATS", "JUNIOR", "SENIOR"}

JUNK_TAIL = re.compile(
    r"^[A-Z0-9]*(?:PARTY|VOTE|VOTEFOR|VOTEYES|YES|ONE|NONEORONE|NOMORETHANTHAN|"
    r"UNEXPIRED|TERM|REPUBLICANP|DEMOCRATICP|REPB|DEMB|NONPARTISANP)[A-Z0-9]*$", re.I)


def words(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.findall(r"[A-Z]+", s.upper().replace('"', "").replace("'", ""))


def compress(s):
    return "".join(words(s))


def title_case_cand(s):
    return s.title()


def match_in(index, index_compact, r, ws):
    """Return a matching baseline tuple (office, district, party, cand), else None."""
    key = " ".join(sorted(ws))
    matches = index.get(key, [])
    if not matches:
        rev = []
        for tok in re.split(r"\s+", r["candidate"].strip()):
            t2 = tok[::-1]
            rev.extend(re.findall(r"[A-Z][a-z]*", t2) or [t2.upper()])
        key_rev = " ".join(sorted(w.upper() for w in rev))
        matches = index.get(key_rev, [])
    if not matches:
        matches = index_compact.get("".join(ws), [])
    if not matches:
        # drop quoted nicknames ("Shamwow") before the containment match
        stripped_q = re.sub(r'"[^"]*"', "", r["candidate"])
        ws_strip = words(stripped_q) or ws
        wb = set(ws_strip)
        cands = []
        for k2, lst in index.items():
            kw = set(k2.split())
            extras = wb - kw
            if kw <= wb and len(extras) <= 3 and extras and all(x in JUNK_WORDS for x in extras):
                cands.append(lst[0])
        if len(cands) == 1:
            matches = cands
        elif cands:
            exact = [m for m in cands if m[0].upper() == r["office"].upper()
                     and m[1].upper() == (r["district"] or "").upper()]
            sp = [m for m in cands if m[2] == r["party"]]
            if len({(m[0], m[1]) for m in cands}) == 1:
                matches = cands
            elif len(exact) == 1:
                matches = exact
            elif len(sp) == 1:
                matches = sp
    if not matches:
        # name split across the row's office title and the candidate label
        combo = sorted(words(r["office"]) + ws)
        lst = index.get(" ".join(combo), [])
        if lst and len({(m[0], m[1]) for m in lst}) == 1:
            matches = lst
    if not matches:
        # baseline has words the label dropped ('John Adefope' vs 'John O. Adefope')
        cands = defaultdict(list)
        for k2, lst in index.items():
            kw = set(k2.split())
            miss = kw - set(ws)
            if set(ws) <= kw and 0 < len(miss) <= 2:
                cands[(lst[0][0], lst[0][1], lst[0][2], lst[0][3])].append(lst[0])
        cand_list = list(cands.values())
        if len(cand_list) == 1:
            matches = cand_list[0]
        else:
            uniq = {(m[0][0], m[0][1]) for m in cand_list}
            if len(uniq) == 1:
                sp = [m[0] for m in cand_list if m[0][2] == r["party"]]
                if len(sp) == 1:
                    matches = sp
    if not matches:
        joined = " ".join(sorted(ws))
        close = difflib.get_close_matches(joined, index.keys(), n=2, cutoff=0.94)
        if len(close) == 1:
            lst = list({(m[0], m[1], m[2], m[3]): m for m in index[close[0]]}.values())
            if len({(m[0], m[1]) for m in lst}) == 1:
                matches = lst
    if not matches:
        return None
    uniq = {(m[0], m[1]) for m in matches}
    if len(uniq) == 1:
        return matches[0]
    exact = [m for m in matches if m[0].upper() == r["office"].upper()
             and m[1].upper() == (r["district"] or "").upper()]
    if len({(m[0], m[1]) for m in exact}) == 1:
        return exact[0]
    same_party = [m for m in matches if m[2] == r["party"]]
    if same_party and len({(m[0], m[1]) for m in same_party}) == 1:
        return same_party[0]
    return None


def repair_office_pass(rows, vocab):
    fixed = 0
    for r in rows:
        comp = compress(r["office"]) + compress(r.get("district") or "")
        if not comp:
            continue
        hit = vocab.get(comp)
        if hit and (compress(r["office"]) != compress(hit[0]) or
                    compress(r.get("district") or "") != compress(hit[1])):
            r["office"], r["district"] = hit[0], hit[1]
            fixed += 1
            continue
        for comp_base, (office, district) in vocab.items():
            if comp.startswith(comp_base) and len(comp) > len(comp_base):
                tail = comp[len(comp_base):]
                if JUNK_TAIL.match(tail):
                    r["office"], r["district"] = office, district
                    if "REPUBLICAN" in r["office"].upper():
                        r["party"] = "REP"
                    elif "DEMOCRATIC" in r["office"].upper():
                        r["party"] = "DEM"
                    fixed += 1
                    break
    return fixed


def main():
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        return
    baseline = load_county_baseline()
    index = defaultdict(list)
    index_compact = defaultdict(list)
    vocab = {}
    for (county, office, district, party, cand), _v in baseline.items():
        index[" ".join(sorted(words(cand)))].append((office, district, party, cand))
        index_compact["".join(words(cand))].append((office, district, party, cand))
        vocab.setdefault(compress(office) + compress(district), (office, district))

    names_fixed = offices_fixed = ambiguous = 0
    for path in paths:
        with open(path) as fh:
            rows = list(csv.DictReader(fh))
            fieldnames = list(rows[0].keys()) if rows else []
        county = ((rows[0]["county"] or "").upper() if rows else "")
        # baseline's races for this county, and per-candidate baseline values
        race_set = {(k[1].upper(), (k[2] or "").upper()) for k in baseline if k[0] == county}
        # candidate-level sum within each (race, party, candidate-name) key
        cand_sums = defaultdict(int)
        for r in rows:
            k = (r["office"].upper(), (r["district"] or "").upper(),
                 (r["party"] or "").upper(), r["candidate"].upper())
            try:
                cand_sums[k] += int(float(str(r["votes"]).replace(",", "") or 0))
            except ValueError:
                pass
        out = []
        for r in rows:
            rkey = (r["office"].upper(), (r["district"] or "").upper())
            in_race_set = rkey in race_set and race_set is not None
            ws = words(r["candidate"])
            m = match_in(index, index_compact, r, ws)
            if m is None:
                out.append(r)
                continue
            if in_race_set and (m[0].upper(), (m[1] or "").upper()) == rkey:
                # race already right: fix only the name spelling/order
                newname = title_case_cand(m[3])
                if newname != r["candidate"]:
                    names_fixed += 1
                r = dict(r)
                r["candidate"] = newname
                if r["party"] in ("", "NON"):
                    r["party"] = m[2]
                out.append(r)
                continue
            if in_race_set:
                # different-office match inside the county: same-name in another
                # race (precinct chairs etc.) — leave the row's race alone
                out.append(r)
                continue
            # row's race is not in the baseline: office may be garbled; only
            # rewrite it when our sum for this candidate matches the baseline value
            k = (rkey[0], rkey[1], (r["party"] or "").upper(), r["candidate"].upper())
            our_sum = cand_sums.get(k)
            base_val = baseline.get((county, m[0], m[1], m[2], m[3]))
            if our_sum is None or base_val is None or our_sum != base_val:
                out.append(r)
                continue
            offices_fixed += 1
            r = dict(r)
            r["office"] = m[0]
            r["district"] = m[1]
            r["candidate"] = title_case_cand(m[3])
            if r["party"] in ("", "NON"):
                r["party"] = m[2]
            out.append(r)
            continue
        # rows with a blank office: take the nearest row (same county) that has
        # one — these are race-title fragments lost by the parser
        for i, r in enumerate(out):
            if not (r["office"] or "").strip():
                for span in range(1, 12):
                    for j in (i - span, i + span):
                        if 0 <= j < len(out) and (out[j]["office"] or "").strip()                                 and out[j]["precinct"] == r["precinct"]:
                            r["office"] = out[j]["office"]
                            if not (r["district"] or "").strip():
                                r["district"] = out[j]["district"]
                            break
                    if (r["office"] or "").strip():
                        break
        offices_fixed += repair_office_pass(out, vocab)
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
            w.writeheader()
            w.writerows(out)
    print(f"names fixed: {names_fixed}, offices fixed: {offices_fixed}")


if __name__ == "__main__":
    main()
