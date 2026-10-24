# courseware-annotator

Turn lecture slides (PPTX or PDF) into a **print-ready open-book exam handout**: every
original slide stays intact, Chinese study notes are written into each slide's own blank
areas like handwritten margin notes, administrative slides are dropped, near-trivial
neighbours are merged, and a knowledge-point index with correct page numbers is prepended.

```text
lecture-01.pptx ──► PDF ──► per-page manifest ──► annotations ──► handout PDF
                                                      │
                              cover · reading legend · knowledge-point index · keyword lookup
                              讲义 P12 · 原课件 P9          ← one landscape page per slide
```

- [SKILL.md](SKILL.md) — the full pipeline, the editorial rules, the 14 hard-won layout
  rules and the limits. This is the authoritative document; read it before running anything.
- `scripts/` — the pipeline (`prepare` → `slice` → `check` → `build` → `qa`, plus `preview`
  for single pages and front matter).
- `templates/` — the annotation spec handed to annotation sub-agents, and a `config.json`
  example.

## Why it exists

Most "summarise the slides" output is either a rewritten document that has lost the figures,
or notes stamped on top of the slide text so nothing is readable during the exam. This skill
keeps the slide as the unit of the page and treats the white space as the only place notes
may live. The rules in [SKILL.md](SKILL.md) were each bought with a real mistake:

| Trap | What goes wrong | What this skill does |
| --- | --- | --- |
| Growing the page with `set_mediabox()` | PyMuPDF re-anchors the content and the whole slide slides down | build a *new* page and `show_pdf_page(clip=src.rect)` |
| Notes on top of slide text | unreadable exactly when the reader needs it | ink test over every note span; a note on ink is a hard failure |
| Fixed-width text wrapping | the block silently overflows into the neighbouring content | wrap inside the rectangle actually chosen, then re-check the height |
| Shrinking to fit a narrow gap | notes end up smaller than the strip they replaced | inline only if `fs + 0.5 >= strip size`; otherwise append a red-ruled strip |
| Copying PowerPoint's overflow | hidden overflow is "revealed" in the appended strip | clip the source page at copy time |
| Uncompressed image streams | a 141-page deck stays at 668 MB | `deflate_images` + object streams + font subsetting → 11 MB |
| Front matter shifting page numbers | the index and the footer print the wrong page | page numbers planned arithmetically from drop/merge, content rendered once |
| Splitting CJK anywhere | `mRNA` becomes `mRN|A`, lines start with `。` | word tokens plus a 行首禁则 |
| Orphan characters in a wrapped title | 「加工」 splits into 「加|工」 | shrink the title 30 → 18 pt on one line, wrap only below that |

## What a page looks like

* the original slide, untouched, clipped to its own page box;
* Chinese annotations in the slide's blank areas, auto-sized per page (15.5 pt down to
  8.4 pt, largest size that really fits); if the page body cannot give ~11.5 pt, a red-ruled
  strip is appended below the slide and the notes go there at 12 pt;
* notes are tagged `★考点 / · 解释 / ▲易错 / ? 问法` and coloured (dark red / navy / brown /
  teal) so they read as notes, not as slide text;
* a hairline footer `讲义 P<n> · 原课件 P<m>` giving the handout page and the source page.

## Requirements

- Python 3.9+
- `pymupdf` (imported as `pymupdf`, also available as `fitz`)
- `python-pptx` — optional, only if you want text pulled from a PPTX
- PowerPoint — only for PPTX input; the conversion step drives PowerPoint COM
  (`scripts/pptx2pdf.ps1`, Windows). PDF input needs no conversion.

No LaTeX, no matplotlib, no headless browser.

## Install as a skill

Copy this directory into your skills folder, keeping the directory name:

```bash
# DeepSeek Harness
cp -r courseware-annotator ~/.dsh/skills/

# Claude-style skill folders
cp -r courseware-annotator ~/.claude/skills/
```

`SKILL.md` carries the frontmatter (`name`, `description`) the skill loaders expect. The
scripts also run standalone, without any skill host.

