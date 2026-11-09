#!/usr/bin/env python3
"""OCR scanned 2026-primary county PDFs through the PaddleOCR cloud API
(PaddleOCR-VL) and convert the results into <base>.ocr.txt layout-style text
sidecars that parse_2026_dominion / parse_2026_hart / parse_2026_box_table
can consume.

API flow (HTTP via curl subprocess; python requests trips connection resets
against aistudio-app.com from this network):
  * POST {JOB_URL} with model + optionalPayload + file -> jobId
  * GET  {JOB_URL}/{jobId} until data.state == done -> data.resultUrl.jsonUrl
  * GET  jsonUrl -> JSONL: records of result.layoutParsingResults[], one entry
    per page, each holding markdown.text with header divs + HTML tables.

Converter: each div becomes its own line; each table row becomes one line of
space-separated cells; '%' cells and the VOTE % header cell are dropped so
race rows keep exactly TOTAL + method counts. A race title seen since the last
'Contest Totals' row is carried across page breaks (dominion reports split
mid-race, and the continuation page's block would otherwise have no title).

Usage:
  uv run python3 python-parsers/ocr_api_2026.py outdir SOURCE.pdf ...
        [--model PaddleOCR-VL-1.6] [--token TOKEN]
"""

import argparse
import html
import json
import os
import re
import subprocess
import tempfile
import sys
import time

JOB_URL = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
TOKEN = os.environ.get("PADDLE_OCR_TOKEN", "30196ed453662a910bf8cfd908de4ee67fb89161")
MODEL = "PaddleOCR-VL-1.6"

TD_RE = re.compile(r"<td([^>]*)>(.*?)</td>", re.S)
TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
TABLE_RE = re.compile(r"<table[^>]*>(.*?)</table>", re.S)
DIV_RE = re.compile(r"<div[^>]*>(.*?)</div>", re.S)
PCT_RE = re.compile(r"^[-+]?[\d,]+(?:\.\d+)?\s*%$")
RACE_TITLE_RE = re.compile(
    r"(SENAT|REPRESENTAT|GOVERNOR|JUDGE|COURT|COMMISSION|BOARD|ATTORNEY|"
    r"LAND OFFICE|AGRICULTURE|COMPTROLLER|RAILROAD)", re.I)
TOTALS_RE = re.compile(r"^(Total Votes Cast|Overvotes|Undervotes|Contest Totals)$", re.I)
STATS_RE = re.compile(r"(Statistics|Registered Voters|Ballots Cast|Voter Turnout)", re.I)
HEADER_TOTAL_RE = re.compile(r"^TOTAL(?=\b|\s|$)", re.I)
VOTEFOR_RE = re.compile(r"^Vote For\b", re.I)


def unesc(s):
    return html.unescape(s).replace("\\n", "\n")


def clean_cell(s):
    """Unescape but KEEP line breaks (callers split on them)."""
    return unesc(s).strip()


def table_rows(table_html):
    rows = []
    for tr in TR_RE.finditer(table_html):
        cells = []
        for m in TD_RE.finditer(tr.group(1)):
            cells.append(unesc(m.group(2)))
        rows.append(cells)
    return rows


def seg(t):
    """Collapse one segment's whitespace after splitting off line breaks."""
    return re.sub(r"\s+", " ", t).strip()


def is_race_title(t):
    t = re.sub(r"\s*Vote For\b.*$", "", t, flags=re.I)
    if not t:
        return False
    if TOTALS_RE.match(t) or STATS_RE.search(t):
        return False
    if HEADER_TOTAL_RE.match(t) or VOTEFOR_RE.match(t):
        return False
    if re.fullmatch(r"[\d,.]+", t or ""):
        return False
    if re.search(r"\d", t) and not re.search(r"(District|Place|Court of|No\.|#)", t):
        return False
    return bool(RACE_TITLE_RE.search(t))


def is_count_row(units):
    """label + one or more integer cells."""
    if len(units) < 2:
        return False
    return all(re.fullmatch(r"[\d,]+", u) for u in units[1:] if u) and \
        any(units[1:]) and not HEADER_TOTAL_RE.match(units[0])


