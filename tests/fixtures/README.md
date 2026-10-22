# Round-trip fixtures (PT-002 and PT-013, 2026-10-21; PT-004, 2026-10-22)

Each `.in.*` file was uploaded to Google Drive with conversion to a native Google Doc; each `.out.md` is the
`text/markdown` export of the resulting Doc, byte for byte. Use them as normalizer test cases: normalize(out) must
equal normalize(in) for pair 04 and, with the losses [tests/test_normalize.py](../test_normalize.py) lists, for
01 and 03; the task-list pair must preserve checkbox state; 05, 06 and 07 have their own equalities below.

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

Trailing double spaces on list lines are part of Google's export; keep them when copying. PT-013's probes went
through the same converter and are kept as evidence, not test cases (recovered from the session transcript), under
[chadkit/work/PT-013/](../../chadkit/work/PT-013/).
