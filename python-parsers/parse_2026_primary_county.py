#!/usr/bin/env python3
"""
Parse the Texas Secretary of State "County by County Canvass Report" for the
2026 March 3 Republican primary into a county-level results CSV.

Source PDF: ~/code/openelections-sources-tx/2026/primary/CountyByCountyCanvassReport.pdf
Output:    2026/20260303__tx__primary__county.csv

Layout of the source PDF (discovered by inspection):
  * The report is a sequence of offices. Each office starts at the top of a page
    with an office title at the left margin (top ~= 128).
  * Each office has a PRIMARY section: a candidate header (one row of "[R]" party
    markers with candidate names stacked above them) plus a "County" label, then
    one row per county (county name + per-candidate vote columns + a "Total"
    column), ending with a "TOTAL VOTES" row. For statewide races the primary
    section spans many pages (county continuation); each continuation page
    repeats the candidate header + "County" label + more county rows.
  * When a race has too many candidates to fit across one page width, additional
    OVERFLOW sections follow the primary section. An overflow section has its own
    candidate header (NO "County" label) and repeats the SAME counties in the SAME
    order (no county names printed), ending with an unlabeled TOTAL row. Overflow
    sections start at the bottom of a page and continue onto subsequent pages
    (each repeating the overflow candidate header).
  * Propositions have no "[R]" party markers; they are skipped (no candidate
    parties). Pages with no party markers produce no output.

We parse by:
  1. Splitting each page into "blocks" delimited by candidate-header marker rows.
  2. Tracking the current office via the office title (pattern matched).
  3. Grouping consecutive same-signature blocks into sections per office
     (first section = primary, which carries county names; rest = overflows).
  4. Using the primary section's ordered county list to assign overflow votes
     positionally, skipping each section's TOTAL row.
"""

import csv
import os
import re
import sys

from natural_pdf import PDF

# The Republican and Democratic County by County Canvass Report PDFs. Both use
# the same layout; the party is read from each column's '[R]'/'[D]' marker, so a
# single pass over each PDF yields REP and DEM rows that are combined here into
# one statewide primary county-level file.
SOURCES = [
    os.path.expanduser(
        "~/code/openelections-sources-tx/2026/primary/CountyByCountyCanvassReport.pdf"
    ),
    os.path.expanduser(
        "~/code/openelections-sources-tx/2026/primary/CountyByCountyCanvassReport-DEM.pdf"
    ),
]
DST = "2026/20260303__tx__primary__county.csv"

BANNER = {
    "Texas Secretary of State",
    "County by County Canvass Report",
    "March 03, 2026",
    "March",
}
LABEL_TEXTS = {"County", "Votes", "Total", "TOTAL VOTES", "Total Votes"}

PARTY_MAP = {"R": "REP", "D": "DEM", "L": "LIB", "G": "GRN", "I": "IND", "N": "NON"}

# When set (e.g. via the JOIN_LOG env var), every mid-word rejoin is recorded
# here so the caller can audit them for false positives.
JOIN_LOG = []


def is_num(t):
    return bool(re.fullmatch(r"[\d,]+", t.strip()))


def party_code(marker_text):
    m = re.match(r"\s*\[([A-Za-z]+)\]", marker_text)
    if not m:
        return "NA"
    code = m.group(1).upper()
    return PARTY_MAP.get(code, code)


def district_num(s):
    """Extract a district number from a title, tolerating mid-word splits
    like 'DI STRICT 21' produced when a title element wraps."""
    m = re.search(r"(?:DISTRICT|STRICT)\s*[,.]?\s*(\d+)", s, re.I)
    return m.group(1) if m else None


def place_num(s):
    m = re.search(r"PLACE\s*(\d+)", s, re.I)
    return ("Place " + m.group(1)) if m else None


def title_case_office(t):
    """Title-case an office title for non-normalized offices, keeping
    ordinal suffixes lowercase (477TH -> 477th) and 'U.S.' intact."""

    def fix(w):
        w = w.strip(",")
        if w.upper() in ("U.S.", "U.S"):
            return "U.S."
        if re.fullmatch(r"\d+(ST|ND|RD|TH)", w, re.I):
            return w.lower()
        if w.upper() == "I":
            return "I"
        return w.capitalize()

    # Preserve commas after the preceding word.
    parts = t.split()
    return " ".join(fix(w) for w in parts)


