"""Shared helpers for the 2026 March 3 primary precinct-level parsers.

The county-level baseline (2026/20260303__tx__primary__county.csv, built from the
Secretary of State County by County Canvass Reports) defines the office naming
conventions used here, so precinct sums can be aggregated and compared row for row.
"""

import csv
import os
import re

COUNT_YEAR_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "2026", "counties")

# Offices we normalize to the canonical titles used by the county-level file.
KNOWN_OFFICES = {
    "U.S. Senate": "",
    "Governor": "",
    "Lieutenant Governor": "",
    "Attorney General": "",
    "Comptroller": "",
    "Land Commissioner": "",
    "Commissioner of Agriculture": "",
    "Railroad Commissioner": "",
}

CAND_OFFICES = {
    "STATE SENATOR": "State Senate",
    "STATE REPRESENTATIVE": "State House",
    "STATE BOARD OF EDUCATION": "State Board of Education",
}

PARTY_MAP = {"R": "REP", "D": "DEM", "L": "LIB", "G": "GRN", "I": "IND", "N": "NON"}
PARTY_NORMAL = {
    "REP": "REP",
    "REPUBLICAN": "REP",
    "DEM": "DEM",
    "DEMOCRATIC": "DEM",
    "NON": "NON",
}

SUFFIX_RE = re.compile(r"\s*\((?:I|unexpired term)\)\s*$", re.I)


def district_from(title):
    m = re.search(r"DIST\w*(?:\s+NO\.?)?\s*(\d+)", title, re.I)
    if m:
        return m.group(1)
    m = re.search(r"\b(\d{1,3})(?:ST|ND|RD|TH)?\b\s*(?=.*COURT OF APPEALS)", title, re.I)
    if m:
        return m.group(1)
    return ""


def expand_abbrevs(t):
    """Expand the local-office abbreviations used by county report systems to the
    full forms used by the Secretary of State canvass (court of appeals districts
    etc.), so precinct rows and the county-level file can be joined by name."""
    t = re.sub(r"\bCT OF APP\b", "COURT OF APPEALS", t, flags=re.I)
    t = re.sub(r"\bCRT\b", "COURT", t, flags=re.I)
    t = re.sub(r"\bAPP\b\.?", "APPEALS", t, flags=re.I)
    t = re.sub(r"\bAPPLS\b", "APPEALS", t, flags=re.I)
    t = re.sub(r"\bCT\s+APPEALS\b", "COURT OF APPEALS", t, flags=re.I)
    t = re.sub(r"\bFAM\b\.?", "FAMILY", t, flags=re.I)
    t = re.sub(r"\bCT\s+CRIM(INAL)?\s+APP(EALS)?\b", "COURT OF CRIMINAL APPEALS", t, flags=re.I)
    t = re.sub(r"\bJ\s+DIST\b", "JUDICIAL DISTRICT", t, flags=re.I)
    t = re.sub(r"\bJUD\b\.?", "JUDICIAL", t, flags=re.I)
    t = re.sub(r"\bCT OF CRIM APP\b", "COURT OF CRIMINAL APPEALS", t, flags=re.I)
    t = re.sub(r"\bCOURT OF CRIM APP\b", "COURT OF CRIMINAL APPEALS", t, flags=re.I)
    t = re.sub(r"\bCOURT OF APP\b", "COURT OF APPEALS", t, flags=re.I)
    t = re.sub(r"\bCOURTS? OF APPEALS? DIST\b", "COURT OF APPEALS DISTRICT", t, flags=re.I)
    t = re.sub(r"\bCOURT OF APPEALS DIST\b", "COURT OF APPEALS DISTRICT", t, flags=re.I)
    t = re.sub(r"\bCT\b\.?", "COURT", t, flags=re.I)
    t = re.sub(r"\bPL\.?\s*(\d+)", r"PLACE \1", t, flags=re.I)
    t = re.sub(r"\bUNEXPIRED?\.?\b(\s+TERM)?\b", "UNEXPIRED TERM", t, flags=re.I)
    t = re.sub(r"\bBOE\b", "BOARD OF EDUCATION", t, flags=re.I)
    t = re.sub(r"\bDIST\b\.?", "DISTRICT", t, flags=re.I)
    t = re.sub(r"\bJOP\b", "JUSTICE OF THE PEACE", t, flags=re.I)
    t = re.sub(r"\bCOMM\b", "COMMISSIONER", t, flags=re.I)
    t = re.sub(r"GENERAL LAND( OFFICE)?", "COMMISSIONER OF THE GENERAL LAND OFFICE", t, flags=re.I)
    t = t.replace("COMMISSIONER COMMISSIONER", "COMMISSIONER")
    t = re.sub(r"\bREP\.?,?\s*DIS\.?\s*(\d+)", "REPRESENTATIVE DISTRICT \\1", t, flags=re.I)
    t = re.sub(r"\bSEN\.?\s*", "SENATE ", t, flags=re.I)
    t = re.sub(r"\bCRIM\b\.?", "CRIMINAL", t, flags=re.I)
    return t


