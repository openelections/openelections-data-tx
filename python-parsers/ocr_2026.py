#!/usr/bin/env python3
"""OCR scanned 2026-primary county reports into synthetic `pdftotext -layout`
style text files that the format parsers (parse_2026_dominion / parse_2026_hart)
can consume.

Pages are rendered with pdftoppm (200 dpi), OCRed with PaddleOCR mobile models
in a worker pool, and grouped into text lines by y-overlap; x gaps become runs
of spaces, matching the layout-text conventions the parsers expect. Result: one
<base>.ocr.txt per source PDF.

Usage:
  uv run python3 python-parsers/ocr_2026.py OUT_DIR SOURCE.pdf [SOURCE.pdf ...]
        [--dpi 200] [--pages 1:44] [--workers 6] [--lang en]
"""

import argparse
import os
import re
import statistics
import subprocess
import sys
import tempfile
from collections import defaultdict
from multiprocessing import Pool

_DPI = 200


def _init_worker(lang="en"):
    global _OCR
    from paddleocr import PaddleOCR
    _OCR = PaddleOCR(
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="PP-OCRv5_mobile_rec",
        use_textline_orientation=False,
        use_doc_orientation_classify=True,
        use_doc_unwarping=False,
        lang=lang,
    )


_OCR = None
_TABLE_MODE = os.environ.get('TABLE_MODE', '1') == '1'


def _ocr_png(path):
    result = _OCR.predict(path)
    items = []
    for res in result:
        texts = res["rec_texts"]
        polys = res["rec_polys"] if "rec_polys" in res else res["dt_polys"]
        for box, text in zip(polys, texts):
            pts = box.tolist() if hasattr(box, "tolist") else [tuple(p) for p in box]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            items.append([min(ys), max(ys), min(xs), max(xs), text])
    if not items:
        return []
    lines = _table_lines(items) if _TABLE_MODE else _text_lines(items)
    if lines is None:
        lines = _text_lines(items) or []
    page_lines = []
    for b in lines:
        b.sort(key=lambda x: (x[0], x[2]))
        s = ""
        prev_end = None
        for y0, y1, x0, x1, text in b:
            if prev_end is not None:
                nsp = max(1, min(90, round((x0 - prev_end) / 7)))
                s += " " * nsp
            s += text
            prev_end = x1
        page_lines.append(s)
    return page_lines


def _text_lines(items):
    """Simple line grouping by y-interval overlap."""
    items = sorted(items, key=lambda b: (b[0], b[2]))
    lines = []
    for it in items:
        if lines:
            last = lines[-1][0]
            inter = min(last[1], it[1]) - max(last[0], it[0])
            h = min(last[1] - last[0], it[1] - it[0])
            if h > 0 and inter >= 0.45 * h:
                lines[-1].append(it)
                continue
        lines.append([it])
    return lines


