"""生成索引/封面页（A4 纵向），并拼到成品 PDF 前面。"""
import json
import os
import sys

import pymupdf as fitz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fonts
import lib_layout as lib

FONT = fonts.HEI
FONTK = fonts.KAI
A4W, A4H = 595.0, 842.0
INK = (0.10, 0.10, 0.12)
BLUE = (0.0, 0.25, 0.45)
RED = (0.63, 0.0, 0.06)
GRAY = (0.42, 0.42, 0.45)


NO_LINE_START = "，。、；：？！）】》」』’”%,.;:?!)]}"


def _wrap(text, width, fs, font):
    """与批注正文共用同一套折行实现（拉丁词不拆、标点不落行首）。"""
    return lib.wrap_cjk(text, width, fs, font) or [""]


def fit_title(text, width, fs_max=30.0, fs_min=18.0):
    """封面标题排版：先缩字号把标题压成一行，压不下去才折行。

    直接按宽度折行会把「加工」拆成「加 / 工」这种两字词断行，很难看；
    标题只有一行最好看，所以宁可把字号从 30 降到 18 换一行。真的折行时，
    末行只剩一个汉字就把上一行最后一个汉字挪下来，避免孤字成行。
    返回 (字号, 行列表)。"""
    font = fitz.Font(fontfile=FONT)
    fs = fs_max
    while fs > fs_min and font.text_length(text, fs) > width:
        fs -= 0.5
    if font.text_length(text, fs) <= width:
        return fs, [text]
    fs = fs_min
    lines = _wrap(text, width, fs, font)
    if len(lines) >= 2 and len(lines[-1].strip()) == 1 and len(lines[-2]) > 2:
        prev = lines[-2]
        if "\u4e00" <= prev[-1] <= "\u9fff":
            lines[-2] = prev[:-1].rstrip()
            lines[-1] = prev[-1] + lines[-1]
    return fs, lines


def cover(doc, title, sub, bullets, course=""):
    p = doc.new_page(width=A4W, height=A4H)
    p.draw_rect(fitz.Rect(0, 0, A4W, 8), color=None, fill=BLUE)
    y = 120
    p.insert_text((56, y), course, fontname="CJK", fontfile=FONT,
                  fontsize=13, color=GRAY)
    y += 46
    fs, tl = fit_title(title, A4W - 112, 30, 18)
    for ln in tl:
        p.insert_text((56, y), ln, fontname="CJK", fontfile=FONT, fontsize=fs, color=INK)
        y += fs * 1.35
    y += 6
    p.insert_text((56, y), sub, fontname="CJK", fontfile=FONT, fontsize=13, color=BLUE)
    y += 30
    p.draw_line(fitz.Point(56, y), fitz.Point(A4W - 56, y), color=RED, width=1.2)
    y += 34
    for b in bullets:
        for i, ln in enumerate(_wrap(b, A4W - 130, 10.5, fitz.Font(fontfile=FONTK))):
            p.insert_text((56, y), ln, fontname="CJK", fontfile=FONTK, fontsize=10.5, color=INK)
            y += 17
        y += 6
    p.insert_text((56, A4H - 50), "本材料为课程课件 + 中文批注，供开卷考试查阅；课件原文内容未作删改。",
                  fontname="CJK", fontfile=FONTK, fontsize=8.5, color=GRAY)
    return p


def legend(doc):
    p = doc.new_page(width=A4W, height=A4H)
    p.insert_text((56, 80), "批注阅读说明", fontname="CJK", fontfile=FONT, fontsize=19, color=INK)
    y = 130
    items = [
        ("★考点", RED, "必须记住的硬知识：定义、分类、数值、顺序、谁结合谁。"),
        ("· 解释", BLUE, "这页图/机制在讲什么，用白话讲清楚，帮助理解而不必死背。"),
        ("▲易错", (0.55, 0.30, 0.0), "最容易混淆、最可能被扣分的地方（名词相近、方向相反、角色易混之处）。"),
        ("? 问法", (0.0, 0.33, 0.30), "老师可能的出题角度，看到就知道该往哪儿想。"),
    ]
    for tag, col, desc in items:
        p.insert_text((56, y), tag, fontname="CJK", fontfile=FONT, fontsize=12, color=col)
        for i, ln in enumerate(_wrap(desc, A4W - 260, 10, fitz.Font(fontfile=FONTK))):
            p.insert_text((170, y + i * 15), ln, fontname="CJK", fontfile=FONTK,
                          fontsize=10, color=INK)
        y += 62
    y += 10
    notes = [
        "页面底部若有「批注」分隔线，表示该页原图无空白处，批注写在页面下延的空白条里。",
        "标注「补充·选读」的页是老师指定的参考资料，了解即可，不是必背考点。",
        "两页并排、下方注「原 N」的页，是把信息量很少的相邻页合并，原内容完整保留。",
        "索引里的页码就是本 PDF 的页号（右上角所示），按页号直接翻。",
        "打印建议：A4 横向、双面、缩放「适合页面」，批注字号 8.4–15.5pt（打印缩放后约 7–13pt），可清晰阅读。",
    ]
    p.insert_text((56, y + 10), "几点说明", fontname="CJK", fontfile=FONT, fontsize=13, color=INK)
    y += 34
    for t in notes:
        for ln in _wrap("· " + t, A4W - 130, 10, fitz.Font(fontfile=FONTK)):
            p.insert_text((56, y), ln, fontname="CJK", fontfile=FONTK, fontsize=10, color=INK)
            y += 16
        y += 4
    return p