class Untitled:
    """Placeholder line for a race whose title cell the API dropped.
    __UNTITLED_RACE__ <file-page-number> <occurrence-on-page>N"""
    SENTINEL = "__UNTITLED_RACE__"

    @classmethod
    def untitled(cls, page, occ=1):
        return f"{cls.SENTINEL} {page} {occ}"

    @classmethod
    def is_untitled(cls, line):
        return line.startswith(cls.SENTINEL)


def page_to_lines(page_md, state):
    lines = []
    tables = list(TABLE_RE.finditer(page_md))
    divs = list(DIV_RE.finditer(page_md))
    events = sorted(
        [(m.start(), m.end(), "table", i) for i, m in enumerate(tables)] +
        [(m.start(), m.end(), "div", i) for i, m in enumerate(divs)])

    def carry(in_stats, t):
        if in_stats or state["have_title"] or not state.get("last_title"):
            return False
        if VOTEFOR_RE.match(t):
            # a new race whose title cell the API dropped: do not inherit the
            # previous race's title — recover it from local page OCR later
            lines.append(Untitled.untitled(state["page"]))
            return True
        if HEADER_TOTAL_RE.match(t) or re.fullmatch(r"[\d,]+", t):
            lines.append(state["last_title"])
            state["have_title"] = True
            return True
        return False

    for _, _, kind, i in events:
        if kind == "div":
            parts = [seg(p) for p in unesc(re.sub(r"<[^>]+>", "",
                                                  divs[i].group(1))).split("\n")
                     if seg(p)]
            lines.extend(parts)
            continue
        rows = table_rows(tables[i].group(1))
        in_stats = False
        for cells in rows:
            raw = [re.sub(r"<img[^>]*>", "", clean_cell(c)).strip()
                   for c in cells]
            raw = [c for c in raw if c]
            if STATS_RE.search(" ".join(raw)):
                in_stats = True
            drop = set()
            for k, c in enumerate(raw):
                cu = c.upper().replace(" ", "")
                if cu in ("VOTE%", "VOTES%", "PERCENT", "PCTOFTOTAL") or \
                        PCT_RE.match(seg(c) or ""):
                    drop.add(k)
            kept = [(k, c) for k, c in enumerate(raw)
                    if k not in drop and not PCT_RE.search(seg(c) or "")]
            segs = []
            for _, c in kept:
                segs.extend([seg(p) for p in c.split("\n") if seg(p)])
            segs = [t for t in segs if t]
            if not segs:
                continue
            first = segs[0]
            if is_race_title(first):
                state["last_title"] = first
                state["have_title"] = True
                lines.append(first)
                for t in segs[1:]:
                    if TOTALS_RE.match(t):
                        state["have_title"] = False
                    lines.append(t)
                continue
            if TOTALS_RE.match(first):
                state["have_title"] = False
                lines.append("  ".join(segs))
                continue
            if HEADER_TOTAL_RE.match(first) or is_count_row(segs) or \
                    VOTEFOR_RE.match(first):
                carry(in_stats, first)
                lines.append("  ".join(segs))
                continue
            for t in segs:
                carry(in_stats, t)
                lines.append(t)
    return lines


METHOD_WORDS = {"Absentee", "Absentee Voting", "Early", "Early Voting",
                 "Voting", "Election Day", "Election", "Day", "By Mail",
                 "Provisional", "Limited", "Vote For 1", "TOTAL"}


def merge_header_fragments(lines):
    """Join a lone 'TOTAL' line plus the single method-word lines that follow
    it (the API splits the stats header into one row per cell)."""
    out = []
    i = 0
    while i < len(lines):
        t = lines[i].strip()
        if t == "TOTAL":
            j = i + 1
            frag = ["TOTAL"]
            while j < len(lines) and lines[j].strip() in METHOD_WORDS - {"TOTAL"}:
                frag.append(lines[j].strip())
                j += 1
            if len(frag) > 1:
                out.append("  ".join(frag))
                i = j
                continue
        out.append(lines[i])
        i += 1
    return out


