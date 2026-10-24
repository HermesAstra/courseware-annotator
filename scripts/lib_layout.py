"""课件批注排版库：空白区域探测 + 中文批注书写。
页面尺寸 960x540pt。所有几何量单位为 pt。
"""
import pymupdf as fitz
import numpy as np
import re

import fonts

FONT_PATH = fonts.HEI
FONT_PATH_KAI = fonts.KAI

# 批注配色
C_KP = (0.63, 0.0, 0.06)      # 考点 深红
C_EXP = (0.06, 0.19, 0.38)    # 解释 深蓝
C_WARN = (0.55, 0.30, 0.0)    # 易错 棕
C_ASK = (0.0, 0.33, 0.30)     # 问法 墨绿
C_PLAIN = (0.15, 0.15, 0.15)
COLORS = {"考点": C_KP, "解释": C_EXP, "易错": C_WARN, "问法": C_ASK, "注": C_PLAIN}
LABEL = {"考点": "★考点 ", "解释": "· ", "易错": "▲易错 ", "问法": "? 问法 ", "注": "· "}


def grid_occupancy(page, cell=12.0, dark=250, ratio=0.004):
    """返回 (nx, ny) 布尔占位网格，True=有内容。cell 单位 pt。"""
    r = page.rect
    pm = page.get_pixmap(dpi=72, colorspace=fitz.csGRAY)
    img = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.height, pm.width)
    h, w = img.shape
    nx = int(np.ceil(w / cell)); ny = int(np.ceil(h / cell))
    occ = np.zeros((ny, nx), dtype=bool)
    darkmask = img < dark
    for j in range(ny):
        y0, y1 = int(j * cell), min(int((j + 1) * cell), h)
        for i in range(nx):
            x0, x1 = int(i * cell), min(int((i + 1) * cell), w)
            if darkmask[y0:y1, x0:x1].mean() > ratio:
                occ[j, i] = True
    return occ, w, h


def free_rects(page, cell=12.0, minw=110, minh=60, pad=8):
    """列出可写批注的空白矩形（pt），按面积降序。
    做法：按行带 [j0,j1] 求最长连续空白列，即"横向书写带"，速度快。"""
    occ, w, h = grid_occupancy(page, cell)
    ny, nx = occ.shape
    out = []
    for j0 in range(ny):
        run = np.ones(nx, dtype=bool)
        for j1 in range(j0, ny):
            run &= ~occ[j1]
            if not run.any():
                break
            hh = (j1 - j0 + 1) * cell
            if hh < minh:
                continue
            # 最长连续 True 段
            d = np.diff(np.concatenate(([0], run.astype(np.int8), [0])))
            starts = np.where(d == 1)[0]
            ends = np.where(d == -1)[0]
            for s, e in zip(starts, ends):
                ww = (e - s) * cell
                if ww < minw:
                    continue
                x0 = s * cell + pad; y0 = j0 * cell + pad
                x1 = min(e * cell, w) - pad; y1 = min((j1 + 1) * cell, h) - pad
                if x1 - x0 >= minw and y1 - y0 >= minh:
                    out.append((x0, y0, x1, y1))
    rects = sorted(out, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]), reverse=True)
    return rects[:400]


def fit_score(rect, need_w, need_h):
    """矩形是否能装下内容（含 10% 余量），返回可用性。"""
    w = rect[2] - rect[0]; h = rect[3] - rect[1]
    return w >= need_w and h >= need_h


def rect_luma(page, rect, dpi=72):
    """矩形区域平均亮度（0-255），用于排除彩色底纹。"""
    clip = fitz.Rect(rect)
    pm = page.get_pixmap(dpi=dpi, clip=clip, colorspace=fitz.csGRAY)
    a = np.frombuffer(pm.samples, dtype=np.uint8)
    return float(a.mean()) if a.size else 255.0