def index_pages(doc, rows, offset, title, chapters):
    """rows: [(chapter, title, kps, page)]；offset=内容首页的绝对页号-1"""
    font = fitz.Font(fontfile=FONT)
    fk = fitz.Font(fontfile=FONTK)
    fs = 8.2
    x0, x1 = 46, A4W - 40
    top, bottom = 96, A4H - 46
    y = 0
    p = None
    cur_ch = None

    def new_page(first=False):
        np_ = doc.new_page(width=A4W, height=A4H)
        np_.insert_text((x0, 62), title, fontname="CJK", fontfile=FONT, fontsize=16, color=INK)
        np_.draw_line(fitz.Point(x0, 72), fitz.Point(x1, 72), color=RED, width=1.0)
        hy = 88
        np_.insert_text((x0, hy), "这一页讲什么", fontname="CJK", fontfile=FONT, fontsize=8.6, color=GRAY)
        np_.insert_text((x0 + 205, hy), "本页知识点（关键词）", fontname="CJK", fontfile=FONT, fontsize=8.6, color=GRAY)
        np_.insert_text((x1 - 34, hy), "页", fontname="CJK", fontfile=FONT, fontsize=8.6, color=GRAY)
        np_.draw_line(fitz.Point(x0, hy + 4), fitz.Point(x1, hy + 4), color=GRAY, width=0.5)
        return np_, 104

    p, y = new_page(True)
    for ch, ttl, kps, pg in rows:
        if ch != cur_ch:
            if y + 26 > bottom:
                p, y = new_page()
            cur_ch = ch
            y += 8
            p.insert_text((x0, y), ch, fontname="CJK", fontfile=FONT, fontsize=10, color=BLUE)
            y += 6
            p.draw_line(fitz.Point(x0, y), fitz.Point(x1, y), color=(0.8, 0.85, 0.9), width=0.6)
            y += 12
        kw = "、".join(kps)
        klines = _wrap(ttl, 190, fs + 0.4, fk)
        tlines = _wrap(kw, x1 - 22 - 250, fs - 0.3, fk)
        h = max(len(klines), len(tlines)) * 11 + 3
        if y + h > bottom:
            p, y = new_page()
        for i, ln in enumerate(klines):
            p.insert_text((x0, y + i * 11), ln, fontname="CJK", fontfile=fk,
                          fontsize=fs + 0.4, color=INK)
        for i, ln in enumerate(tlines):
            p.insert_text((x0 + 205, y + i * 11), ln, fontname="CJK", fontfile=fk,
                          fontsize=fs - 0.3, color=(0.30, 0.30, 0.33))
        p.insert_text((x1 - 22, y), str(pg + offset), fontname="CJK", fontfile=fk,
                      fontsize=fs, color=BLUE)
        y += h
    return


def keyword_pages(doc, rows, offset, title):
    """跨页关键词速查：只收出现在 2 页以上的知识点关键词，三栏排版。"""
    from collections import defaultdict
    m = defaultdict(set)
    for ch, ttl, kps, pg in rows:
        for k in kps:
            k = k.strip()
            if k:
                m[k].add(pg)
    items = sorted([(k, sorted(v)) for k, v in m.items() if len(v) >= 2],
                   key=lambda x: (-len(x[1]), x[0]))
    if not items:
        return
    fk = fitz.Font(fontfile=FONTK)
    fs = 8.4
    x0, x1 = 46, A4W - 40
    colw = (x1 - x0) / 2
    top, bottom = 104, A4H - 44
    per_col = int((bottom - top) // 13.5)
    per_page = per_col * 2
    first = True
    for off in range(0, len(items), per_page):
        chunk = items[off:off + per_page]
        p = doc.new_page(width=A4W, height=A4H)
        ttl = title if first else title + "（续）"
        first = False
        p.insert_text((x0, 62), ttl, fontname="CJK", fontfile=FONT, fontsize=16, color=INK)
        p.draw_line(fitz.Point(x0, 72), fitz.Point(x1, 72), color=RED, width=1.0)
        if off == 0:
            p.insert_text((x0, 90), "同一知识点出现在多页时按出现次数列出；页码＝本 PDF 页号。",
                          fontname="CJK", fontfile=fk, fontsize=8.6, color=GRAY)
        ncol = 2
        per = -(-len(chunk) // ncol)
        for idx, (k, pgs) in enumerate(chunk):
            c, r = divmod(idx, per)
            cx = x0 + c * colw
            cy = top + r * 13.5
            p.insert_text((cx, cy), k, fontname="CJK", fontfile=fk, fontsize=fs, color=INK)
            p.insert_text((cx + 105, cy), "、".join(str(x + offset) for x in pgs),
                          fontname="CJK", fontfile=fk, fontsize=fs - 0.6, color=BLUE)