def normalize_office(title):
    """Return (office, district) or None if the title is not a recognized office
    (e.g. candidate-name fragments that leaked into the title band)."""
    t = title.strip()
    if not t:
        return None
    u = t.upper()

    # Per the data convention for this file, offices without a district value
    # carry a blank district rather than "NA".
    if u == "U. S. SENATOR":
        return ("U.S. Senate", "")
    if re.search(r"U\.?\s*S\.?\s*REPRESENTATIVE", u):
        return ("U.S. House", district_num(u) or "")
    if u == "GOVERNOR":
        return ("Governor", "")
    if u == "LIEUTENANT GOVERNOR":
        return ("Lieutenant Governor", "")
    if u == "ATTORNEY GENERAL":
        return ("Attorney General", "")
    if u == "COMPTROLLER OF PUBLIC ACCOUNTS":
        return ("Comptroller", "")
    if u == "COMMISSIONER OF THE GENERAL LAND OFFICE":
        return ("Land Commissioner", "")
    if u == "COMMISSIONER OF AGRICULTURE":
        return ("Commissioner of Agriculture", "")
    if u.startswith("RAILROAD COMMISSIONER"):
        return ("Railroad Commissioner", "")
    if "SUPREME COURT" in u:
        return ("Supreme Court", place_num(u) or ("Chief" if "CHIEF" in u else ""))
    if "COURT OF CRIMINAL APPEALS" in u:
        return ("Court of Criminal Appeals", place_num(u) or "")
    if "STATE BOARD OF EDUCATION" in u:
        return ("State Board of Education", district_num(u) or "")
    if re.search(r"STATE\s+SENATOR", u):
        return ("State Senate", district_num(u) or "")
    if re.search(r"STATE\s+REPRESENTATIVE", u):
        return ("State House", district_num(u) or "")
    if re.search(r"PROPOSITION", u):
        return None  # propositions have no candidate parties; skip
    # Judicial / district-attorney / county-court offices: include with a
    # title-cased name (not in the normalized set the task specifies).
    # Judicial / district-attorney / county-court offices: include with a
    # title-cased name (not in the normalized set the task specifies).
    # Whole-word matching so "COURT" doesn't match inside "COURTNEY" (a
    # candidate first name that leaks into the title band on overflow pages).
    if re.search(r"\b(JUDGE|ATTORNEY|COURT|MULTICOUNTY|JUSTICE|CHIEF)\b", u):
        return (title_case_office(t), "")
    return None


# --------------------------------------------------------------------------
# Block extraction
# --------------------------------------------------------------------------


def clean_elements(page):
    out = []
    for e in page.find_all("text"):
        t = e.text.strip()
        if not t:
            continue
        if t in BANNER:
            continue
        if "REPUBLICAN PRIMARY" in t:
            continue
        if t.startswith("Page ") or "2026-08-" in t:
            continue
        out.append(e)
    return out


def cluster_markers(els):
    """Group party-marker elements (text starts with '[') into header clusters
    by vertical proximity. Markers in one header can sit at slightly different y
    (candidate names that wrap push their [R] down a line)."""
    markers = sorted((e for e in els if e.text.strip().startswith("[")), key=lambda e: e.top)
    clusters = []
    for m in markers:
        if clusters and m.top - clusters[-1][-1].top <= 22:
            clusters[-1].append(m)
        else:
            clusters.append([m])
    return clusters


def column_defs(cluster):
    """Return list of {'x','party','cx'} for a marker cluster, deduped by x.

    'x' is the marker's left edge (used for nearest-column assignment and for
    interior/last-column boundaries, which are tuned to it). 'cx' is the marker
    center, used for the single-column right boundary so it lands on the actual
    text-wrap edge rather than well short of it."""
    cols = []
    for m in sorted(cluster, key=lambda e: e.x0):
        x = round(m.x0)
        if cols and abs(x - cols[-1]["x"]) < 8:
            continue
        cols.append({"x": x, "cx": round((m.x0 + m.x1) / 2), "party": party_code(m.text)})
    return cols


def name_fragments(cluster_top, els, exclude):
    """Text fragments that form candidate names for a header at `cluster_top`:
    non-numeric, non-label, non-marker, non-title, within the name band above
    and around the markers."""
    lo = cluster_top - 72
    hi = cluster_top + 20
    frags = []
    for e in els:
        if e in exclude:
            continue
        t = e.text.strip()
        if not (lo <= e.top <= hi):
            continue
        if t.startswith("["):
            continue
        if t in LABEL_TEXTS:
            continue
        if is_num(t):
            continue
        frags.append(e)
    return frags