def is_ghost_title_pair(a, b):
    """Two adjacent lines both looking like race titles: the API sometimes
    emits a ghost second title (less specific) under the first. If both carry
    their own party prefix, treat the pair as duplicated and keep the longer
    (more specific) one."""
    return is_race_title(a) and is_race_title(b) and \
        re.match(r"^\s*(DEM|REP|LIB|GRN)\b", a) is not None and \
        re.match(r"^\s*(DEM|REP|LIB|GRN)\b", b) is not None


def collapse_ghost_titles(lines):
    out = []
    i = 0
    while i < len(lines):
        if i + 1 < len(lines) and is_ghost_title_pair(lines[i], lines[i + 1]):
            keep = lines[i] if len(lines[i]) >= len(lines[i + 1]) else lines[i + 1]
            out.append(keep.strip())
            i += 2
            continue
        out.append(lines[i])
        i += 1
    return out


def convert(jsonl_path, out_path, src=None):
    state = {"last_title": None, "have_title": False, "page": 0,
             "page_occ": {}}
    out_pages = []
    for raw in open(jsonl_path):
        if not raw.strip():
            continue
        rec = json.loads(raw)
        for pg in rec["result"]["layoutParsingResults"]:
            state["page"] += 1
            state["page_occ"] = {}
            try:
                pg_lines = page_to_lines(pg["markdown"]["text"], state)
            except Exception as e:  # noqa: BLE001
                print(f"  convert error on a page: {e!r}", file=sys.stderr)
                continue
            if pg_lines:
                pg_lines = collapse_ghost_titles(merge_header_fragments(pg_lines))
                out_pages.append("\n".join(pg_lines))
            out_pages.append("")
    text = "\n".join(out_pages).rstrip() + "\n"
    if src is not None and Untitled.SENTINEL in text:
        text = recover_untitled(src, text)
    with open(out_path, "w") as fh:
        fh.write(text)
    return out_path


def recover_untitled(src, text):
    """For every '__UNTITLED_RACE__ <page>' placeholder, OCR that page locally
    and splice in the race title + 'Vote For' lines that precede its first
    count row. The occ counter handles two dropped titles on one page."""
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location(
            "ocr_local", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "ocr_2026.py"))
        ocr_local = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ocr_local)
        ocr_local._DPI = 200
        ocr_local._init_worker("en")
    except Exception as e:  # noqa: BLE001
        print(f"  untitled-title recovery unavailable: {e!r}", file=sys.stderr)
        return text.replace(Untitled.untitled("", 0), "")
    pages_needed = sorted({int(m.group(1)) for m in
                           re.finditer(Untitled.SENTINEL + r"\s+(\d+)", text)})
    page_text = {}
    with tempfile.TemporaryDirectory() as tmp:
        cmd = ["pdftoppm", "-png", "-r", "200", src, os.path.join(tmp, "p")]
        subprocess.run(cmd, check=False, capture_output=True)
        pngs = sorted(f for f in os.listdir(tmp) if f.endswith(".png"))
        for pg in pages_needed:
            if pg - 1 < len(pngs):
                page_text[pg] = ocr_local._ocr_png(os.path.join(tmp, pngs[pg - 1]))
    out = []
    occ_seen = {}
    for line in text.split("\n"):
        m = re.fullmatch(re.escape(Untitled.SENTINEL) + r"\s+(\d+)\s+(\d+)", line)
        if not m:
            out.append(line)
            continue
        pg, occ = int(m.group(1)), int(m.group(2))
        occ = occ + occ_seen.get(pg, 0)
        occ_seen[pg] = occ_seen.get(pg, 0) + 1
        recovered = page_text.get(pg) or []
        title_lines = _title_cluster_in_page(recovered, occ)
        if title_lines:
            out.extend(title_lines)
        else:
            print(f"  warning: could not recover title for page {pg} occ {occ}",
                  file=sys.stderr)
    out_txt = "\n".join(out).rstrip() + "\n"
    # drop page-1-untitled placeholders that had no title available
    return out_txt