## Quick start

```bash
# 0. one-time: PPTX -> PDF (needs PowerPoint; on Windows a sandbox may need wider access)
pwsh -File scripts/pptx2pdf.ps1 -Src deck/lecture-01.pptx -Dst work/L1.pdf

# 1. per-page manifest + page images for the annotation agents
python scripts/prepare.py --pdf work/L1.pdf --out work/work_L1 --tag L1

# 2. split the manifest into batches for parallel annotation sub-agents
python scripts/slice.py --manifest work/work_L1/manifest_L1.json --out work/work_L1/batches --size 36

# 3. validate the annotations they wrote (coverage, note length vs page budget, labels)
python scripts/check.py --manifest work/work_L1/manifest_L1.json --ann "work/work_L1/ann_*.json"

# 4. preview pages while iterating — seconds, not minutes
python scripts/preview.py --config work/config.json --pages 17,42
python scripts/preview.py --config work/config.json --front

# 5. full build into output/
python scripts/build.py --config work/config.json

# 6. automated QA (ink under every note, footer/page consistency, index page numbers)
python scripts/qa.py --config work/config.json
```

Then look at 6–10 rendered pages. Automated checks cannot judge whether the notes read well.

## Repository layout

| Path | Purpose |
| --- | --- |
| `SKILL.md` | Skill definition, pipeline, editorial rules, hard-won rules, limits |
| `scripts/prepare.py` | PDF → per-page manifest (text, note character budget, page images) |
| `scripts/slice.py` | manifest → batch files for annotation sub-agents |
| `scripts/check.py` | validate annotation JSON (coverage, length, labels, drop/merge summary) |
| `scripts/build.py` | annotations + config → final handout PDFs |
| `scripts/preview.py` | render single pages or only the front matter, with the real page numbers |
| `scripts/qa.py` | ink test, footer/page-number consistency, index sanity |
| `scripts/assemble.py` | page composition: inline notes vs appended strip, merge-two-pages |
| `scripts/lib_layout.py` | blank-area detection, CJK wrapping, text fitting |
| `scripts/frontmatter.py` | cover, legend, knowledge-point index, keyword lookup |
| `scripts/pptx2pdf.ps1` | PPTX → PDF through PowerPoint COM |
| `templates/spec_template.md` | the annotation spec handed to sub-agents |
| `templates/config.example.json` | `config.json` example (sources, chapters, cover text, output paths) |

Run artifacts (`work/`, `out/`, `output/`, previews) are git-ignored.

## Outputs

- one landscape A4 PDF per source deck (for example `output/01_<course>_annotated_L1.pdf`);
- 3–6 A4-portrait front pages: cover, reading legend, knowledge-point index (page → what +
  keywords), and a cross-page keyword lookup when a keyword recurs on two or more pages;
- PDF bookmarks per chapter;
- the annotation JSON (`ann_*.json`) — keep it: re-running the layout with a different font
  policy is cheap only if the annotation content is reused.

Print advice: A4 landscape, duplex, "fit to page".

## Limits (read these)

- **Automated checks cannot judge aesthetics.** `qa.py` proves no note sits on slide ink and
  that page numbers are consistent; it cannot tell you the notes read well.
- **The editorial calls are judgement.** `drop` / `merge` / `supp` are per-deck decisions; a
  one-line section divider in one course is a content page in another.
- **The annotations are Chinese**, because the handouts this skill was built for are Chinese
  open-book exam material. The layout code is language-agnostic; only the fixed strings in
  `frontmatter.py` and the CJK font lookup are Chinese-specific.
- **The deck is reproduced, not improved.** The original slide is never edited, cropped or
  re-laid-out. If the source page is already wall-to-wall, its notes go in the appended strip.
- **Fewer than ~20 slides:** hand-write the notes; the pipeline overhead is not worth it.
- **Editable PowerPoint output is out of scope** — the deliverable is a printable PDF.

## License

MIT — see [LICENSE](LICENSE).