class Frag:
    """A lightweight text fragment with the position attributes the joiner needs,
    used when we split a multi-word text element into its constituent words."""

    __slots__ = ("text", "x0", "x1", "top")

    def __init__(self, text, x0, x1, top):
        self.text = text
        self.x0 = x0
        self.x1 = x1
        self.top = top


def element_word_frags(e):
    """Split a text element into per-word fragments at intra-line space gaps.

    pdfplumber sometimes groups two candidates' surname fragments that sit on
    the same line into a single text element (e.g. 'HERNANDE SCHWERTN' spanning
    two columns). Splitting at the space gap recovers the individual words with
    their own x positions so each lands in its correct candidate column. A
    single-word element, or one whose words all belong to the same column, is
    returned as one fragment so normal single-column names are unaffected.
    """
    try:
        chars = list(e.chars)
    except Exception:
        chars = []
    if not chars:
        return [e]
    groups = [[chars[0]]]
    for prev, c in zip(chars, chars[1:]):
        if c.x0 - prev.x1 > 1.5:  # space gap between words
            groups.append([c])
        else:
            groups[-1].append(c)
    words = [
        Frag("".join(c.text for c in g), g[0].x0, g[-1].x1, g[0].top)
        for g in groups
    ]
    return words if len(words) > 1 else [e]


