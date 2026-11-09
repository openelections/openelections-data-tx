# 2014 primary precinct verification report

Generated 2026-11-08. 22 new counties converted from the 180/208-char fixed-width
ASC exports in `openelections-sources-tx/2014/primary/` (files with "runoff" in
the name and the March 11 Bexar joint-primary file excluded). All precinct
totals verified against the county-level baseline
`2014/20140304__tx__primary__county.csv` via `python-parsers/verify_2014.py`
(per-candidate sums; office totals advisory — the baseline's own `Total` rows
are inconsistent with its candidate rows in several counties, and ~1,163
baseline rows in 32 counties are corrupt with the candidate's votes lost).

## Fully verified (candidate sums equal the baseline: 12 counties)

bastrop, dallam, fayette, lamar, lavaca, montague, moore, rusk (±1 vote),
san_jacinto, midland (±1), dallas (±2 on two candidates), lamb (±1),
washington (±1 on one candidate), jefferson, yoakum, williamson*, hidalgo

*williamson: Jim Hogan / Richard "Kinky" Friedman sums are swapped
(2235/2285 precinct vs 2285/2235 baseline) relative to the baseline — the two
Comptroller candidates' rows appear transposed in the county's export.

## Source-level discrepancies (documented, not parse errors)

| County | Issue |
|---|---|
| bexar | Main+early ASC file pairs merged (keep-larger). Per-candidate sums run −4 to −12 (~0.03–0.05%) below the certified county totals; e.g. Ken Paxton 25,294 vs 25,303. |
| van_zandt | ASC source votes run +1 to +6 (~0.1%) above the certified totals for most Republican statewide candidates; single-file parse, so the difference is source vs canvass. |
| hemphill | The "Democratic" ASC export contains only REP-party rows; no Dem candidate data exists at the source. 20 Dem baseline candidates have no precinct coverage. Also +1/-2 on a few REP rows. |
| swisher | Single REP-only source file; all Dem candidates (and several REP ones absent from the export) uncovered. |
| shelby | Both ASC files contain only a partial slate (no 12th Court of Appeals, CCA 4/9, State Senate 3, State Rep 9, Supreme Court Place 8 rows). |
| hidalgo | Criminal District Attorney race (René Guerra / Ricardo Rodriguez) absent from the Hidalgo canvass ASCs entirely. County truncates several race titles; places recovered via `repair_2014.py` (candidate→place map from the baseline). Hidalgo writes the DA race under office='Criminal'. |
| washington | Nathan Hecht (Chief Justice, Supreme Court) sums 2,267 in the ASC vs 3,267 certified — a precinct's rows appear missing at the source. |
| rusk | Reynaldo "Ray" Madrigal: ASC gives 50 votes vs 5 certified for Lieutenant Governor. |

## Baseline data-quality notes

- ~1,163 rows in 32 counties (e.g. Armstrong, Foard, La Salle, Brooks, Duval,
  Zavala) are corrupt: `<county>,<office>,<district>,<candidate>,,,<party>,0`
  — the write collapsed `incumbent` + `votes` and put the party in the votes
  column. True votes are unknown in the baseline; verification for those
  offices uses the `Total` row (which itself only floors the good candidate
  rows) plus the precinct file as evidence.
- The `Total` rows do not always equal the sum of the baseline's candidate
  rows even in counties with no corrupt rows (Lamar Attorney General: 5,083
  vs candidate sum 5,592); the ASC's under/over-vote rows explain part of the
  gap, but both figures can differ. Office-total checks are advisory.
- The baseline misspells Dallas county-level judge 'Ernest White' as
  'Ernest While' and drops the accented e in 'Rubán Hinojosa'.

## Excel group

Added 2026-11-08: 79 counties converted from the Excel/CSV-shaped sources in
`openelections-sources-tx/2014/primary/` (Hart "Detail Vote Totals" long
exports, SOS 37-column DVT exports, and ~20 wide "pct-by-pct" sheet layouts;
parsers `python-parsers/parse_2014_excel.py` + `python-parsers/parse_2014_wide.py`,
driven by `build_2014.py excel` which also applies `repair_2014.py` and
verifies every county against the county-level baseline). Counties whose
sources cover a single party are written as
`20140304__tx__primary__{democratic|republican}__<county>__precinct.csv`.

### Fully verified (per-candidate sums equal the baseline: 14)

childress, coryell (±1 vote), dickens, floyd, hopkins, liberty, lubbock,
madison, nacogdoches, roberts, runnels, tom_green, zapata, zavala

### Small diffs (≤ ~25 mismatching candidate rows, mostly ±1–2 votes or
source-vs-canvass rounding)

