# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

OpenElections Data TX is a **data repository**, not an application. It holds pre-processed Texas election results as standardized CSV files, converted from original source files (in the separate `openelections-sources-tx` repo). The code here is a collection of one-off parsers/scraper scripts (Python, Ruby, R) that transform county-specific source formats into the standardized CSVs. The primary deliverable is the CSV data itself; the scripts are tooling.

## Data tests (the CI gate)

There is no test suite in this repo. Validation is performed by the external **`openelections/openelections-data-tests`** repo (pinned at `v2.2.0` in CI). Four test suites run as a matrix:

- `duplicate_entries`
- `file_format`
- `missing_values`
- `vote_breakdown_totals`

### Tooling

This is a **uv** project (see `pyproject.toml`, `uv.lock`, `.python-version`). Use `uv` to manage the Python environment and run scripts — e.g. `uv sync` to install dependencies, `uv run python3 ...` to execute scripts. Prefer `uv run` over invoking `python3` directly.

## Run tests locally

Check out the data-tests repo alongside this one and invoke its runner:

```bash
# one-time: clone the test harness at the pinned ref
git clone --branch v2.2.0 https://github.com/openelections/openelections-data-tests ../openelections-data-tests

# run all four suites against the full repo
python3 ../openelections-data-tests/run_tests.py --group-failures <test_name> .

# run against only changed/added files (mirrors the PR workflow)
python3 ../openelections-data-tests/run_tests.py --files <space-separated-added-csvs> --group-failures <test_name> .
```

`<test_name>` is one of the four suites above. The PR workflow (`data_tests_changed_files.yml`) only runs when added CSV files are present.

## Filename convention

From CONTRIBUTING.md — the canonical form is:

```
date__state__{party}__{special}__election_type__{jurisdiction}{office}__{office_district}__{reporting_level}.format
```

Example: `20180306__tx__primary__dallas__precinct.csv` (Dallas County precinct-level March 2018 primary).

- Statewide files live in year directories (e.g. `2022/20221108__tx__general__precinct.csv`).
- Per-county files live in `<year>/counties/` (e.g. `2022/counties/20220301__tx__primary__anderson__precinct.csv`).
- Files prefixed with `_` in `counties/` are intermediate/staging files, not final output.

## CSV format rules

Required row headers: `county`, `precinct`, `office`, `district`, `party`, `candidate`, `votes`. Optional: `early_voting`, `election_day`, `provisional`, `mail`, `absentee`, `limited` (only if present in the source). Only add a `winner` column if the winner is clearly indicated in the original data.

Conventions (enforced by the data tests):
- Unix line endings (`\n`), never `\r\n`.
- Trailing newline after the last row.
- Don't include "County" in the county name; don't include "Precinct" in the precinct name.
- Strip leading zeros from numeric precinct names (005 → 5).
- Use `NA` (not empty) for non-applicable `district` values when the column is present.
- No set order for candidates/races — order can differ between counties in the same election.
- Standard office titles: President, U.S. Senate, U.S. House, Governor (and other statewide officers), State Senate, State House.

## Architecture of the parsers

The source files come in many county-specific formats (image PDFs, Excel, fixed-width `.asc`, XML from Clarity/ElectionWare, HTML). There is no unified parser framework — instead there are many independent scripts, often county- or format-specific:

- **`python-parsers/`** — the largest set. Format-specific parsers (e.g. `asc.py` for 208-char fixed-width ASC files, `clarity_parser.py`, `pdf_extractor.py` for LLM-based PDF extraction, county-specific scripts like `dallas_parser.py`, `harris.py`, `williamson.py`). `compare_extraction.py` validates LLM-extracted output against reference files. `candidate_cache.csv` is a lookup aid.
- **Root-level `.rb` files** — Ruby parsers (historical; the `Gemfile`/Pipfile environments were removed in favor of uv). Examples: `csv_parser.rb`, `parser.rb`, `parser2.rb`, `harris_parser.rb`. If one is ever needed, re-add `remote_table` / `roo-xls` dependencies via uv or Bundler.
- **`r-parsers/`** and **`src/openelections-tx-r/`** — R scripts for specific elections, often paired with a `*_defs.csv` definitions file and a `combine_*.R` script that merges county files into the statewide CSV.
- **`scraper.py`**, **`clarity_excel_parser.py`** — top-level scraping/conversion helpers.
- **`normalize.py`** (root) — post-processing utility to clean generated CSVs. Subcommands: `line_endings` (force `\n`), `utf8` (latin→utf8), `column_names` (map deviant header names to canonical ones via an internal `xform_map`), `remove_unnamed_columns`. Run it on output before committing, e.g. `python3 normalize.py column_names path/to/file.csv`. The canonical column order is defined in `normalize.py`'s `colorder` list.
- **`vendor/`** — bundled gems (gitignored output of `bundle install`).

When adding a new county, the typical workflow is: obtain the source file, write or adapt a parser, generate the county CSV, run `normalize.py` on it, then run the data tests.

## OCR / vision tasks

Use **PaddleOCR** for all vision/OCR tasks, as is done in the sibling `~/code/openelections-data-or` repo (see its parsers under `src/parsers/` and its `CLAUDE.md`). Prefer PaddleOCR over ad-hoc LLM-based image extraction for converting image PDFs / scanned result sheets to text.

## PDF parsing

Use **natural-pdf** for PDF parsing (text extraction, layout analysis, table extraction) rather than ad-hoc approaches. Prefer it for both text-based and scanned/image PDFs; pair with PaddleOCR for OCR of image-only pages where natural-pdf's built-in OCR is insufficient.

## LLM-based PDF extraction

`LLM_EXTRACTION_CASE_STUDY.md` documents a tested approach for counties whose only source is image PDFs. `pdf_extractor.py` (in `python-parsers/`) uses the Python `llm` library with a prompt containing the target CSV schema, office-name formatting rules, and 40+ example rows; a 32,000-token output limit is required to avoid truncation. Key findings: Gemini 2.5 Pro (~82.5%) and Claude Haiku 4.5 (~77.8%) were most accurate; models tend to drop zero-vote candidates and Over/Under vote rows, so extracted output needs validation (use `compare_extraction.py`) and manual review before committing.