def assign_to_columns(frags, cols):
    """Assign each fragment to its nearest candidate column; within a column
    sort fragments top-to-bottom and join into a name.

    A candidate name that is too long for its column wraps onto a second line.
    When the wrap happens *mid-word* (the PDF could not fit the whole word), the
    fragment on the upper line runs right up to (and slightly past) the column
    boundary -- the halfway point between adjacent party markers. We detect
    that and join the continuation *without* a space, so 'BIERSCHW' + 'ALE'
    becomes 'BIERSCHWALE' rather than 'BIERSCHW ALE'. A wrap at a real word
    boundary leaves the upper fragment short of the boundary, so we join with a
    space as normal ('VIRGIL' + 'JOHN' -> 'VIRGIL JOHN')."""
    by_col = {i: [] for i in range(len(cols))}

    def nearest(x):
        return min(range(len(cols)), key=lambda i: abs(x - cols[i]["x"]))

    for f in frags:
        words = element_word_frags(f)
        col_ids = [nearest(w.x0) for w in words]
        if len(set(col_ids)) <= 1:
            # All words belong to one column -- keep the element intact so a
            # normal multi-word name ('DE LA CRUZ', 'DANIEL W.') is not split.
            by_col[col_ids[0] if col_ids else nearest(f.x0)].append(f)
        else:
            # The element spans columns -- distribute the words individually.
            for w, ci in zip(words, col_ids):
                by_col[ci].append(w)
    names = []
    for i in range(len(cols)):
        parts = sorted(by_col[i], key=lambda e: (e.top, e.x0))
        # Right boundary of this column: halfway to the next party marker. For
        # the last column there is no next marker, so its right edge sits one
        # half-pitch past the last marker -- the same half-spacing an interior
        # column gets on its right side. (Using the full pitch here would place
        # the boundary far past the actual text-wrap edge, so mid-word wraps in
        # the last column would read as non-overflowing and go unrejoined.)
        if i + 1 < len(cols):
            boundary = (cols[i]["x"] + cols[i + 1]["x"]) / 2.0
        elif i > 0:
            boundary = cols[i]["x"] + (cols[i]["x"] - cols[i - 1]["x"]) / 2.0
        else:
            # Single candidate column: the only thing to its right is the Total
            # column, whose divider sits one half-pitch past the marker. Using the
            # marker *center* (not its left edge) here places the boundary on the
            # actual text-wrap edge; using the left edge would leave it ~14px
            # short, so a complete word that fills the column ('J. SCOTT') would
            # read as overflowing and wrongly merge with the next line ('NOVY').
            boundary = cols[i]["cx"] + 30
        nm = ""
        prev_x1 = None
        for f in parts:
            t = f.text.strip()
            if nm == "":
                nm = t
            else:
                last_tok = nm.rsplit(" ", 1)[-1]
                first_elem = " " not in nm
                # Rejoin a mid-word wrap (no space) only when the evidence is
                # strong. The upper fragment overflowed the column boundary
                # (reach >= 2) and the continuation is a short tail (<= 4 chars).
                # We do NOT rejoin when:
                #   * the continuation's first word is an initial ('T.', 'J.R.') --
                #     that is its own token, not a word tail. We only look at the
                #     first word so a tail like 'R' inside 'R Z.' (middle initials
                #     on the same element) still rejoins to 'ALEXANDE';
                #   * the upper name ends in a lone initial ('B', 'B.', 'R') --
                #     the continuation is then a separate surname word;
                #   * the upper fragment is the first (only) token so far *and* the
                #     continuation's first word is longer than one character -- a
                #     first name that overflowed a narrow column is followed by the
                #     surname, not a word tail. A single-char tail is allowed so that
                #     a wrapped first name ('ALEXANDE' + 'R') still rejoins. We test
                #     the *first word* (not the whole element) because the tail may
                #     share a line with trailing middle initials ('R Z.'), making the
                #     element long while its leading tail 'R' is still one char.
                first_word = t.split()[0]
                reach = (prev_x1 - boundary) if prev_x1 is not None else None
                # A trailing hyphen on the upper fragment means a hyphenated name
                # wrapped at the hyphen ('GIBBS-' + 'WALKER' -> 'GIBBS-WALKER');
                # join without a space. Guard against the continuation being an
                # initial so 'GIBBS-' + 'A.' does not collapse to 'GIBBS-A.'. The
                # renderer sometimes leaves a space before the hyphen ('SAGREDO -');
                # drop it so the name is 'SAGREDO-HAMMOND', not 'SAGREDO -HAMMOND'.
                if (
                    last_tok.endswith("-")
                    and not re.match(r"[A-Za-z]\.", first_word)
                ):
                    if nm.endswith(" -"):
                        nm = nm[:-2] + "-"
                    rejoin = True
                else:
                    # Rejoin a mid-word wrap (no space) only when the evidence is
                    # strong. The upper fragment overflowed the column boundary
                    # (reach >= 2) and the continuation is a short tail (<= 4 chars).
                    # We do NOT rejoin when:
                    #   * the continuation's first word is an initial ('T.', 'J.R.') --
                    #     that is its own token, not a word tail. We only look at the
                    #     first word so a tail like 'R' inside 'R Z.' (middle initials
                    #     on the same element) still rejoins to 'ALEXANDE';
                    #   * the upper name ends in a lone initial ('B', 'B.', 'R') --
                    #     the continuation is then a separate surname word;
                    #   * the upper fragment is the first (only) token so far *and* the
                    #     continuation's first word is longer than one character -- a
                    #     first name that overflowed a narrow column is followed by the
                    #     surname, not a word tail. A single-char tail is allowed so
                    #     that a wrapped first name ('ALEXANDE' + 'R') still rejoins.
                    #     We test the *first word* (not the whole element) because the
                    #     tail may share a line with trailing middle initials ('R Z.'),
                    #     making the element long while its leading tail 'R' is 1 char.
                    overflow_rejoin = (
                        reach is not None
                        and reach >= 2
                        and len(t) <= 4
                        and not re.match(r"[A-Za-z]\.", first_word)
                        and not re.fullmatch(r"[A-Za-z]\.?", last_tok)
                        and not (first_elem and len(first_word) != 1)
                    )
                    # Wide columns (single/few candidates) wrap differently: the
                    # upper fragment (a long surname/first-name fragment) fills the
                    # column and ends right at the wrap edge (reach ~ 0, slightly
                    # negative), and only a 1-2 char tail spills to the next line.
                    # The tail may share its line with trailing middle names
                    # ('ALEXANDRI' + 'A NICOLE', 'CONSTANC' + 'E FILLEY'), so -- like
                    # the overflow rule -- we test the *first word* length, not the
                    # whole element. The structural signal (long word fragment
                    # ending in a letter, followed by a tiny tail that is not an
                    # initial) is itself strong: a complete word is not followed by
                    # such a fragment and middle initials stay on the same line as
                    # the first name ('ERLEIGH N', 'JULIE C'). The letter-ending
                    # guard avoids suffixes ('BARKER,' + 'SR').
                    near_edge_rejoin = (
                        reach is not None
                        and reach >= -8
                        and len(first_word) <= 2
                        and len(t) <= 16
                        and len(last_tok) >= 5
                        and last_tok[-1].isalpha()
                        and not re.match(r"[A-Za-z]\.", first_word)
                        and not re.fullmatch(r"[A-Za-z]\.?", last_tok)
                        and not (first_elem and len(first_word) != 1)
                    )
                    rejoin = overflow_rejoin or near_edge_rejoin
                if rejoin:
                    JOIN_LOG.append((nm, t, round(prev_x1 - boundary, 1)))
                    nm += t
                else:
                    nm += " " + t
            prev_x1 = f.x1
        nm = nm.replace('"', "")  # strip quotes around nicknames like "GUS"
        nm = re.sub(r"\s+", " ", nm).strip()
        names.append(nm)
    return names