def _table_lines(items):
    """Reconstruct a ruled table: label cells at the left, one value column per
    x position. Returns synthetic lines as box lists, or None when the page
    doesn't look like such a table."""
    xs_all = sorted(set(round((b[2] + b[3]) / 2) for b in items))
    # candidate label column: the leftmost cluster with the most long texts
    label_items = []
    col_items = []
    # a value column anchor: numeric tokens only
    numeric = [b for b in items if re.fullmatch(r"\d+", b[4] or "") or
               (b[4] and b[4].replace(",", "").replace(".", "").isdigit())]
    if len(numeric) < 12:
        return None
    # cluster numeric x centers into columns
    centers = sorted(((b[2] + b[3]) / 2) for b in numeric)
    cols = []
    for cx in centers:
        if cols and abs(cx - cols[-1][-1]["x"]) <= 26:
            cols[-1].append({"x": cx, "items_": [b for b in [1] and []]})
        else:
            cols.append([{"x": cx}]) if False else None
        if cols and not isinstance(cols[-1][-1], dict):
            pass
    # simpler: build columns as lists
    cols = []
    for b in numeric:
        cx = (b[2] + b[3]) / 2
        if cols and abs(cx - cols[-1]["x_last"]) <= 30:
            cols[-1]["vals"].append(b)
        else:
            cols.append({"x_last": cx, "vals": [b]})
    if len(cols) < 5:
        return None
    first_x = min(b[2] for c in cols for b in c["vals"])
    label_rows = []
    for b in items:
        # labels: everything left of the first value column (~40px tolerance)
        if isinstance(b, list) and False:
            pass
    labels = [b for b in items if b[2] <= first_x - 50]
    if len(labels) < 8:
        return None
    # label rows: chain by y
    labels = sorted(labels, key=lambda b: (b[0], b[2]))
    label_lines = []
    for b in labels:
        if label_lines:
            last = label_lines[-1][0]
            inter = min(last[1], b[1]) - max(last[0], b[0])
            h = min(last[1] - last[0], b[1] - b[0])
            if h > 0 and inter >= 0.45 * h:
                label_lines[-1].append(b)
                label_lines[-1].sort(key=lambda x: x[2])
                continue
        label_lines.append([b])
    # drop labels that look like value columns (rare) — labels are non-numeric mostly
    label_lines = [l for l in label_lines
                   if not all(re.fullmatch(r"\d[\d,]*", w[4]) for w in l)]
    if len(label_lines) < 6:
        return None
    # estimate row pitch from label row centers
    centers_l = [ (l[0][0] + l[0][1]) / 2 for l in label_lines ]
    pitches = [b - a for a, b in zip(centers_l, centers_l[1:]) if b - a > 8]
    if not pitches:
        return None
    pitch = sorted(pitches)[len(pitches) // 2]
    # value rows may sit level with the label or offset within the row band;
    # estimate a whole-page offset and pair each value to the nearest label row
    val_centers = sorted(set(round((b[0] + b[1]) / 2) for c in cols for b in c["vals"]))
    centers_l = [(l[0][0] + l[0][1]) / 2 for l in label_lines]
    best_off, best_score = 0.0, -1
    for frac in (0.0, 0.25, 0.5, 0.75):
        off = frac * pitch
        score = 0
        for vc in val_centers:
            for lc in centers_l:
                if abs(vc - (lc + off)) <= pitch * 0.22:
                    score += 1
                    break
        if score > best_score:
            best_off, best_score = off, score
    off = best_off
    rows_out = [list(l) for l in label_lines]
    claimed = {}  # (label_row_idx, col_idx) -> distance of the claim
    for ci, c in enumerate(cols):
        for v in sorted(c["vals"], key=lambda b: (b[0], b[2])):
            vc = (v[0] + v[1]) / 2
            best, bestd = 0, None
            for li, l in enumerate(label_lines):
                lc = (l[0][0] + l[0][1]) / 2
                d = abs(vc - (lc + off))
                if bestd is None or d < bestd:
                    bestd, best = d, li
            if bestd is None or bestd > pitch * 0.3:
                continue
            key2 = (best, ci)
            if key2 in claimed and claimed[key2] <= bestd:
                continue  # a closer value already claims this cell
            claimed[key2] = bestd
            rows_out[best].append(v)
        ci += 1
    return rows_out


def ocr_pdf(pdf, out_prefix, dpi=200, lang="en", pages=None, workers=6):
    global _DPI
    _DPI = dpi
    with tempfile.TemporaryDirectory() as tmp:
        cmd = ["pdftoppm", "-png", "-r", str(dpi)]
        if pages:
            cmd += ["-f", str(pages[0]), "-l", str(pages[1])]
        cmd += [pdf, os.path.join(tmp, "p")]
        subprocess.run(cmd, check=True, capture_output=True)
        pngs = sorted(os.path.join(tmp, f) for f in os.listdir(tmp)
                      if f.endswith(".png"))
        with Pool(workers, initializer=_init_worker, initargs=(lang,)) as pool:
            blocks = pool.map(_ocr_png, pngs, chunksize=1)
    text = "\n\n".join("\n".join(b) for b in blocks) + "\n"
    with open(out_prefix + ".ocr.txt", "w") as fh:
        fh.write(text)
    return out_prefix + ".ocr.txt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--pages", default=None, help="e.g. 1:44")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--lang", default="en")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    pages = None
    if args.pages:
        a, b = args.pages.split(":")
        pages = (int(a), int(b))
    for src in args.sources:
        base = os.path.splitext(os.path.basename(src))[0]
        out_prefix = os.path.join(args.outdir, base)
        if os.path.exists(out_prefix + ".ocr.txt"):
            print("skip (exists):", out_prefix + ".ocr.txt", file=sys.stderr)
            continue
        ocr_pdf(src, out_prefix, dpi=args.dpi, lang=args.lang, pages=pages,
                workers=args.workers)
        print("wrote", out_prefix + ".ocr.txt", file=sys.stderr)


if __name__ == "__main__":
    main()