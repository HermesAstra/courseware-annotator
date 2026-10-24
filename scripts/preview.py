#!/usr/bin/env python
"""Fast single-page preview: build only the pages you just changed.

    python preview.py --config work/config.json --pages 3,17,42 [--tag L1] [--out work/out/preview.pdf]
    python preview.py --config work/config.json --front       # 只渲染前置页（封面/图例/索引/关键词）

No front matter is built for page previews. The footer carries the *real* final page
number (same drop/merge planner as build.py), so you can judge font size, placement,
strip vs inline and merged pages without paying for a full 60-page build. Also writes
`preview_pNNN.png` next to the PDF for `read_image`.

`--front` renders the front matter only (a few seconds): its page numbers already use the
real offset, so what you see is what ships. Use it to check cover text, the index and the
keyword lookup without a 2-minute full build.
"""
import argparse, json, os, sys

import pymupdf as fitz

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import assemble
import build


def render_front(src, scratch, out_pdf, dpi=95):
    """只渲染前置页（封面/图例/索引/关键词）。页码用真实偏移，所见即所得。"""
    ann = build.load_ann(os.path.join(scratch, src["ann_glob"]))
    manifest = os.path.join(scratch, src["manifest"])
    man = {r["n"]: r for r in json.load(open(manifest, encoding="utf-8"))}
    pm = assemble.page_map(man, ann)
    front = build.front_doc(src, ann, pm)
    probe = front(0)
    n_idx = probe.page_count
    probe.close()
    doc = front(n_idx)

    os.makedirs(os.path.dirname(out_pdf), exist_ok=True)
    out = fitz.open()
    base = os.path.dirname(out_pdf)
    for i in range(doc.page_count):
        out.insert_pdf(doc, from_page=i, to_page=i)
        png = os.path.join(base, f"front_p{i + 1:03d}.png")
        doc[i].get_pixmap(dpi=dpi).save(png)
        first = next((l for l in doc[i].get_text().splitlines() if l.strip()), "")
        print(f"front p{i + 1}: {first.strip()[:40]}  -> {png}")
    out.save(out_pdf, garbage=4, deflate=True)
    print(f"{out.page_count} front page(s) -> {out_pdf}; 正文首页 = P{n_idx + 1}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--pages", default=None, help="原课件页号，逗号分隔，如 3,17,42")
    ap.add_argument("--front", action="store_true", help="只渲染前置页（封面/图例/索引/关键词）")
    ap.add_argument("--tag", default=None, help="多份 source 时指定用哪份")
    ap.add_argument("--out", default=None)
    ap.add_argument("--dpi", type=int, default=95)
    a = ap.parse_args()

    cfg = json.load(open(a.config, encoding="utf-8"))
    scratch = cfg["scratch"]
    srcs = [s for s in cfg["sources"] if a.tag is None or s["tag"] == a.tag]
    if not srcs:
        raise SystemExit(f"no source with tag {a.tag!r}")
    src = srcs[0]

    # 前置预览与正文预览默认写不同文件，免得互相覆盖
    default_out = (f"preview_front_{src['tag']}.pdf" if a.front
                   else f"preview_{src['tag']}.pdf")
    out_pdf = a.out or os.path.join(scratch, "out", default_out)
    if a.front:
        render_front(src, scratch, out_pdf, dpi=a.dpi)
        return
    if not a.pages:
        raise SystemExit("要么给 --pages，要么给 --front")

    ann = build.load_ann(os.path.join(scratch, src["ann_glob"]))
    manifest = os.path.join(scratch, src["manifest"])
    man = {r["n"]: r for r in json.load(open(manifest, encoding="utf-8"))}
    pm = assemble.page_map(man, ann)
    front = build.front_doc(src, ann, pm)
    probe = front(0)
    n_idx = probe.page_count
    probe.close()

    units = list(assemble.iter_units(man, ann))

    def unit_of(k):
        for kind, pages in units:
            if k in pages:
                return kind, pages
        return None

    os.makedirs(os.path.dirname(out_pdf), exist_ok=True)
    out = fitz.open()
    pdf = fitz.open(src["pdf"])
    for tok in a.pages.replace("，", ",").split(","):
        tok = tok.strip()
        if not tok:
            continue
        k = int(tok)
        if k not in man:
            print(f"p{k}: 超出课件范围（1–{len(man)}）")
            continue
        hit = unit_of(k)
        if hit is None:
            print(f"p{k}: 不在任何单元里")
            continue
        kind, pages = hit
        if kind == "skip":
            print(f"p{k}: 最终讲义里已 drop，没有可预览内容")
            continue
        if kind == "merge":
            x, y = pages
            notes = ann.get(x, {}).get("notes", []) + ann.get(y, {}).get("notes", [])
            d, info = assemble.merge_two(pdf, x, y, notes, src["head"], pm[x] + n_idx)
            label = f"p{x}+p{y}"
            print(f"{label}: 合并页 → 讲义 P{pm[x] + n_idx}")
        else:
            notes = ann.get(k, {}).get("notes", [])
            d, info = assemble.make_page(pdf, k, notes, src["head"],
                                         f"讲义 P{pm[k] + n_idx} · 原课件 P{k}")
            label = f"p{k}"
            print(f"p{k}: → 讲义 P{pm[k] + n_idx}  mode={info['mode']} "
                  f"fs={info['fs']} rect={info['rect']}")
        start = out.page_count
        out.insert_pdf(d)
        png = os.path.join(os.path.dirname(out_pdf), f"preview_{label.replace('+', '_')}.png")
        out[start].get_pixmap(dpi=a.dpi).save(png)
        print(f"    png {png}")

    out.save(out_pdf, garbage=4, deflate=True)
    print(f"{out.page_count} page(s) -> {out_pdf}")


if __name__ == "__main__":
    main()