def normalize_office(title, fallback_commas=True):
    """Return (office, district) for a race title, or None if unrecognized.

    Handles the Hart report style ('United States Representative, District No. 13 -
    Republican Party'), the Dominion style ('REP US Representative, District 3'),
    and the all-caps Dominion style ('(R) US SENATOR').
    """
    t = re.sub(r"\s+", " ", SUFFIX_RE.sub("", title.strip()))
    if not t:
        return None
    u = expand_abbrevs(t.upper())
    # drop leading party markers like 'REP ', 'DEM US Senator', '(R) US SENATOR'
    u = re.sub(r"^\(?[RDN]\)?\.?\s+(?=[A-Z])", "", u)
    u = re.sub(r"^(?:REPUB|REPUBLICAN|DEMO|DEMOCRATIC|NONPART|NONPARTISAN)[A-Z]*\s+", "", u)
    # drop trailing qualifiers
    u = re.sub(r"\s*-\s*(?:VOTE FOR|REP|DEM).*$", "", u)
    u = re.sub(r"\s+VOTE FOR.*$", "", u, flags=re.I)
    u = re.sub(r"NONE OR ONE$", "", u).strip()
    u = SUFFIX_RE.sub("", u).strip()

    # Courts of appeals: the county-level file keeps the place in the office text
    m = re.match(
        r"(CHIEF )?JUSTICE,?\s*(\d+)(ST|ND|RD|TH)?\s+COURT OF APPEALS DISTRICT"
        r"[,.]?\s*(?:PLACE|PL\.?|P)\s*(\d+)(.*)$", u)
    if m:
        suffix = " - Unexpired Term" if "UNEXPIRED" in m.group(5).upper() else ""
        suffix_ord = (m.group(3) or "").lower()
        who = "Chief Justice" if m.group(1) else "Justice"
        name = (f"{who} {m.group(2)}{suffix_ord} Court Of Appeals District "
                f"Place {m.group(4)}{suffix}")
        return (name, "")
    m = re.match(
        r"(CHIEF )?JUSTICE,?\s*(\d+)(ST|ND|RD|TH)?\s+COURT OF APPEALS DISTRICT", u)
    if m:
        who = "Chief Justice" if m.group(1) else "Justice"
        suffix_ord = (m.group(3) or "").lower()
        name = f"{who} {m.group(2)}{suffix_ord} Court Of Appeals District"
        return name, ""

    if re.search(r"(?:U\.?\s*S\.?\s*|UNITED\s+STATES\s+)SENAT", u) or re.search(r"US SENAT", u):
        return ("U.S. Senate", "")
    if re.search(r"(?:U\.?\s*S\.?\s*|UNITED\s+STATES\s+)REPRESENTATIVE", u) or re.search(r"US REPRESENTATIVE", u):
        return ("U.S. House", district_from(u))
    if u.startswith("GOVERNOR"):
        return ("Governor", "")
    if u.startswith("LIEUTENANT GOVERNOR"):
        return ("Lieutenant Governor", "")
    if u.startswith("ATTORNEY GENERAL"):
        return ("Attorney General", "")
    if re.search(r"COMMISSIONER.*GENERAL.*LAND", u):
        return ("Land Commissioner", "")
    if u.startswith("COMPTROLLER"):
        return ("Comptroller", "")
    if u.startswith("COMMISSIONER OF THE GENERAL LAND OFFICE"):
        return ("Land Commissioner", "")
    if u.startswith("COMMISSIONER OF AGRICULTURE"):
        return ("Commissioner of Agriculture", "")
    if u.startswith("RAILROAD COMMISSION"):
        return ("Railroad Commissioner", "")
    if "SUPREME COURT" in u:
        if "CHIEF" in u:
            return ("Supreme Court", "Chief")
        m = re.search(r"(?:\bPLACE|PL\.?|P)\s*(\d+)", u, re.I)
        return ("Supreme Court", "Place " + m.group(1) if m else "")
    if "COURT OF CRIMINAL APPEALS" in u:
        m = re.search(r"(?:\bPLACE|PL\.?|P)\s*(\d+)", u, re.I)
        return ("Court of Criminal Appeals", "Place " + m.group(1) if m else "")
    if "STATE BOARD OF EDUCATION" in u:
        return ("State Board of Education", district_from(u))
    if re.search(r"\bSTATE\s*SENAT", u):
        return ("State Senate", district_from(u))
    if re.search(r"\bSTATE\s*REPRESENTATIVE", u):
        return ("State House", district_from(u))
    # Everything else (courts of appeals, district judges, county offices, props):
    # keep the title as-is, title-cased, with the district in the office text
    # (matching the county-level file's conventions). Commas collapse to spaces:
    # 'Judge, 253rd Judicial District' -> 'Judge 253rd Judicial District'.
    t = re.sub(r"\s*,\s*", " ", t.strip())
    t = t.replace("#", " ")
    return (title_case_office(expand_abbrevs(t)), "")