def _title_cluster_in_page(page_lines, occ=1):
    """ocr_2026 page lines -> title + 'Vote For' lines above the first
    'TOTAL' header / count row (or above the occ-th 'Vote For' line)."""
    lines = [l.strip() for l in page_lines if l.strip()]
    title_like = []
    idx = 0
    found = 0
    for l in lines:
        if VOTEFOR_RE.match(l):
            found += 1
            if found == occ:
                idx = lines.index(l)
                break
    if not idx:
        # first 'TOTAL' header or count row after stats
        for j, l in enumerate(lines):
            if HEADER_TOTAL_RE.match(l) or re.search(r"\s\d+$", l) \
                    or TOTALS_RE.match(l):
                idx = j
                break
    if not idx:
        return None
    cluster = []
    for j in range(idx - 1, -1, -1):
        t = lines[j]
        if HEADER_TOTAL_RE.match(t) or TOTALS_RE.match(t) or \
                re.search(r"\d[,.]?\s*$", t) and not VOTEFOR_RE.match(t):
            break
        cluster.insert(0, t)
        if is_race_title(t):
            break
    cluster = [t for t in cluster if is_race_title(t) or VOTEFOR_RE.match(t)]
    if not cluster:
        return None
    # keep only the contiguous title+VoteFor tail of the cluster
    keep = []
    for t in reversed(cluster):
        if is_race_title(t) or VOTEFOR_RE.match(t):
            keep.insert(0, t)
        else:
            if keep:
                break
    return [re.sub(r"\s+", " ", t) for t in keep]


