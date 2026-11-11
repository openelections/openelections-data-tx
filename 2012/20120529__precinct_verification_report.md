# May 29, 2012 primary — precinct-level conversion and verification report

Generated 2026-11-10. Sources: `openelections-sources-tx/2012/primary/`; baseline: `2012/20120529__tx__primary__county.csv`.

## Wide/pivoted spreadsheet group (final pass)

`python-parsers/parse_2012_wide.py` has six layout kinds (candidate_rows,
fixed_cols, narrow, named_cols, transposed) plus baseline-driven office
repair that falls back to surname / first-token / truncation-tolerant and
one-edit surname matching, all party-scoped and office-scoped when the row's
raw office text resolves.

Converted and committed in this group:
* **bowie** — REP sums match the canvass; DEM export lacks early-vote data
  (every Dem sum falls ~460 short of the canvass).
* **hockley** — COMBINED sheet; source mis-enters Huntsman's precinct-16 cell
  as 96; two -1 diffs.
* **hansford** — REP-only source; per-precinct cells internally incomplete
  (row totals equal the canvass).
* **parker** — Hart-template narrow, 3969 rows, **fully verified** (0 diffs).
* **mcmullen** — one DEM + one REP file each carrying EV (per precinct) and
  ED sheets; 9 residual diffs: some EV-file rows lost to truncated/typo'd
  names, County Chair Rostig contest absent from the export (50 votes),
  scattered ±1s.
* **oldham** — truncated candidate names; 1 residual diff: Romney +10 (the
  sheet's EARLY column overlaps its own precinct columns in that row; both
  the sheet TOTAL and the canvass say 176).
* **concho** (REP) — hart narrow template; full DEM side (DEM csv is a text
  file for the text group).
* **oldham/panola/concho/willacy** are single-party (`republican__`-prefixed):
  panola's DEM source is a mail-ballot log with no results; willacy's DEM
  side is a mislabeled PDF; their REP content verifies.

All 13 leftover wide counties are now converted (final pass added the
`typed_rows` kind for childress, TOTAL-table gating for brewster's stacked
Early/Election/TOTAL grids, a report-total column exclusion for cass, and
baseline-driven office/name repair that is office-scoped and
typo-tolerant — covering terrell's surname-only lists ('Rodriquez',
'Buchamante', 'Uresh') and county-wide early-vote columns (panola/oldham,
emitted as `Absentee` pseudo-precinct rows)):

* **terrell** (`democratic__`) — hart-template DEM xlsx; name repair resolved
  the surname-only/typo'd candidates. The file contains DEM races only: the
  5 missing offices + REP diffs are the absent REP side (no REP machine
  source). District Judge 63 'Enrique' is the SOS spelling (export spelled
  it Fernandez) — reconciled by an office-scoped name fix.
* **brewster** (`democratic__`) — transposed grids (four sheets: candidates
  across columns, first/last name split over two lines, three stacked
  Early/Election/TOTAL tables of which the TOTAL table is used). DEM file
  only; the 6 missing offices + REP diffs are the absent REP side. One DEM
  residual: Addie Dainell Allen -3 vs the canvass.
* **cass** (`republican__`) — EARLY/GRAND/TOTALS sheets, TOTALS used with the
  report-total column excluded. 20 REP diffs are ±0-2 (and Davis/Huntsman
  gaps); DEM side has no source in the repo (14 DEM candidate gaps).
* **childress** — Type-row sheets (Early/Election rows per candidate,
  summed). 8 documented diffs: the export omits State Rep 68 (Odom) and
  SBOE 15 (Schafersman) and disagrees with the canvass on Cleaver
  (21 vs 3), Duncan (533 vs 577), Hervey (-10) and scattered ±1s.

County-wide early-vote totals that cannot be split by precinct (panola EV
column, oldham EARLY column) are emitted as `Absentee` pseudo-precinct rows,
which makes candidate sums tie with the canvass except where noted.

## What was done