def title_case_office(t):
    t = re.sub(r"\s+", " ", t.strip()).strip()
    t = re.sub(r",\s*", ", ", t)
    words = t.split(" ")
    out = []
    for w in words:
        if not w:
            continue
        if w.upper() in ("U.S.", "U.S"):
            out.append("U.S.")
            continue
        m = re.fullmatch(r"(\d+)(ST|ND|RD|TH)", w, re.I)
        if m:
            out.append(m.group(1) + m.group(2).lower())
            continue
        if re.fullmatch(r"\d+", w):
            out.append(w)
            continue
        out.append(w.capitalize())
    s = " ".join(out)
    s = s.replace(", ", ", ")
    s = re.sub(r",\s*$", "", s)
    s = re.sub(r"(?<![A-Za-z])[Nn]o\.?(?![A-Za-z])", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def clean_candidate(name):
    """Clean a candidate name: strip party tokens (McLennan style 'James Talarico
    DEM'), trailing whitespace, internal quote marks kept as-is."""
    name = re.sub(r"\s*\b(DEM|REP|LIB|GRN|IND|CON|NPA)\b.?$", "", name.strip(), flags=re.I)
    name = re.sub(r"\s+", " ", name).strip(" ,-")
    return name


def precinct_name(raw):
    """Normalize a precinct label: drop a 'PCT ' / 'PRECINCT' prefix and leading
    zeros on a leading numeric segment (005 -> 5)."""
    raw = raw.strip()
    raw = re.sub(r"^(?:precinct|pct|box)\s*\.?\s*", "", raw, flags=re.I)
    raw = raw.strip("-, .:")
    if re.fullmatch(r"\d+", raw):
        raw = raw.lstrip("0") or "0"
    elif re.match(r"0*[\w-]", raw):  # zero-pad only a leading numeric segment
        raw = re.sub(r"^0+(\d)", r"\1", raw)
    return raw


def write_county_csv(out_path, county, rows, fieldnames):
    """Write one county's precinct rows. rows: list of dicts with the fieldnames."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            rec = {k: r.get(k, "") for k in fieldnames}
            rec["county"] = county
            w.writerow(rec)


def key_norm(office, district, party, candidate):
    return (
        office.upper().replace(" ", " "),
        district.upper(),
        PARTY_NORMAL.get(party.upper(), party.upper()),
        candidate.upper().replace('"', "").replace("'", "").strip(),
    )


def load_county_baseline(path=None):
    """Load the county-level file: {(county, office, district, party, cand): votes}."""
    if path is None:
        path = os.path.join(os.path.dirname(__file__), os.pardir, "2026",
                            "20260303__tx__primary__county.csv")
    base = {}
    with open(path) as fh:
        for r in csv.DictReader(fh):
            base[(r["county"], r["office"], r["district"], r["party"], r["candidate"])] = int(
                r["votes"].replace(",", "")
            )
    return base