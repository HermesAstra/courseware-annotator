---
name: courseware-annotator
description: >
  Turn lecture slides (PPTX or PDF) into a print-ready open-book exam handout:
  every original slide stays intact, Chinese study annotations are placed into
  each slide's own empty areas (like handwritten notes), administrative slides
  are dropped, near-trivial neighbours are merged, and a knowledge-point index
  with correct page numbers is prepended. Use when the user asks to annotate
  courseware, summarise + annotate a slide deck for an exam, build a printable
  revision handout (纸质复习材料 / 开卷考试材料), add per-page Chinese notes to a
  PDF lecture, or "把课件做成能打印的复习讲义". Also use when re-running such a
  job for the next lectures of the same course.
---

# courseware-annotator

Turn a lecture deck (PPTX or PDF) into a printable open-book exam handout: every original
slide is kept as-is, Chinese study notes are written into each slide's own blank areas, and
a knowledge-point index with correct page numbers is prepended.

The pipeline is fully scripted and reproducible. The *editorial* decisions — which
administrative slides to drop, how to phrase each note — are model judgement, so review a
sample of pages before shipping a batch. See **Limits** at the end of this file.

---

## What you get

Three to six A4-portrait front-matter pages + one landscape PDF page per source slide:

* original slide copied in, untouched, clipped to its own page box;
* Chinese annotations written **into the slide's empty areas**, auto-sized per page:
  the layout tries 15.5 pt down to 8.4 pt and keeps the largest size that really fits;
  if the page body cannot give at least ~11.5 pt, a red-ruled blank strip is appended
  below the slide and the notes go there at 12 pt on a 760 pt measure;
* a hairline footer `讲义 P<n> · 原课件 P<m>` giving the handout page and the source page;
* front matter: cover, reading legend, knowledge-point index (page → what + keywords),
  cross-page keyword lookup (shown only when a keyword recurs on two or more pages);
  PDF bookmarks per chapter.

Annotations are tagged `★考点 / · 解释 / ▲易错 / ? 问法` and coloured
(dark red / navy / brown / teal) so they read as notes, not as slide text.

---

## Pipeline

Work in a scratch dir, e.g. `<workspace>/agent/tmp/<course>/`. All scripts live in
`scripts/` next to this file; they only need `pymupdf` (+ `python-pptx` if the source is
a PPTX and you want text without rendering).

```bash
S=<skill_dir>/scripts          # this skill's scripts dir
W=<scratch dir>                # per-course working dir
```

### 1. Normalise sources to PDF

```bash
# PPTX -> PDF needs PowerPoint COM, which the Windows sandbox blocks (0x80070005).
# Run pptx2pdf.ps1 once with sandbox_permissions=danger-full-access.
pwsh -File $S/pptx2pdf.ps1 -Src "C:\path\deck.pptx" -Dst "$W/L12.pdf"
```

PDF input needs no conversion. Every deck becomes a 960×540 pt PDF with vector text —
that uniformity is what the rest of the pipeline assumes.

### 2. Build the per-page manifest

```bash
python $S/prepare.py --pdf "$W/L12.pdf" --out "$W/work_L12" --tag L12
```

Produces `manifest_L12.json` (page number, extracted text, annotation character budget
`cap`, thumbnail path) and `pages/pNNN.png` at 90 dpi.

### 3. Slice the manifest and dispatch annotation sub-agents

```bash
python $S/slice.py --manifest "$W/work_L12/manifest_L12.json" --out "$W/work_L12/batches" --size 36
```

Give each sub-agent: `SPEC.md` (from `templates/spec_template.md`), one batch file, and the
section context (what this page range is about). They read the page images with
`read_image`, then write `ann_<a>_<b>.json`. See *Editorial rules* below.

### 4. Validate the annotation JSON

```bash
python $S/check.py --manifest ... --ann "$W/work_L12/ann_*.json"
```

Checks coverage (every page present), `notes` length vs `cap`, title/label sanity,
and prints the drop / merge / supplemental summary.

### 5. Build

```bash
python $S/build.py --config "$W/config.json"
```

`config.json` (see `templates/config.example.json`) lists the sources, chapter ranges,
cover text and output paths. This writes the final PDFs into `output/`.

`build.py` takes a couple of minutes for a 60-page deck, so **do not rebuild the deck to
check one page**. Iterate with the preview instead:

