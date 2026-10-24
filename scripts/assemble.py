"""把批注写回原页面，生成成品 PDF。每页底部加一条极窄页脚（页码/原页号）。"""
import json, os
import pymupdf as fitz
import lib_layout as lib

FS_MAX = 15.5       # 批注最大尝试字号
FS_MIN = 8.4        # 低于此号宁可下延空白条
FOOT = 18           # 页脚高度
C_FOOT = (0.45, 0.45, 0.48)


MIN_W = 300         # 页内批注块最小宽度：低于此宁可下延空白条（避免塞窄缝）
FS_STRIP = 12.0     # 下延空白条的默认字号（条宽 912pt，能放大就放大）
INLINE_BONUS = 0.5  # 页内摆放的加分：同样字号优先写在页内（更像笔记）


def min_width(fs):
    return MIN_W


def _footer(pg, left, right, media_h):
    y = media_h - 6
    pg.draw_line(fitz.Point(20, y - 10), fitz.Point(pg.rect.width - 20, y - 10),
                 color=(0.85, 0.85, 0.88), width=0.5)
    pg.insert_text((20, y), left, fontname="CJK", fontfile=lib.FONT_PATH,
                   fontsize=6.4, color=C_FOOT)
    w = fitz.Font(fontfile=lib.FONT_PATH).text_length(right, 6.4)
    pg.insert_text((pg.rect.width - 20 - w, y), right, fontname="CJK",
                   fontfile=lib.FONT_PATH, fontsize=6.4, color=C_FOOT)


def fit_rect(page, notes, fs, rects=None, luma=None):
    """在页面里找一块能装下批注的空白区（按实际宽度重新折行后校验高度）。
    luma: 可选的矩形亮度查表函数（与字号无关，跨字号梯度复用）。"""
    best = None
    lead = fs * 1.36
    mw = min_width(fs)
    if rects is None:
        rects = lib.free_rects(page)
    for r in rects:
        w = r[2] - r[0]; h = r[3] - r[1]
        if w < mw or h < 40:
            continue
        bright = lib.rect_luma(page, r) if luma is None else luma(r)
        if bright < 232:
            continue
        lines, need = lib.layout_notes(notes, w - 4, fs, lead)
        if need + 6 <= h:          # 留 6pt 呼吸，别贴着原文
            asp = w / max(h, 1)
            score = w * h * (0.45 if asp < 1.8 else 1.0) * (0.85 if r[3] < 260 else 1.0)
            if r[1] < 90:            # 贴着页顶的条带像页眉，降权
                score *= 0.5
            if r[1] > 230:           # 页面下半部更像页边笔记
                score *= 1.15
            if best is None or score > best[0]:
                best = (score, r, lines)
    return best


def make_page(src, page_no, notes, head, foot_label):
    # 用新页 + show_pdf_page(clip=原页)，避免 set_mediabox 让内容整体下移、也避免溢出内容外露
    SRC = fitz.Rect(0, 0, 960, 540)

    def newdoc(H):
        d = fitz.open()
        pg = d.new_page(width=960, height=H)
        pg.show_pdf_page(SRC, src, page_no - 1, clip=SRC)
        return d, pg

    base_h = 540
    doc, p = newdoc(base_h + FOOT)
    _footer(p, head, foot_label, base_h + FOOT)
    mode, rect = "plain", None
    fs_used = None
    if notes:
        got = None
        rects = lib.free_rects(p)          # 只算一次，字号循环复用
        _lum = {}

        def luma(r, _p=p, _cache=_lum):
            """矩形亮度与字号无关：每页按矩形缓存一次，别在字号梯度里反复测。"""
            k = tuple(round(v, 1) for v in r)
            if k not in _cache:
                _cache[k] = lib.rect_luma(_p, r)
            return _cache[k]

        fs = FS_MAX
        while fs >= FS_MIN - 0.01:
            got = fit_rect(p, notes, fs, rects, luma)
            if got is not None:
                break
            fs = round(fs - 0.4, 2)
        # 页内能放的字号 + 加分 仍不如"下延条"大，就走下延条（宁可加一条空白，也不压小字）
        if got is not None and (fs + INLINE_BONUS) < FS_STRIP:
            got = None
        if got is not None:
            _, rect, lines = got
            mode, fs_used = "inline", fs
        else:
            fs_used = FS_STRIP
            lead = fs_used * 1.36
            strip_w = 760                       # 行宽别拉满整页，太长难读
            _, need = lib.layout_notes(notes, strip_w, fs_used, lead)
            extra = max(70, need + 24)
            doc, p = newdoc(base_h + extra + FOOT)
            _footer(p, head, foot_label, base_h + extra + FOOT)
            p.draw_line(fitz.Point(20, base_h + 8), fitz.Point(940, base_h + 8),
                        color=(0.62, 0.0, 0.06), width=1.0)
            rect = (24, base_h + 12, 24 + strip_w, base_h + extra + FOOT - 12)
            lines, _ = lib.layout_notes(notes, rect[2] - rect[0], fs_used, lead)
            mode = "strip"
        lib.draw_notes(p, rect, lines, fs_used, fs_used * 1.36)
    return doc, {"mode": mode, "fs": fs_used,
                 "rect": [round(v) for v in rect] if rect else None}


