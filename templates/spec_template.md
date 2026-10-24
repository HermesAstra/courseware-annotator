# Annotation spec (hand this to the annotation sub-agents)

You are writing Chinese study annotations for lecture slides of
**<COURSE NAME>** (instructor: <NAME>). The final exam is **open-book, paper only**,
so every page must let the reader see the key points at a glance.

## Input
`batch_<a>_<b>.json` — one object per page:
* `n` page number inside this deck
* `text` extracted text (may be empty or incomplete)
* `cap` character budget for this page's notes (never exceed it)
* `img` path to the page image; **use `read_image` on pages with little text and on
  every figure page** — otherwise the annotation will mis-describe the figure.

## Output
One JSON file, UTF-8:
```json
{"pages":[
 {"n":28,
  "title":"真核基因结构",
  "kp":["增强子","启动子","外显子","成熟mRNA"],
  "supp":false,
  "drop":false,
  "merge":"none",
  "notes":[
    {"t":"考点","s":"……"},
    {"t":"解释","s":"……"},
    {"t":"易错","s":"……"}
  ]}
]}
```

## Field rules
* `drop: true` — *only* clicker/voting/attendance pages, course schedule or syllabus,
  grading/reporting rules, group-assignment lists, TA/lecturer self-intro, bare covers,
  pure table-of-contents pages. Everything else stays.
* `merge: "next"|"prev"` — only for a page with essentially no information (one-line
  section divider, a copyright line, a single caption).
* `supp: true` — teacher-marked supplemental/reference pages (e.g. coloured background).
  Keep them; write one "选读" line; never a 考点.
* `title` ≤ 10 Chinese characters — used by the index.
* `kp` — 2–4 keywords, 2–8 characters each; the index is built from these. Write what a
  reader would scan for during the exam ("lac 操纵子负调控", "衰减作用", "σ 因子").
  Every `kp` must name a **knowledge point**. Never use meta words such as
  「设问」「重复页」「合并页」「其他疗法」— the index is built from these and they pollute it.
* `notes` — 2–4 items, **80–180 characters in total**, never above `cap`. `t` is one of:
  * `考点` — the hard fact to remember: definition, classification, numbers, order, who binds what.
  * `解释` — what this figure/mechanism is actually saying, in plain language.
  * `易错` — the confusion that costs marks (positive vs negative control, cis vs trans,
    inducible vs repressible …).
  * `问法` — how this page might be asked, one sentence.

## Style
* Chinese; keep technical terms in English with a Chinese gloss: `operon（操纵子）`.
* Never describe the handout's own layout ("排版时并入上一页", "重复页", "此页与下页合并").
  A reader only ever sees one slide and its notes: describe the biology, never the booklet.
* Compress; never copy a whole English sentence from the slide.
* Write for "flip to this page and instantly see the point", not textbook prose.
* Stay inside what the slides say. If unsure, leave it out — a wrong note is worse than none.
* Pages must read as one continuous set: do not restate the same preamble on every page.

## Deliver
Write the JSON to the path given in the task and reply with: number of pages, dropped
page numbers, merged page numbers, and any page you are unsure about.