def curl_json(args):
    last = None
    for _ in range(6):
        r = subprocess.run(["curl", "-sS", "--max-time", "60"] + args,
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            try:
                return json.loads(r.stdout)
            except json.JSONDecodeError as e:  # noqa: PERF203
                last = e
        time.sleep(5)
    raise RuntimeError(f"curl failed: {last}")


def submit(path, token, model, orient=False):
    cmd = ["curl", "-sS", "--max-time", "300", "-X", "POST",
           "-H", f"Authorization: bearer {token}",
           "-F", "model=" + model,
           "-F", "optionalPayload=" + json.dumps({
               "useDocOrientationClassify": orient,
               "useDocUnwarping": False,
               "useChartRecognition": False,
           }),
           "-F", f"file=@{path}", JOB_URL]
    j = curl_json(cmd)
    if j.get("code") != 0:
        raise RuntimeError(f"submit failed: {j}")
    return j["data"]["jobId"]


def polls(job_id, token):
    for _ in range(1200):
        j = curl_json(["-H", f"Authorization: bearer {token}",
                       f"{JOB_URL}/{job_id}"])
        d = j.get("data") or {}
        st = d.get("state")
        if st == "done":
            return d["resultUrl"]["jsonUrl"]
        if st == "failed":
            raise RuntimeError(f"job failed: {d.get('errorMsg')}")
        prog = d.get("extractProgress") or {}
        print(f"  job {job_id}: {st} "
              f"{prog.get('extractedPages', '?')}/{prog.get('totalPages', '?')}",
              file=sys.stderr)
        time.sleep(8)
    raise RuntimeError(f"job {job_id} timed out")


def fetch_text(url):
    for _ in range(6):
        r = subprocess.run(["curl", "-sS", "--max-time", "600", url],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout:
            return r.stdout
        time.sleep(5)
    raise RuntimeError(f"download failed: {url[:80]}")


def process(src, outdir, token, model):
    base = os.path.splitext(os.path.basename(src))[0]
    jsonl = os.path.join(outdir, base + ".api.jsonl")
    if not os.path.exists(jsonl):
        job_id = submit(src, token, model)
        print(f"{base}: job {job_id}", file=sys.stderr)
        url = polls(job_id, token)
        text = fetch_text(url)
        with open(jsonl, "w") as fh:
            fh.write(text)
        print(f"{base}: fetched {len(text)} bytes", file=sys.stderr)
    out = os.path.join(outdir, base + ".ocr.txt")
    if not os.path.exists(out):
        convert(jsonl, out)
    print("wrote", out, file=sys.stderr)


def recover_first_titles(src, ocr_path, outdir, dpi=200):
    """The VL API drops the '<party> <race>' + 'Vote For' cells that open a
    report's page 1 (verified: neither markdown nor prunedResult holds them).
    Recover them with one local-PaddleOCR page and insert before the first
    untitled race block of the converted file.

    Returns True if a title was inserted."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ocr_local", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "ocr_2026.py"))
    ocr_local = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ocr_local)
    os.environ["TABLE_MODE"] = "0"   # plain layout lines are fine for titles
    ocr_local._DPI = dpi
    try:
        ocr_local._init_worker("en")
        with tempfile.TemporaryDirectory() as tmp:
            cmd = ["pdftoppm", "-png", "-r", str(dpi), "-f", "1", "-l", "1",
                   src, os.path.join(tmp, "p")]
            subprocess.run(cmd, check=True, capture_output=True)
            png = sorted(os.listdir(tmp))[0]
            blocks = [ocr_local._ocr_png(os.path.join(tmp, png))]
        lines = [l.rstrip() for b in blocks for l in b]
    except Exception as e:  # noqa: BLE001
        print(f"  title recovery OCR failed: {e!r}", file=sys.stderr)
        return False
    # page-1 layout: ... 'Voter Turnout ...' lines, then the race title lines,
    # then the 'TOTAL ...' header row
    try:
        last_turnout = max(i for i, l in enumerate(lines)
                           if l.startswith("Voter Turnout"))
    except ValueError:
        return False
    title_lines = []
    for l in lines[last_turnout + 1:]:
        t = l.strip()
        if not t:
            continue
        if VOTEFOR_RE.match(t):
            title_lines.append(t)
            continue
        if re.match(r"^TOTAL\b", t, re.I) or re.search(r"\d\s*$", t):
            break
        title_lines.append(t)
    title_lines = [t for t in title_lines if not HEADER_TOTAL_RE.match(t)]
    if not title_lines:
        return False
    txt_lines = [l.rstrip() for l in open(ocr_path)]
    # find last 'Voter Turnout' line in the converted file
    out_idx = None
    for i, l in enumerate(txt_lines):
        if l.startswith("Voter Turnout"):
            out_idx = i
    if out_idx is None:
        return False
    for j in range(out_idx + 1, len(txt_lines)):
        if re.match(r"^TOTAL\s+Absentee", txt_lines[j]):
            txt_lines[j:j] = title_lines
            with open(ocr_path, "w") as fh:
                fh.write("\n".join(txt_lines).rstrip() + "\n")
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--token", default=TOKEN)
    ap.add_argument("--orient", action="store_true",
                    help="enable useDocOrientationClassify (rotated pages)")
    ap.add_argument("--force", action="store_true",
                    help="re-submit even if a cached api.jsonl exists")
    ap.add_argument("--no-recover", action="store_true",
                    help="skip local page-1 OCR title recovery")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    for src in args.sources:
        base = os.path.splitext(os.path.basename(src))[0]
        jsonl = os.path.join(args.outdir, base + ".api.jsonl")
        if args.force and os.path.exists(jsonl):
            os.rename(jsonl, jsonl + ".rot.bak")
        if not os.path.exists(jsonl):
            try:
                job_id = submit(src, args.token, args.model, orient=args.orient)
                print(f"{base}: job {job_id}", file=sys.stderr)
                url = polls(job_id, args.token)
                text = fetch_text(url)
                with open(jsonl, "w") as fh:
                    fh.write(text)
                print(f"{base}: fetched {len(text)} bytes", file=sys.stderr)
            except Exception as e:  # noqa: BLE001 - keep batch alive
                print(f"{base}: FAILED, skipping (will retry): {e!r}",
                      file=sys.stderr)
                continue
        out = os.path.join(args.outdir, base + ".ocr.txt")
        if not os.path.exists(out):
            try:
                convert(jsonl, out, src=src)
            except Exception as e:  # noqa: BLE001
                print(f"{base}: convert failed: {e!r}", file=sys.stderr)
                continue
            if not args.no_recover:
                ok = recover_first_titles(src, out, args.outdir)
                if ok:
                    print(f"{base}: recovered page-1 title", file=sys.stderr)
        print("wrote", out, file=sys.stderr)


if __name__ == "__main__":
    main()