def merge_two(src, a, b, notes, head, pageno=None):
    out = fitz.open()
    H = 540 + FOOT
    pg = out.new_page(width=960, height=H)
    _footer(pg, head, ("讲义 P%d · 合并页（原 %d + 原 %d）" % (pageno, a, b)) if pageno else f"合并页（原 {a} + 原 {b}）", H)
    for k, pn in enumerate((a, b)):
        sub = fitz.open()
        sub.insert_pdf(src, from_page=pn - 1, to_page=pn - 1)
        dst = fitz.Rect(14 + k * 472, 12, 14 + k * 472 + 460, 12 + 259)
        pg.show_pdf_page(dst, sub, 0, clip=sub[0].rect)
        pg.draw_rect(dst, color=(0.80, 0.80, 0.84), width=0.6)
        pg.insert_text((dst.x0 + 3, dst.y1 + 10), f"原 {pn}", fontname="CJK",
                       fontfile=lib.FONT_PATH, fontsize=6.4, color=C_FOOT)
    if notes:
        fs = 11.6
        lines, h = lib.layout_notes(notes, 900, fs, fs * 1.36)
        lib.draw_notes(pg, (16, 292, 944, 532), lines, fs, fs * 1.36)
    return out, {"mode": "merged"}


def iter_units(man, ann):
    """按 drop / merge 规则给出输出单元顺序（不渲染）：('skip'|'merge'|'page', 页号元组)。"""
    done = set()
    for k in sorted(man):
        if k in done:
            continue
        a = ann.get(k, {})
        if a.get("drop"):
            yield "skip", (k,); done.add(k); continue
        nxt = ann.get(k + 1, {})
        if a.get("merge") == "next" and k + 1 in man and not nxt.get("drop") and (k + 1) not in done:
            yield "merge", (k, k + 1); done.add(k); done.add(k + 1); continue
        yield "page", (k,); done.add(k)


def page_map(man, ann):
    """交付页号映射（1 起，仅计非 drop 单元）。纯算术，不需要渲染整册。"""
    pm, n = {}, 0
    for kind, pages in iter_units(man, ann):
        if kind == "skip":
            continue
        n += 1
        for pn in pages:
            pm[pn] = n
    return pm


def build(manifest_path, ann_path, out_pdf, src_pdf, title_head, foot_offset=0):
    man = {r["n"]: r for r in json.load(open(manifest_path, encoding="utf-8"))}
    ann = {r["n"]: r for r in json.load(open(ann_path, encoding="utf-8"))["pages"]}
    src = fitz.open(src_pdf)
    out = fitz.open()
    page_map, skipped, merged, layout = {}, [], {}, {}
    n = 1
    for kind, pages in iter_units(man, ann):
        if kind == "skip":
            skipped.append(pages[0]); continue
        if kind == "merge":
            a, b = pages
            doc, _ = merge_two(src, a, b, ann.get(a, {}).get("notes", []) + ann.get(b, {}).get("notes", []),
                               title_head, foot_offset + n)
            page_map[a] = n; page_map[b] = n
            merged[a] = (a, b)
            out.insert_pdf(doc); n += 1; continue
        k = pages[0]
        doc, info = make_page(src, k, ann.get(k, {}).get("notes", []), title_head,
                              f"讲义 P{n + foot_offset} · 原课件 P{k}")
        layout[k] = info
        page_map[k] = n
        out.insert_pdf(doc); n += 1
    os.makedirs(os.path.dirname(out_pdf), exist_ok=True)
    out.subset_fonts()
    out.save(out_pdf, garbage=4, deflate=True, deflate_images=True,
            deflate_fonts=True, clean=True, use_objstms=1)
    meta = {"page_map": page_map, "skipped": skipped, "merged": merged,
            "layout": layout, "total": out.page_count}
    json.dump(meta, open(out_pdf.replace(".pdf", "_map.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(os.path.basename(out_pdf), "pages", out.page_count, "skipped", len(skipped),
          "merged", len(merged))
    return meta