* **115 county precinct files written** with the filename base `20120529__tx__primary`. 105 counties cover both parties; 10 (`democratic__`/`republican__`-prefixed) cover a single party because the county's other party is only available as PDF/other formats (e.g. McCulloch, Medina, Sherman, Washington).
* ASC/Hart-export counties parsed with `python-parsers/parse_2012_asc.py` (180-char record layout; `.001` Hart exports and Calhoun's EL30A `.LST` text report included).
* Excel counties parsed with `python-parsers/parse_2012_excel.py` (wraps the 2014 Detail-Vote-Totals parser; adds the 2012 quirks listed below).
* Every file was verified against the county-level file: per-candidate precinct sums are compared to the SOS county canvass (candidate rows are authoritative; the baseline's `Total` rows are advisory). Office names are matched on canonical keys; the 2012 propositions are checked for coverage only.
* All written CSVs pass the openelections-data-tests suites (re-checked after each pass) (`duplicate_entries`, `file_format`, `missing_values`, `vote_breakdown_totals`, harness v2.2.0).

## Verification result summary

* Clean (no candidate mismatches, no missing offices): **17** of 115 counties
* Small diffs (each mismatch ±1 vote, no missing offices): **17** counties
* Notable mismatches remain: **81** counties (counts per county below) — see the JSON report `2012/20120529__report.json` for office-by-office detail.

Clean: colorado, coryell, dewitt, eastland, falls, hopkins, madison, mitchell, montgomery, nacogdoches, nolan, orange, san_jacinto, stonewall, upshur, wheeler, young

## Source defects found (files excluded or partially usable)

| County | Source | Problem |
|---|---|---|
| Tyler | `12PTYLER.ASC` (both parties) | every vote field in the export is 0; no results recoverable — file skipped |
| Fayette | `10GFAYET.ASC` | mislabeled: the export is the **2010 general election**, not the 2012 primary — file skipped |
| Chambers | `AEROLST.WRK` | EL45A summary (county totals) only; no precinct breakdown — skipped |
| Lamb | `12PLAMB.ALG`; Webb `12PWEBB.CVS` | Hart report-definition binaries, no results data — skipped |
| Bandera | Bandera sources are the 2011 amendment election (`2011_Constitutional_Amendment`); the 2012 primary files are absentee-only `EPB_ABSENTEE.csv` — not precinct-level |

## Documented source-vs-canvass discrepancies

* **Wharton**: the county exports (`12PWHART.001`) carry only a fraction of the contests (19 of ~20 offices missing).
* **Cameron**: exports omit the 13th Court of Appeals places and District Judge courts 138/404/444/445 entirely.
* **Smith**: exports omit the Criminal District Judge races (courts 7 and 114).
* **Victoria / Hood / parts of Wharton**: Hart title fields are truncated at 56 characters, which cuts the Place numbers off Court of Appeals / CCA judge races; those races are written with an empty district and are candidates under a single office. The votes are present but the place disambiguation cannot be recovered from the export alone.
* **Bexar**: the county's exports (both parties) run consistently **+5 or so votes over** the SOS county canvass; all Dem/Rep statewide candidates show the same excess.
* **Widespread small diffs**: dozens of counties show a small number of candidates whose precinct sums differ from the SOS canvass by exactly ±1 (93 occurrences across the ASC group alone). Direction and magnitude suggest a single provisional/late ballot in the canvass absent from the county's exports; the export values are kept as parsed.
* **Typos recovered by aliases** (kept in the outputs, mapped for verification): `Raplh M. Hall` (Morris), `Tawana L. Cadien` (Austin; SOS file says W.), `John Grunwold` (Calhoun), `Elizabeth Murray-Kolb` / `MurrayKolb` spelling variants.

## PDF text-layer group (final pass): `parse_2012_pdf.py` parses the
'Precinct Report' text-layer PDFs via `pdftotext`, with a raw-mode fallback
for wrapped tables (cherokee's RR Unexpired race) and an 'Unexpired Term'
marker. Converted & committed: **bee, cherokee, coke, gray, jack,
jim_wells, denton** (both parties; denton's dash-form office names
'District Judge - 16th District Court' canonicalized) and **willacy**
(DEM pdf; its Republican side was already committed from the REP totals
xlsx). Residual documented diffs vs the canvass: bee's CoA/CCA candidates
run ~105 votes short of the canvass (bee export covers 16 of 17 precincts),
denton misses rows on some wrapped pages (11 diffs incl. 10,000-vote
Shipman discrepancy — 24703 vs 14703), willacy differs on CCA/CoA/Unexpired
(REP side absent from the DEM export). Data tests pass.

Still uncommitted: **jim_hogg** and **llano**. `parse_2012_canvass.py` now
parses both canvasses with the two-phase approach (race titles, fixed
columns, rotated candidate name columns clustered by x-overlap, and data
values mapped by character position to the nearest name column): it emits
~495 llano rows and ~135 jim_hogg rows, but the rotated name columns whose
candidate headers interleave with the 'Ballots/Cast' subheader lines (e.g.
llano's DEM President block, jim_hogg's Justice 4th CoA blocks) still lose
rows (Obama-style columns with names on multiple wrapped lines), and
llano's Railroad Commissioner Unexpired block and jim_hogg's Justice 4th
CoA/CCA-7-8/Supreme 2-4 races are absent. Next pass: handle the interleaved
subheader lines per candidate column (names whose x range intersects a
subheader's y-range belong on a separate 'row' of the header band).

County-wide early-vote totals that cannot be split by precinct (panola EV
column, oldham EARLY column) are emitted as `Absentee` pseudo-precinct rows,
which makes candidate sums tie with the canvass except where noted.

## What was done

* **115 county precinct files written** with the filename base `20120529__tx__primary`. 105 counties cover both parties; 10 (`democratic__`/`republican__`-prefixed) cover a single party because the county's other party is only available as PDF/other formats (e.g. McCulloch, Medina, Sherman, Washington).
* ASC/Hart-export counties parsed with `python-parsers/parse_2012_asc.py` (180-char record layout; `.001` Hart exports and Calhoun's EL30A `.LST` text report included).
* Excel counties parsed with `python-parsers/parse_2012_excel.py` (wraps the 2014 Detail-Vote-Totals parser; adds the 2012 quirks listed below).
* Every file was verified against the county-level file: per-candidate precinct sums are compared to the SOS county canvass (candidate rows are authoritative; the baseline's `Total` rows are advisory). Office names are matched on canonical keys; the 2012 propositions are checked for coverage only.
* All written CSVs pass the openelections-data-tests suites (re-checked after each pass) (`duplicate_entries`, `file_format`, `missing_values`, `vote_breakdown_totals`, harness v2.2.0).

## Verification result summary

* Clean (no candidate mismatches, no missing offices): **17** of 115 counties
* Small diffs (each mismatch ±1 vote, no missing offices): **17** counties
* Notable mismatches remain: **81** counties (counts per county below) — see the JSON report `2012/20120529__report.json` for office-by-office detail.

Clean: colorado, coryell, dewitt, eastland, falls, hopkins, madison, mitchell, montgomery, nacogdoches, nolan, orange, san_jacinto, stonewall, upshur, wheeler, young

## Source defects found (files excluded or partially usable)

| County | Source | Problem |
|---|---|---|
| Tyler | `12PTYLER.ASC` (both parties) | every vote field in the export is 0; no results recoverable — file skipped |
| Fayette | `10GFAYET.ASC` | mislabeled: the export is the **2010 general election**, not the 2012 primary — file skipped |
| Chambers | `AEROLST.WRK` | EL45A summary (county totals) only; no precinct breakdown — skipped |
| Lamb | `12PLAMB.ALG`; Webb `12PWEBB.CVS` | Hart report-definition binaries, no results data — skipped |
| Bandera | Bandera sources are the 2011 amendment election (`2011_Constitutional_Amendment`); the 2012 primary files are absentee-only `EPB_ABSENTEE.csv` — not precinct-level |

## Documented source-vs-canvass discrepancies

* **Wharton**: the county exports (`12PWHART.001`) carry only a fraction of the contests (19 of ~20 offices missing).
* **Cameron**: exports omit the 13th Court of Appeals places and District Judge courts 138/404/444/445 entirely.
* **Smith**: exports omit the Criminal District Judge races (courts 7 and 114).
* **Victoria / Hood / parts of Wharton**: Hart title fields are truncated at 56 characters, which cuts the Place numbers off Court of Appeals / CCA judge races; those races are written with an empty district and are candidates under a single office. The votes are present but the place disambiguation cannot be recovered from the export alone.
* **Bexar**: the county's exports (both parties) run consistently **+5 or so votes over** the SOS county canvass; all Dem/Rep statewide candidates show the same excess.
* **Widespread small diffs**: dozens of counties show a small number of candidates whose precinct sums differ from the SOS canvass by exactly ±1 (93 occurrences across the ASC group alone). Direction and magnitude suggest a single provisional/late ballot in the canvass absent from the county's exports; the export values are kept as parsed.
* **Typos recovered by aliases** (kept in the outputs, mapped for verification): `Raplh M. Hall` (Morris), `Tawana L. Cadien` (Austin; SOS file says W.), `John Grunwold` (Calhoun), `Elizabeth Murray-Kolb` / `MurrayKolb` spelling variants.

## PDF text-layer group (final pass): `parse_2012_pdf.py` parses the
'Precinct Report' text-layer PDFs via `pdftotext`, with a raw-mode fallback
for wrapped tables (cherokee's RR Unexpired race) and an 'Unexpired Term'
marker. Converted & committed: **bee, cherokee, coke, gray, jack,
jim_wells, denton** (both parties; denton's dash-form office names
'District Judge - 16th District Court' canonicalized) and **willacy**
(DEM pdf; its Republican side was already committed from the REP totals
xlsx). Residual documented diffs vs the canvass: bee's CoA/CCA candidates
run ~105 votes short of the canvass (bee export covers 16 of 17 precincts),
denton misses rows on some wrapped pages (11 diffs incl. 10,000-vote
Shipman discrepancy — 24703 vs 14703), willacy differs on CCA/CoA/Unexpired
(REP side absent from the DEM export). Data tests pass.

Still uncommitted: **jim_hogg** (its canvass pages parse but the Justice
4th CoA blocks use a two-level layout where the candidate name column sits
between the fixed header and the data rows; needs the same per-race-block
parser as llano) and **llano** (2-COLUMN-landscape pages with MULTIPLE race
blocks side by side, defeating per-page clustering — needs a per-race-block
parser keyed on the block title row and column x-ranges; the
`parse_2012_pdf.bbox_words` helper and the parse_2012_canvass scaffolding
are in place).

County-wide early-vote totals that cannot be split by precinct (panola EV
column, oldham EARLY column) are emitted as `Absentee` pseudo-precinct rows,
which makes candidate sums tie with the canvass except where noted.

## What was done

* **115 county precinct files written** with the filename base `20120529__tx__primary`. 105 counties cover both parties; 10 (`democratic__`/`republican__`-prefixed) cover a single party because the county's other party is only available as PDF/other formats (e.g. McCulloch, Medina, Sherman, Washington).
* ASC/Hart-export counties parsed with `python-parsers/parse_2012_asc.py` (180-char record layout; `.001` Hart exports and Calhoun's EL30A `.LST` text report included).
* Excel counties parsed with `python-parsers/parse_2012_excel.py` (wraps the 2014 Detail-Vote-Totals parser; adds the 2012 quirks listed below).
* Every file was verified against the county-level file: per-candidate precinct sums are compared to the SOS county canvass (candidate rows are authoritative; the baseline's `Total` rows are advisory). Office names are matched on canonical keys; the 2012 propositions are checked for coverage only.
* All written CSVs pass the openelections-data-tests suites (re-checked after each pass) (`duplicate_entries`, `file_format`, `missing_values`, `vote_breakdown_totals`, harness v2.2.0).

## Verification result summary

* Clean (no candidate mismatches, no missing offices): **17** of 115 counties
* Small diffs (each mismatch ±1 vote, no missing offices): **17** counties
* Notable mismatches remain: **81** counties (counts per county below) — see the JSON report `2012/20120529__report.json` for office-by-office detail.

Clean: colorado, coryell, dewitt, eastland, falls, hopkins, madison, mitchell, montgomery, nacogdoches, nolan, orange, san_jacinto, stonewall, upshur, wheeler, young

## Source defects found (files excluded or partially usable)

| County | Source | Problem |
|---|---|---|
| Tyler | `12PTYLER.ASC` (both parties) | every vote field in the export is 0; no results recoverable — file skipped |
| Fayette | `10GFAYET.ASC` | mislabeled: the export is the **2010 general election**, not the 2012 primary — file skipped |
| Chambers | `AEROLST.WRK` | EL45A summary (county totals) only; no precinct breakdown — skipped |
| Lamb | `12PLAMB.ALG`; Webb `12PWEBB.CVS` | Hart report-definition binaries, no results data — skipped |
| Bandera | Bandera sources are the 2011 amendment election (`2011_Constitutional_Amendment`); the 2012 primary files are absentee-only `EPB_ABSENTEE.csv` — not precinct-level |

## Documented source-vs-canvass discrepancies

* **Wharton**: the county exports (`12PWHART.001`) carry only a fraction of the contests (19 of ~20 offices missing).
* **Cameron**: exports omit the 13th Court of Appeals places and District Judge courts 138/404/444/445 entirely.
* **Smith**: exports omit the Criminal District Judge races (courts 7 and 114).
* **Victoria / Hood / parts of Wharton**: Hart title fields are truncated at 56 characters, which cuts the Place numbers off Court of Appeals / CCA judge races; those races are written with an empty district and are candidates under a single office. The votes are present but the place disambiguation cannot be recovered from the export alone.
* **Bexar**: the county's exports (both parties) run consistently **+5 or so votes over** the SOS county canvass; all Dem/Rep statewide candidates show the same excess.
* **Widespread small diffs**: dozens of counties show a small number of candidates whose precinct sums differ from the SOS canvass by exactly ±1 (93 occurrences across the ASC group alone). Direction and magnitude suggest a single provisional/late ballot in the canvass absent from the county's exports; the export values are kept as parsed.
* **Typos recovered by aliases** (kept in the outputs, mapped for verification): `Raplh M. Hall` (Morris), `Tawana L. Cadien` (Austin; SOS file says W.), `John Grunwold` (Calhoun), `Elizabeth Murray-Kolb` / `MurrayKolb` spelling variants.

## PDF text-layer group (final pass): `parse_2012_pdf.py` parses the
'Precinct Report' text-layer PDFs via `pdftotext`, with a raw-mode fallback
for wrapped tables (cherokee's RR Unexpired race) and an 'Unexpired Term'
marker. Converted & committed: **bee, cherokee, coke, gray, jack,
jim_wells, denton** (both parties; denton's dash-form office names
'District Judge - 16th District Court' canonicalized) and **willacy**
(DEM pdf; its Republican side was already committed from the REP totals
xlsx). Residual documented diffs vs the canvass: bee's CoA/CCA candidates
run ~105 votes short of the canvass (bee export covers 16 of 17 precincts),
denton misses rows on some wrapped pages (11 diffs incl. 10,000-vote
Shipman discrepancy — 24703 vs 14703), willacy differs on CCA/CoA/Unexpired
(REP side absent from the DEM export). Data tests pass.

Still uncommitted: **jim_hogg and llano** — 'Canvass — Total Voters' grids
whose candidate names are scattered column headers, not row labels; they
need an x-position-based mapping (pdftotext -bbox) rather than the
row-block parser, and were withdrawn rather than committed wrong.

Remaining work after the text pass:
* text counties **grimes / lampasas / waller** (Hart CSV dialect whose
  Court-of-Appeals race titles need a dedicated office cleanup) and
  **guadalupe** (SOS 'EXPORT DATA' rows with truncated race labels and labels
  stacked over candidate columns; needs its own handler), **zapata**
  ( hart header offset 3 — header matcher picks no candidate column).
* text sources that carry no results data: howard (voter history), bandera
  EPB files (mail applications), zapata 'List of Voters by Party'.
* pdf (17), doc/docx (3), zip (2), PCL-printer (hill/matagorda) groups.