def extract_rows(data_els, cols):
    """Group data elements into rows (by y), parse each into
    (county_or_None, votes_list, total)."""
    if not data_els:
        return []
    data_els = sorted(data_els, key=lambda e: e.top)
    rows = []
    cur = []
    cur_y = None
    for e in data_els:
        y = round(e.top)
        if cur_y is None or abs(y - cur_y) <= 5:
            cur.append(e)
            cur_y = y if cur_y is None else cur_y
        else:
            rows.append(cur)
            cur = [e]
            cur_y = y
    if cur:
        rows.append(cur)

    min_x = cols[0]["x"]
    max_x = cols[-1]["x"]
    parsed = []
    for row in rows:
        county = None
        county_frags = []  # (x0, x1, text) of left-column, non-numeric pieces
        votes = [None] * len(cols)
        total = None
        for e in row:
            t = e.text.strip()
            if not is_num(t):
                # Left-column non-numeric text is the county name (or TOTAL VOTES).
                # A single county name can be split across adjacent text elements
                # (pdfplumber sometimes breaks 'HARRIS' into 'H' + 'ARRIS'), so
                # collect every piece and rejoin below.
                if e.x0 < min_x - 15:
                    county_frags.append((e.x0, e.x1, t))
                continue
            x = e.x0
            if x > max_x + 25:
                total = t
                continue
            # assign to nearest column within tolerance
            best_i = min(range(len(cols)), key=lambda i: abs(x - cols[i]["x"]))
            if abs(x - cols[best_i]["x"]) <= 30:
                votes[best_i] = t
            elif x > max_x + 25:
                total = t
        # Rejoin the county-name fragments: no space where they are contiguous
        # (a mid-word split: 'H'+'ARRIS' -> 'HARRIS', 'TOT'+'AL VOTES' ->
        # 'TOTAL VOTES'), a space where there is a gap ('VAN'+'ZANDT' ->
        # 'VAN ZANDT').
        if county_frags:
            county_frags.sort(key=lambda f: f[0])
            county = county_frags[0][2]
            prev_x1 = county_frags[0][1]
            for x0, x1, txt in county_frags[1:]:
                if x0 - prev_x1 <= 1.5:
                    county += txt
                else:
                    county += " " + txt
                prev_x1 = x1
        parsed.append((county, votes, total))
    return parsed


def page_blocks(page):
    """Return list of block dicts for a page:
    {'top','cols','names','has_county','rows'}."""
    els = clean_elements(page)
    # Office title detection: elements in the title band [120,140].
    title_els = [e for e in els if 120 <= e.top <= 140]
    title_els.sort(key=lambda e: e.x0)
    title_text = " ".join(e.text.strip() for e in title_els)
    office = normalize_office(title_text)
    title_exclude = set(title_els) if office else set()

    clusters = cluster_markers(els)
    if not clusters:
        return office, []

    # Names per cluster (and their min top), for data-region boundaries.
    cluster_info = []
    for cluster in clusters:
        top = min(m.top for m in cluster)
        cols = column_defs(cluster)
        frags = name_fragments(top, els, title_exclude)
        names = assign_to_columns(frags, cols)
        cluster_info.append({"top": top, "cols": cols, "names": names})

    blocks = []
    for ci, info in enumerate(cluster_info):
        top = info["top"]
        cols = info["cols"]
        # data region: from just below markers to just before next cluster's names
        data_lo = top + 12
        if ci + 1 < len(cluster_info):
            next_top = cluster_info[ci + 1]["top"]
            # next cluster's names start ~ up to 72px above its markers
            data_hi = next_top - 75
        else:
            data_hi = 565  # above the footer
        data_els = [e for e in els if data_lo <= e.top <= data_hi]
        # has_county: a "County" label just above this cluster's markers
        has_county = any(
            e.text.strip() == "County" and (top - 25) <= e.top <= (top + 12)
            for e in els
        )
        rows = extract_rows(data_els, cols)
        blocks.append(
            {
                "top": top,
                "cols": cols,
                "names": info["names"],
                "has_county": has_county,
                "rows": rows,
            }
        )
    return office, blocks


