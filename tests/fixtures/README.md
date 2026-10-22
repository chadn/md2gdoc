# Round-trip fixtures from the PT-002 spike (2026-10-21)

Each `.in.*` file was uploaded to Google Drive with conversion to a native Google Doc; each `.out.md` is the
`text/markdown` export of the resulting Doc, byte for byte. Use them as normalizer test cases: normalize(out) must
equal normalize(in) for every pair, and the task-list pair must preserve checkbox state.

- 01-markdown-import: markdown with every feature; `.round2.out.md` is the export after feeding `.out.md` back in.
- 02-html-import: the same content as HTML; shows what HTML conversion keeps.
- 03-resume-style: headings, rules, 4-space nested lists, bold labels, escaped characters.
- 04-task-list: ChadKit-style task lines; `.after-ui-edit.out.md` is the export after a human ticked T-002 and
  typed T-004 in the Docs UI (T-004 came back bold because typed text inherits the previous run's style).

Trailing double spaces on list lines are part of Google's export; keep them when copying.