```bash
python $S/preview.py --config "$W/config.json" --pages 17,42
```

It renders only those pages (a few seconds each), writes `preview_pNNN.png` next to the
PDF for `read_image`, and prints the layout decision (`mode=inline|strip`, `fs`, `rect`).
The footer already carries the *real* final page number, so what you see is what ships;
run the full `build.py` once, after the annotations and the per-page layout are settled.

Front matter has its own preview — use it after editing the cover text, the chapter ranges
or the cover bullets, **before** paying for a full build:

```bash
python $S/preview.py --config "$W/config.json" --front
```

It renders cover / legend / index / keyword pages only (~2.5 s), writes `front_pNNN.png`
for `read_image`, and prints the real page on which the content starts. The index uses the
real offset, so the page numbers in it are exactly what the final PDF will print.


### 6. QA

```bash
python $S/qa.py --config "$W/config.json"
```

* ink test: for every note span, is there original ink underneath? Must be 0 pages;
* footer/page-number consistency: `讲义 P<n>` must equal the real page index;
* index page numbers must be ≤ page count.

Then render 6–10 sample pages (`pymupdf ... get_pixmap(dpi=95)`) and *look* at them:
font size, placement, merged pages, strip pages. Automated checks cannot judge aesthetics.

### 7. Hand over

Report: page counts (source → dropped → merged → final), where the files are, print
advice (A4 landscape, duplex, "fit to page"), and what the handout does **not** cover.

---

## Editorial rules (what goes in the annotation JSON)

Per page: `{"n", "title", "kp", "supp", "drop", "merge", "notes"}`

* `drop: true` — only for: clicker/voting/attendance pages, course schedule/syllabus,
  grading and reporting rules, group-assignment lists, TA/lecturer self-intro, bare
  covers, pure table-of-contents pages.
* `merge: "next"|"prev"` — only for pages with essentially no content (one-line section
  divider, a copyright line, a single caption). Two pages are then shown side by side on
  one handout page and their notes merged.
* `supp: true` — teacher-marked supplemental/reference pages (for example, a coloured
  background the lecturer uses for "not examinable"). Keep them, annotate with one "选读"
  line, never with 考点.
* `notes` — 2–4 items, 80–180 characters total, `t` ∈ 考点 / 解释 / 易错 / 问法.
  Write for someone flipping to this page during an open-book exam: definition,
  direction of regulation, the one thing people mix up, and how it might be asked.
* `title` / `kp` feed the index — every `kp` must name a knowledge point. Meta words such
  as 「设问」「重复页」 end up in the reader's keyword lookup and are useless there; and a
  note must never describe the booklet's own layout ("排版时并入上一页").

---

## Hard-won rules (do not relearn these)

1. **Never `set_mediabox()` to grow a page.** PyMuPDF re-anchors the existing content and
   the whole slide slides down by the added height. Build a *new* page and
   `show_pdf_page(dst, src, n, clip=src.rect)` instead — that also clips PowerPoint's
   overflow, which otherwise gets "revealed" in the appended strip.
2. **`save(deflate=True)` does not compress image streams.** A 141-page deck went from
   668 MB to 11 MB only after `deflate_images=True, use_objstms=1, subset_fonts(), clean=True`.
3. **Blank-area detection:** grid = 12 pt cells, ink threshold `gray < 250`, cell
   occupancy ratio `0.004`. The looser `245 / 0.012` misses thin light-blue italic text
   and the notes end up on top of it.
4. **Never wrap text at a fixed width.** Wrap inside the rectangle you actually picked and
   re-check the height; otherwise the block silently overflows into neighbouring content.
5. **Do not shrink the font to squeeze into a narrow gap.** Require block width ≥ 300 pt.
   The size ladder alone is not enough: an early version took the *first* size that fitted
   anywhere, which let pages fall into narrow columns at 8.4 pt — smaller than the strip
   they replaced. Decide by comparing the two options instead: compute the largest inline
   size `fs` and the strip size, place inline only if `fs + 0.5 >= strip_size` (12 pt),
   otherwise append the strip. Leave ≥ 6 pt of breathing room between notes and slide text.
6. **Cache `free_rects()` per page.** It does not depend on font size; recomputing it inside
   the size ladder makes the build 10× slower.
