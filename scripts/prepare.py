#!/usr/bin/env python
"""Per-page manifest builder: text, annotation budget, thumbnails.

    python prepare.py --pdf deck.pdf --out work_L12 --tag L12 [--dpi 90]
"""
import argparse, json, os, sys

import pymupdf as fitz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_layout as lib


def build(pdf, outdir, tag, dpi=90, min_w=300):
    os.makedirs(os.path.join(outdir, "pages"), exist_ok=True)
    d = fitz.open(pdf)
    rows = []
    for i in range(d.page_count):
        p = d[i]
        text = "\n".join(l.strip() for l in p.get_text().splitlines() if l.strip())
        r = lib.pick_rect(p, 70, min_w=min_w)
        if r:
            cpl, nl, cap = lib.capacity(r)
            cap = min(cap, 520)
            box = [round(v) for v in r]
        else:
            cpl, nl, cap = (108, 16, 620)
            cap = 620
            box = None
        png = os.path.join(outdir, "pages", f"p{i + 1:03d}.png")
        p.get_pixmap(dpi=dpi).save(png)
        rows.append({"n": i + 1, "text": text, "cap": cap, "box": box,
                     "img": png, "chars": len(text)})
    man = os.path.join(outdir, f"manifest_{tag}.json")
    json.dump(rows, open(man, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with_box = sum(1 for r in rows if r["box"])
    print(f"{tag}: {len(rows)} pages, {with_box} with free box, "
          f"avg cap {sum(r['cap'] for r in rows) // len(rows)} -> {man}")
    return man


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--dpi", type=int, default=90)
    a = ap.parse_args()
    build(a.pdf, a.out, a.tag, a.dpi)