def sig(cols):
    return tuple(round(c["x"] / 10.0) * 10 for c in cols)


# --------------------------------------------------------------------------
# Office assembly
# --------------------------------------------------------------------------


def assemble_offices(all_pages):
    """Iterate pages, track current office, group blocks into sections."""
    offices = []  # list of {'office','district','sections':[{'cols','names','rows','has_county'}]}
    cur = None
    for pidx, page in enumerate(all_pages):
        office, blocks = page_blocks(page)
        if office is not None:
            # finalize current office, start a new one
            if cur is not None:
                offices.append(cur)
            cur = {"office": office[0], "district": office[1], "sections": []}
            cur_section = None
        if cur is None:
            # blocks before any office title (shouldn't happen) -> skip
            continue
        for b in blocks:
            b_sig = sig(b["cols"])
            if cur_section is None or b_sig != cur_section["_sig"]:
                cur_section = {
                    "_sig": b_sig,
                    "cols": b["cols"],
                    "names": b["names"],
                    "has_county": b["has_county"],
                    "rows": list(b["rows"]),
                }
                cur["sections"].append(cur_section)
            else:
                cur_section["rows"].extend(b["rows"])
    if cur is not None:
        offices.append(cur)
    return offices


def emit_rows(offices):
    out = []
    for off in offices:
        office, district = off["office"], off["district"]
        if not off["sections"]:
            continue
        # primary section = the one with county labels (first).
        primary = None
        overflows = []
        for s in off["sections"]:
            if s["has_county"] and primary is None:
                primary = s
            else:
                overflows.append(s)
        if primary is None:
            # No primary (county-labeled) section; skip office.
            continue
        # counties from primary (exclude TOTAL VOTES rows)
        counties = []
        primary_votes = []  # per county: list aligned to primary cols
        for county, votes, total in primary["rows"]:
            if county and county.upper() == "TOTAL VOTES":
                continue
            if county is None:
                # primary row without a county name (shouldn't happen) -> skip
                continue
            counties.append(county)
            primary_votes.append(votes)
        n = len(counties)

        # Build candidate list = primary candidates + overflow candidates.
        cand_defs = []  # (name, party)
        for i, c in enumerate(primary["cols"]):
            cand_defs.append((primary["names"][i], c["party"]))
        # per-county vote matrix, starting with primary votes.
        matrix = [list(v) for v in primary_votes]

        for ov in overflows:
            ov_rows = ov["rows"]
            # take first n rows (counties), skip the rest (TOTAL row)
            for i in range(n):
                county, votes, total = ov_rows[i]
                matrix[i].extend(votes)
            for i, c in enumerate(ov["cols"]):
                cand_defs.append((ov["names"][i], c["party"]))

        for i, county in enumerate(counties):
            row_votes = matrix[i]
            for j, (cname, party) in enumerate(cand_defs):
                v = row_votes[j] if j < len(row_votes) else None
                if v is None:
                    continue
                votes = v.replace(",", "")
                if votes == "0" or votes == "":
                    # keep zero-vote rows too
                    pass
                out.append(
                    {
                        "county": county,
                        "office": office,
                        "district": district,
                        "party": party,
                        "candidate": cname,
                        "votes": votes,
                    }
                )
    return out


def main():
    rows = []
    for src in SOURCES:
        if not os.path.exists(src):
            sys.exit(f"Source PDF not found: {src}")
        print(f"Loading {src} ...", file=sys.stderr)
        pdf = PDF(src)
        print(f"  {len(pdf.pages)} pages", file=sys.stderr)
        offices = assemble_offices(pdf.pages)
        rows.extend(emit_rows(offices))

    os.makedirs(os.path.dirname(DST) or ".", exist_ok=True)
    with open(DST, "w", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["county", "office", "district", "party", "candidate", "votes"],
            lineterminator="\n",
        )
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"Wrote {len(rows)} rows to {DST}", file=sys.stderr)

    # Diagnostics
    from collections import Counter

    by_office = Counter(r["office"] for r in rows)
    print("\nRows per office:", file=sys.stderr)
    for k, v in sorted(by_office.items()):
        print(f"  {v:6d}  {k}", file=sys.stderr)

    if os.environ.get("JOIN_LOG"):
        print(f"\nMid-word rejoins ({len(JOIN_LOG)}):", file=sys.stderr)
        for nm, tail, reach in JOIN_LOG:
            print(f"  {nm} + {tail}  (reach {reach:+.1f})", file=sys.stderr)


if __name__ == "__main__":
    main()