7. **Front matter shifts page numbers.** The index and the footer both need the *absolute*
   page number. That number is a pure function of drop/merge, so `assemble.page_map()` plans
   it arithmetically and the content is rendered **once**, with `foot_offset = front_page_count`
   (only the front matter itself is laid out twice, and it is text-only). Do not go back to
   "render the whole deck once just to learn the page count" — it doubled build time.
8. **Trust pixels, not rectangles, for the overlap check.** Geometric checks flag image
   bounding boxes with transparent padding and unfilled frames; the ink test does not.
9. **PowerPoint COM is blocked in the sandbox** (`0x80070005`); the single conversion step
   needs `danger-full-access`. Everything else runs confined.
10. **Q: why do sub-agents?** They isolate ~140 pages of images from the main context and
    run the batches in parallel. Total tokens go up, wall-clock and main-context go down.
11. **Cost is per-page pixel work, not page count.** `rect_luma()` renders a pixmap per rect;
    the font-size ladder used to ask for the *same* rect dozens of times (366 luma calls on one
    page). Cache luma per rect per page and the deck builds in half the time. For single-page
    iteration use `preview.py --pages N` (seconds), never a full `build.py` — the layout is
    deterministic, so a previewed page is what ships.
12. **CJK wrapping needs word tokens and a 行首禁则.** Per-character greedy wrapping splits
    Latin terms (`mRNA` → `mRN|A`), leaves a space at the start of the next line, and happily
    starts a line with `。` `，`. `wrap_cjk()` now tokenises Latin words as units, drops the
    break-space, and lets closing punctuation hang on the previous line. `frontmatter._wrap()`
    delegates to it so front matter and notes cannot drift apart.
13. **Cover titles: shrink the font before wrapping.** `frontmatter.fit_title()` steps the
    title from 30 pt down to 18 pt and keeps the largest size that still fits on one line;
    it only wraps below 18 pt, and a wrapped last line never keeps a single orphan
    character (it borrows one from the line above). Reason: width-only wrapping split
    「加工」 into 「加|工」 — CJK can break between any two characters, so the wrapper has no
    idea where a word ends. A 510 pt title becomes 28 pt on one line instead.
14. **Preview the front matter separately — it costs 2.5 s, not 2 min.** `preview.py --front`
    renders only the cover / legend / index / keyword pages, with the real page offset, and
    its text is identical to what `build.py` ships (checked page by page on the RNA deck:
    all 5 front pages matched exactly). Settle every front-matter string (title, cover
    bullets, chapter names) with `--front` before spending a full build on it.

---

## Files after a run

```
W/
  L12.pdf                     normalised source
  work_L12/manifest_L12.json  per-page text + cap + thumbnails
  work_L12/pages/pNNN.png     page images for the sub-agents
  work_L12/ann_*.json         annotations (editorial output, worth keeping)
  out/content_L12.pdf         slides + notes (intermediate, large)
  config.json
output/
  01_<course>_annotated_L1-2.pdf
  02_<course>_annotated_L3-4.pdf
```

Keep `ann_*.json`: re-running layout with a different font policy is cheap only if the
annotation content is reused.

## Limits (read these)

* **Automated checks cannot judge aesthetics.** `qa.py` proves that no note sits on top of
  slide ink and that page numbers are consistent; it cannot tell you whether the notes read
  well. Render 6–10 sample pages and look at them before delivering.
* **Editorial calls are judgement.** `drop` / `merge` / `supp` are per-deck decisions: a
  one-line section divider in one course is a content page in another. Skim the index of the
  finished handout — it lists exactly what was kept.
* **The annotations are Chinese**, because the handouts this skill was built for are Chinese
  open-book exam material. The layout code itself is language-agnostic; only the fixed
  strings in `frontmatter.py` and the CJK font lookup are Chinese-specific.
* **The deck is reproduced, not improved.** Notes go into blank space; the original slide is
  never edited, cropped or re-laid-out. If a slide is already wall-to-wall, its notes land in
  the strip appended below the slide.
* **PPTX input needs PowerPoint** for the single conversion step (`pptx2pdf.ps1`, COM); a
  sandbox that blocks COM must run that one step with wider permissions. PDF input has no
  such requirement.

## When not to use it

* The deck is a talk/marketing deck and the user wants a *new* deck — use a slide-authoring
  skill instead.
* The user wants editable PowerPoint output rather than a printable PDF.
* Fewer than ~20 slides: hand-write the notes, the pipeline overhead is not worth it.