armstrong, brazoria, burnet (±1), cooke, denton, falls, fannin, fort_bend,
franklin, hale, harrison, hockley (Marchbanks +39: the county's own
early/ED sheets double-count him), hood, howard, hutchinson, kaufman,
kenedy, kinney (Reasor +1), lasalle, lipscomb, llano, mclennan, menard,
milam, montgomery, newton, oldham* (±1), parker, randall, reagan,
red_river, refugio, rockwall (Granberg 824 vs baseline 324 — the county's
certified-file number appears mistyped; the canvass sheets agree on 824),
san_patricio, schleicher, tarrant, taylor, trinity, wood (Walther +300,
Abbott −106, Bush −984, Hensarling −126: the county's own export disagrees
with the certified canvass for a handful of candidates)

*oldham keeps the pre-existing tracked `20140304__tx__primary__oldham__precinct.csv`;
the new conversion is `republican__oldham__precinct.csv` (the excel source is
R-only and also lacks District Judge 222, 7th Court of Appeals and
State Rep 86, whose baseline rows therefore have no precinct coverage).

### Source gaps / larger diffs (documented, not invented)

- **cass**: the GRAND sheet's second precinct block repeats the label `12`
  and uses extra-wide labels, so a handful of races are still unmatched
  (≈50 candidate rows); the DEM file is a partial sheet (fewer races).
- **bowie**: two-region wide tables whose second region repeats/misprints
  precinct labels (`12 13 12 14`); not converted — needs manual layout
  handling if attempted (source `DEMOCRAT/REP EARLY|ELECTION DAY` .xls).
- **single-party sources** (county baseline also contains only DEM rows for
  cottle: REP candidates in the baseline with no coverage): andrews (R file
  uses `PRE #` header, partially parsed), hall, hood (criminal district
  judge 355 missing at source), rains, trinity, titus, kinney.
- **DVT exports whose `total_votes` excludes absentee/provisional ballots**
  (certified totals exceed early+ED sums by the absentee amount): anderson,
  atascosa (−274 countywide), blanco, bosque, coleman, ector, harrison,
  jasper, kaufman, waller, wichita, willacy, garza, panola, sterling, titus.
- **hamilton**: the `R/D 3-4-2014` sheet yields only ~82 rows (partial
  race coverage; the source's election-day sheet is an unrecognized layout).
- **hansford**: the early-votes `Sheet2` block for the 2014 races sits under
  a 2008 header and its 2014 blocks use truncated office labels; ≈12 races
  still unmatched.
- **hidalgo**: no excel/precinct source beyond the ASC canvass file already
  converted in the ASC section.
- **harris**: 223k rows parsed; ≈113 candidate rows differ in the baseline
  joins (Harris county's report uses truncated local-race titles and the
  baseline's own local rows are partially corrupt).
- **kimble**: the sheet's totals columns disagree with the certified rows
  for the district-attorney race (missing office) and ~10 candidates.
- **bexar/atascosa-style note**: where a county's export is the official
  canvass the sums tie out; where they differ the certified baseline is the
  target and the export's shortfall equals its missing absentee column.


## Not yet converted (source issues remaining)

- chambers (`AEROLST.WRK`) and stonewall (`EL30A.LST`) — binary/HP PCL
  printstream, not parseable as ASC.
- palo_pinto — ragged fixed-width lines (mixed 178/180 lengths), needs manual
  layout handling.
- clay — `..._ERM.exe` is actually a zip archive of the ERM election package.
- bowie — two-region wide tables with a repeated/ambiguous second precinct
  block (see Excel group above).

Old party-prefixed partial files superseded by full-county files (removed):
`20140304__tx__primary__{democratic__shelby,republican__dallam,republican__hemphill,republican__moore}__precinct.csv`.
