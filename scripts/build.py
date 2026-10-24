#!/usr/bin/env python
"""Build the handout PDFs from a config file.

    python build.py --config work/config.json
"""
import argparse, glob, json, os, sys

import pymupdf as fitz

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import assemble
import frontmatter


def load_ann(pattern):
    ann = {}
    for p in sorted(glob.glob(pattern)):
        for r in json.load(open(p, encoding="utf-8"))["pages"]:
            ann[r["n"]] = r
    # normalise merge="prev" into "next" on the previous page, merging notes
    for n in sorted(ann):
        a = ann[n]
        if a.get("merge") == "prev" and (n - 1) in ann:
            prev = ann[n - 1]
            if prev.get("merge") in (None, "none"):
                prev["merge"] = "next"
            prev["notes"] = list(prev.get("notes", [])) + list(a.get("notes", []))
            a["notes"] = []
            a["merge"] = "none"
    return ann


def chapter_of(chapters, n):
    for name, a, b in chapters:
        if a <= n <= b:
            return name
    return "其他"


def front_doc(src, ann, pm):
    """返回 front(offset) -> 前置页 doc。offset = 内容首页之前的页数。
    只排版不渲染内容页，所以很便宜；preview.py 也复用它来算真实页脚页号。"""
    chapters = src["chapters"]
    rows = []
    for n in sorted(pm):
        a = ann.get(n, {})
        if not a.get("title"):
            continue
        rows.append((chapter_of(chapters, n), a["title"], a.get("kp") or [], pm[n]))

    def front(offset):
        d = fitz.open()
        frontmatter.cover(d, src["title"], src["sub"], src.get("cover_bullets", []),
                          src.get("course", ""))
        frontmatter.legend(d)
        frontmatter.index_pages(d, rows, offset, "知识点索引（页码＝本 PDF 页号）", chapters)
        frontmatter.keyword_pages(d, rows, offset, "跨页关键词速查")
        return d
    return front


def build_one(src, scratch, out_pdf):
    tag = src["tag"]
    ann = load_ann(os.path.join(scratch, src["ann_glob"]))
    merged = os.path.join(scratch, f"out/ann_{tag}.json")
    os.makedirs(os.path.dirname(merged), exist_ok=True)
    json.dump({"pages": [ann[k] for k in sorted(ann)]},
              open(merged, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    content = os.path.join(scratch, f"out/content_{tag}.pdf")
    head = src["head"]
    manifest = os.path.join(scratch, src["manifest"])
    man = {r["n"]: r for r in json.load(open(manifest, encoding="utf-8"))}
    # 页号只取决于 drop / merge，先算出来；不必为了拿页数把整册渲染一遍
    pm = assemble.page_map(man, ann)
    chapters = src["chapters"]
    front = front_doc(src, ann, pm)

    probe = front(0)
    n_idx = probe.page_count
    probe.close()
    meta = assemble.build(manifest, merged, content, src["pdf"], head, foot_offset=n_idx)
    if {int(k): v for k, v in meta["page_map"].items()} != pm:
        raise SystemExit("page_map mismatch between planner and build")
    doc = front(n_idx)

    out = fitz.open()
    out.insert_pdf(doc)
    out.insert_pdf(fitz.open(content))
    toc = [[1, "封面与使用说明", 1]]
    for name, _, _ in chapters:
        first = None
        for n in sorted(pm):
            if chapter_of(chapters, n) == name:
                first = pm[n] + n_idx
                break
        if first:
            toc.append([1, name, first])
    out.set_toc(toc)
    out.set_metadata({"title": f"{src['course']} · {src['title']} · 复习批注版",
                      "author": src.get("author", ""),
                      "subject": "开卷复习材料"})
    out.subset_fonts()
    os.makedirs(os.path.dirname(out_pdf), exist_ok=True)
    out.save(out_pdf, garbage=4, deflate=True, deflate_images=True,
             deflate_fonts=True, clean=True, use_objstms=1)
    print(f"{os.path.basename(out_pdf)}: content {meta['total']} + front {n_idx} "
          f"= {out.page_count} pages")
    return out.page_count


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--only", default=None, help="build only this tag")
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8"))
    scratch = cfg["scratch"]
    outdir = cfg["output_dir"]
    for src in cfg["sources"]:
        if a.only and src["tag"] != a.only:
            continue
        build_one(src, scratch, os.path.join(outdir, src["out"]))
