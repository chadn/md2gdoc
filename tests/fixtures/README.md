# Round-trip fixtures (PT-002 and PT-013, 2026-10-21; PT-004, 2026-10-22; PT-023, 2026-10-25; PT-024, 2026-10-27)

Each `.in.*` file was uploaded to Google Drive with conversion to a native Google Doc; each `.out.md` is the
`text/markdown` export of the resulting Doc, byte for byte. Use them as normalizer test cases: normalize(out) must
equal normalize(in) for pair 04 and, with the losses [tests/test_normalize.py](../test_normalize.py) lists, for
01 and 03; the task-list pair must preserve checkbox state; 05, 06, 07 and 09 to 12 have their own equalities
below.

- 01-markdown-import: markdown with every feature; `.round2.out.md` is the export after feeding `.out.md` back in.
- 02-html-import: the same content as HTML; shows what HTML conversion keeps.
- 03-resume-style: headings, rules, 4-space nested lists, bold labels, escaped characters.
- 04-task-list: ChadKit-style task lines; `.after-ui-edit.out.md` is the export after a human ticked T-002 and
  typed T-004 in the Docs UI (T-004 came back bold because typed text inherits the previous run's style).
- 05-code-blocks: inline code edge cases and fenced blocks (PT-013). `.src.md` is the file as a person writes it,
  `.in.md` is the push form the script sends in its place ([docs/design.md](../../docs/design.md), "Push form"),
  `.out.md` the export.
  Tests: push_form(src) == in, and normalize(out, src) == src where src supplies the fences' info strings.
  The export has no final newline; keep it that way.
- 06-hard-breaks: a one-line fenced block, a two-line paragraph, and a list item with a continuation line
  (PT-005); same three files and equalities as 05.
- 07-spans: backslashes and markdown characters inside code spans, and escapes outside them (PT-005). A pair:
  normalize(out) == normalize(in), and the test pins the one deliberate escape the normalizer drops.
- 08-nested-checkboxes: checkboxes four levels deep, a plain bullet under a checkbox and the reverse, and a
  checkbox under an ordered item (PT-004, through the script's own OAuth client). A pair: normalize(out) == in.
- 09-gfm-headings-rules: setext headings, H4-H6, the three rule styles (PT-023). A pair: normalize(out) == in
  with each setext heading as ATX and every rule `---`.
- 10-gfm-lists-quotes: bullet and numbering markers back to back, a loose list, a nested quote, a list in a quote,
  indented code, a tab (PT-023); `.src.md`, `.in.md` and `.out.md` as 05. Equalities: push_form(src) == in, and
  normalize(out, src) == src with the blank between adjacent lists gone, empty `>` lines around the quotes, and
  the indented code as two paragraphs.
- 11-gfm-inlines: strikethrough, emphasis markers, entities, an image, autolinks, link titles, reference links,
  raw inline HTML, Unicode (PT-023). normalize(out) == in with the losses the test lists; `.round2.out.md` is the
  export fed back in, byte for byte the same as `.out.md` (the image's data URI survives a push).
- 12-gfm-list-markers: each marker style in its own list, a start at 3, nested mixed markers (PT-023). A pair:
  normalize(out) == in.
- [04-task-list.doc.json](04-task-list.doc.json): the `documents.get` of a Doc made from
  [04-task-list.in.md](04-task-list.in.md) through the script's own import (PT-009,
  [build-probe-1.py](../../chadkit/work/PT-009/build-probe-1.py)), `documentId` and `revisionId` masked, document
  and named styles dropped; the edit planner's test bed.
- 13-list-kinds: fixture 12's lists plus a checklist and a paragraph with every inline style, made and exported
  through the script (PT-009, [build-probe-2.py](../../chadkit/work/PT-009/build-probe-2.py) and
  [build-probe-2b.py](../../chadkit/work/PT-009/build-probe-2b.py)); `.doc.json` is its `documents.get`, masked
  as 04's. A pair: normalize(out) == normalize(in).
- 14-github-platform: GitHub's layer beyond GFM: a mermaid fence, alerts, inline and block math and a math fence,
  emoji shortcodes, color chips, `<details>`, a mention, an issue reference and a commit SHA (PT-024); `.src.md`,
  `.in.md` and `.out.md` as 05. Equalities: push_form(src) == in, and normalize(out, src) == src with two alerts
  back to back merged into one quote, each shortcode as its character, and the `<details>` block as one paragraph.

Trailing double spaces on list lines are part of Google's export; keep them when copying. PT-013's probes went
through the same converter and are kept as evidence, not test cases (recovered from the session transcript), under
[chadkit/work/PT-013/](../../chadkit/work/PT-013/).
PT-023's fixtures went through the script's own `Drive.create` and `Drive.export` calls, by
[chadkit/work/PT-023/probe.py](../../chadkit/work/PT-023/probe.py); PT-024's by
[chadkit/work/PT-024/probe.py](../../chadkit/work/PT-024/probe.py).
