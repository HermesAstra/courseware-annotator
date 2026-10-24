"""Locate the CJK fonts used for annotations and front matter.

Windows ships SimHei / SimKai; macOS has PingFang / STKaiti; Linux usually has
Noto CJK or WenQuanYi. Override either face with ``COURSEWARE_FONT_HEI`` /
``COURSEWARE_FONT_KAI`` (path to a .ttf / .ttc file).
"""
import os
import sys

_CANDIDATES = {
    "HEI": ("COURSEWARE_FONT_HEI", [
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\Deng.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]),
    "KAI": ("COURSEWARE_FONT_KAI", [
        r"C:\Windows\Fonts\simkai.ttf",
        r"C:\Windows\Fonts\STKAITI.TTF",
        "/System/Library/Fonts/STKaiti.ttf",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc",
        "/usr/share/fonts/truetype/arphic/ukai.ttc",
    ]),
}


def _resolve(env, candidates):
    explicit = os.environ.get(env, "")
    for path in ([explicit] if explicit else []) + candidates:
        if path and os.path.isfile(path):
            return path
    return ""


HEI = _resolve(*_CANDIDATES["HEI"])
KAI = _resolve(*_CANDIDATES["KAI"]) or HEI

if not HEI:
    sys.exit("courseware-annotator: no CJK font found. Install one (for example Noto Sans CJK) "
             "or set COURSEWARE_FONT_HEI / COURSEWARE_FONT_KAI to a .ttf/.ttc file.")