def capacity(rect, fs=8.6, leading=11.6):
    """矩形能容纳的汉字数（估算）。"""
    w = rect[2] - rect[0]; h = rect[3] - rect[1]
    cpl = max(1, int(w / fs))
    nl = max(0, int(h / leading))
    return cpl, nl, cpl * nl


def pick_rect(page, need_h, min_w=200, prefer="auto"):
    """选一个能装下 need_h 高、宽度合理的空白区；无合适则 None。"""
    best = None; best_score = -1
    for r in free_rects(page):
        w = r[2] - r[0]; h = r[3] - r[1]
        if w < min_w or h < need_h:
            continue
        if rect_luma(page, r) < 232:      # 底纹太深，写了看不清
            continue
        asp = w / max(h, 1)
        score = w * h
        if asp < 1.2:            # 太窄高的条状，阅读体验差
            score *= 0.35
        elif asp < 2:
            score *= 0.75
        elif asp > 7:
            score *= 0.8
        if r[3] < 260:           # 偏上的区域优先级略低（下方更像页边笔记）
            score *= 0.85
        if score > best_score:
            best_score = score; best = r
    return best


NO_LINE_START = "，。、；：？！）】》」』’”%,.;:?!)]}"

# 一个"不可拆"单元：拉丁字母/数字词（含内部 - ' . /）、空白串、或单个汉字/标点
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-'’/\.]*|\s+|.", re.S)


def wrap_cjk(text, width, fs, font):
    """按宽度折行（中英混排）。
    - 拉丁词整体不拆（mRNA 不会被断成 mRN|A），超长词才退回逐字拆；
    - 行首禁则：标点挂在前一行末，不另起一行；
    - 断行处的空格丢弃，不留在行首。"""
    tokens = _TOKEN.findall(text)
    lines, cur = [], ""

    def fits(s):
        return font.text_length(s, fs) <= width

    def hard_split(tok):
        """超长单词：按字符尽量填满一行。"""
        out, rest = [], tok
        while not fits(rest):
            k = len(rest)
            while k > 1 and not fits(rest[:k]):
                k -= 1
            out.append(rest[:k]); rest = rest[k:]
        return out, rest

    for tok in tokens:
        if tok.isspace():
            if cur and not cur.endswith(" "):
                if fits(cur + " "):
                    cur += " "
            continue
        cand = cur + tok
        if fits(cand):
            cur = cand
            continue
        if not cur.strip():
            parts, cur = hard_split(tok)
            lines.extend(parts)
            continue
        if tok[0] in NO_LINE_START:          # 标点不另起一行
            lines.append(cand.rstrip()); cur = ""
            continue
        lines.append(cur.rstrip()); cur = tok
    if cur.strip():
        lines.append(cur.rstrip())
    return lines


def layout_notes(notes, width, fs=8.6, leading=11.6):
    """把 notes 排成行序列 [(type, text, indent)]，返回 (lines, height)。
    notes: [{"t": "考点"/"解释"/"易错"/"问法", "s": "..."}]"""
    font = fitz.Font(fontfile=FONT_PATH)
    lines = []
    for n in notes:
        t = n.get("t", "解释"); s = n["s"].strip()
        head = LABEL.get(t, "· ")
        indent = 0.0
        wrapped = wrap_cjk(head + s, width, fs, font)
        for k, ln in enumerate(wrapped):
            lines.append((t, ln, indent))
        lines.append(None)  # 段间空行
    if lines and lines[-1] is None:
        lines.pop()
    return lines, len(lines) * leading


def draw_notes(page, rect, lines, fs=8.6, leading=11.6, fontfile=FONT_PATH):
    x0, y0 = rect[0], rect[1]
    y = y0 + fs
    fontname = "NoteCJK"
    for ln in lines:
        if ln is None:
            y += leading * 0.45
            continue
        t, text, ind = ln
        page.insert_text((x0 + ind, y), text, fontname=fontname, fontfile=fontfile,
                         fontsize=fs, color=COLORS.get(t, C_PLAIN), render_mode=0)
        y += leading
    return y
