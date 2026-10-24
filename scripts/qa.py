#!/usr/bin/env python
"""QA: ink-under-note test + page-number / index consistency.

    python qa.py --config work/config.json
"""
import argparse, json, os, re, sys

import numpy as np
import pymupdf as fitz

EXIT_BAD = 1


def ink_test(src_pdf, content_pdf, label):
    src = fitz.open(src_pdf)
    out = fitz.open(content_pdf)
    meta = json.load(open(content_pdf.replace(".pdf", "_map.json"), encoding="utf-8"))
    pm = {int(k): v for k, v in meta["page_map"].items()}
    rev = {}
    for n, p in pm.items():
        rev.setdefault(p, []).append(n)
    bad = []
    for p, pages in sorted(rev.items()):
        if len(pages) > 1:          # merged page: geometry differs, skip
            continue
        n = pages[0]
        rects = []
        for b in out[p - 1].get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    # note font is SimHei at the size chosen by the layout step
                    if s["font"].startswith("SimHei") and s["size"] >= 8.0 \
                            and s["size"] < 15.5 and s["bbox"][1] < 530:
                        rects.append(fitz.Rect(s["bbox"]))
        if not rects:
            continue
        pmx = src[n - 1].get_pixmap(dpi=144, colorspace=fitz.csGRAY)
        img = np.frombuffer(pmx.samples, dtype=np.uint8).reshape(pmx.height, pmx.width)
        k = 2.0
        worst = 0.0
        for r in rects:
            x0, y0 = max(0, int(r.x0 * k)), max(0, int(r.y0 * k))
            x1, y1 = min(img.shape[1], int(r.x1 * k)), min(img.shape[0], int(r.y1 * k))
            if x1 <= x0 or y1 <= y0:
                continue
            worst = max(worst, float((img[y0:y1, x0:x1] < 210).mean()))
        if worst > 0.02:
            bad.append((n, p, round(worst, 3)))
    bad.sort(key=lambda x: -x[2])
    print(f"[{label}] ink-under-note: {len(bad)} page(s) over 2%")
    for b in bad:
        print("   source p%d -> handout p%d  ink %.3f" % b)
    return bad


def number_test(final_pdf, front_pages):
    d = fitz.open(final_pdf)
    bad_footer, idx = [], []
    for i in range(front_pages, d.page_count):
        m = re.search(r"讲义 P(\d+)", d[i].get_text())
        if m and int(m.group(1)) != i + 1:
            bad_footer.append((i + 1, int(m.group(1))))
    for i in range(2, front_pages):
        for b in d[i].get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    if s["bbox"][0] > 480 and s["text"].strip().isdigit():
                        idx.append(int(s["text"]))
    out_of_range = sorted({n for n in idx if n > d.page_count})
    print(f"[{os.path.basename(final_pdf)}] pages {d.page_count}  "
          f"footer mismatches {len(bad_footer)}  index out of range {out_of_range}")
    if bad_footer:
        print("   ", bad_footer[:5])
    return bad_footer, out_of_range


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8"))
    scratch, outdir = cfg["scratch"], cfg["output_dir"]
    bad = 0
    for src in cfg["sources"]:
        tag = src["tag"]
        content = os.path.join(scratch, f"out/content_{tag}.pdf")
        if os.path.exists(content):
            bad += len(ink_test(src["pdf"], content, tag))
        final = os.path.join(outdir, src["out"])
        # front page count = index of the first content page; derive from the footer
        d = fitz.open(final)
        first = None
        for i in range(d.page_count):
            if "讲义 P" in d[i].get_text():
                first = i
                break
        if first is not None:
            f, o = number_test(final, first)
            bad += len(f) + len(o)
    print("QA:", "FAIL" if bad else "PASS")
    sys.exit(EXIT_BAD if bad else 0)
