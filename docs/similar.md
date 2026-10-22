# Similar solutions

What else reads or writes a native Google Doc from markdown, and how this project differs. Two kinds: platform
paths, which need no code from this project, and custom tools on GitHub. Keep this list current when a new one turns up;
the review that seeded it is PT-002.md, whose Comparison of the top 3 scores the platform paths feature by
feature.

## Platform paths

| Path                               | Write                                              | Read                              | Edit in place        | Named versions | Notes                                                                                                   |
| ---------------------------------- | -------------------------------------------------- | --------------------------------- | -------------------- | -------------- | ------------------------------------------------------------------------------------------------------- |
| [Drive connector in Claude](https://support.claude.com/en/articles/10166901-using-the-google-workspace-connectors) | md or html upload, new Doc each time               | markdown render, or export        | no, metadata only    | no             | no setup; what PT-002 tested                                                                        |
| [Google Docs connector](https://support.claude.com/en/articles/10166901-using-the-google-workspace-connectors) | `batchUpdate` requests, suggestion mode            | full JSON with positions          | yes                  | no             | UTF-16 positions, revision guards; the skill reference calls it error-prone          |
| [Docs API + Drive API, own script](https://developers.google.com/workspace/drive/api/guides/manage-uploads) | `files.update` with `text/markdown` keeps the link | `files.export` as `text/markdown` | yes                  | no             | needs an OAuth client; in-place markdown replace proven by gdoc below; PT-004 confirms it here                     |
| [Apps Script](https://developers.google.com/apps-script/reference/document/document) | DocumentApp element tree                           | same                              | yes                  | no             | nothing the REST API lacks for this use                                                                 |
| Claude Docs artifact               | export to Google Docs is a UI button only          | n/a                               | n/a                  | n/a            | the MCP export has no Google target; not an API path                                                    |
| [`.md` edited natively in Drive](https://workspaceupdates.googleblog.com/2026/10/preview-edit-and-collaborate-on-Markdown-files-natively-across-Drive-and-Docs.html) | upload `.md` as is                                 | as is                             | Docs UI, Oct 2026    | n/a            | not a native Doc, so out of scope by the Direction, but it removes the conversion loss entirely          |

The Drive connector stays useful as a zero-setup read path and for one-off creates. The Docs connector is the only
path where an AI edits a Doc in place with suggestions, at the cost of determinism and write access to every Doc
in the account. This project is the third row.

## Custom tools on GitHub

Three open-source markdown to Google Docs tools, each cloned and read against one rubric on 2026-10-21 (PT-002),
compared with what this project builds ("This project"). All three are single-maintainer alpha projects; none handles
checkboxes.

| Feature                    | [gdoc-sync](https://github.com/MattHandzel/gdoc-sync) (MattHandzel)                       | [md-gdoc](https://github.com/MattFisher/md-gdoc) (MattFisher)                            | [gdoc](https://github.com/LucaDeLeo/gdoc) (LucaDeLeo)                                     | This project                                                                            |
| -------------------------- | ----------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Purpose                    | Two-way md/Doc sync with comments as CriticMarkup                                         | Push md, pull reviewer comments and edits, keep comment anchors                          | Token-efficient CLI and MCP server for AI agents on Docs, Drive, Sheets                   | Two-way sync of one task list, reusable single file                                       |
| Maturity                   | 4 stars, pushed 2026-09-30, MIT, 1 contributor, 424 tests, v0.9 alpha                     | 1 star, last commit 2026-08-07, MIT, 2 contributors, 135 tests, v0.2 alpha               | 20 stars, pushed 2026-10-18, MIT claimed but no LICENSE file, 5 contributors, ~1,850 tests| none yet                                                                                  |
| Auth and scopes            | OAuth desktop; full `drive` + `documents`                                                 | OAuth desktop; full `drive`                                                              | OAuth desktop; full `drive` + `documents`                                                 | OAuth desktop; `drive.file` only                                                          |
| Write path                 | md -> pandoc docx -> `files.update` (tabs via batchUpdate)                                | Docs API batchUpdate only, incremental block replace; Drive import avoided on purpose    | `files.update` with `text/markdown` media for whole doc; batchUpdate for edits           | `files.update` with `text/markdown` media, whole doc                                      |
| Update keeps link          | yes                                                                                       | yes                                                                                      | yes                                                                                       | yes (same call as gdoc)                                                                   |
| Read path                  | `documents.get` + own JSON-to-md renderer                                                 | `files.export` text/markdown + cleanup + mdformat                                        | `files.export` text/markdown, raw                                                         | `files.export` text/markdown + normalizer                                                 |
| Sync direction             | two-way (`sync`, `watch`) plus push/pull                                                  | two-way, asymmetric: pull overwrites or drops a `.remote.md`                             | one-way push, one-way pull; Claude Code hooks auto-pull/push                              | two-way (`sync`) plus push/pull                                                           |
| Change detection           | two snapshots (local, remote); rejects revisionId as churny; sha256 text fingerprint      | two snapshots in `.sync/`, content equality                                              | Drive `version` integer stamped in frontmatter; no snapshot                               | two snapshots + Drive `version` guard (changed from revisionId after this review)         |
| Merge                      | three-way `git merge-file --diff3`, pure-Python fallback                                  | none: human merges the `.remote.md`                                                      | none: refuse or `--force` last-writer-wins                                                | three-way on normalized lines                                                             |
| Conflict handling          | git-style markers, sticky conflict state, `resolve` command, backups kept                 | `.remote.md` sidecar, push refuses unless `--force`                                      | exit 3, manual pull-to-new-path and `diff`                                                | `<<<<<<< api-edited` / `>>>>>>> hand-edited` markers, exit 2, no push                     |
| Export noise normalization | n/a (does not use export)                                                                 | `clean()`: strips 20 backslash escapes, collapses blanks, code-font to fences; mdformat  | only for diff display                                                                     | heading bold, escapes, autolinks, trailing spaces, nesting (list in Script design)        |
| Checkboxes                 | no; pandoc would emit glyphs                                                              | no; `[ ]` kept as literal text                                                           | no; refuses glyph lists                                                                   | yes, proven through Google's converter both ways                                          |
| Markdown coverage          | widest: tables, fenced code, images, footnotes, LaTeX, callouts, tabs; no blockquotes     | headings, lists, tables, fenced code byte-perfect, blockquote; images dropped on push    | headings, lists, fenced code, tables, blockquote, HR, images; no footnotes               | what the converter keeps; code runs for fences                                            |
| Comments                   | pulled as CriticMarkup, replies and resolves pushed                                       | read-only to `<file>.comments.md`, warns before overwriting an anchor                    | full comments API, anchored in preview program, suggestions via batchUpdate              | none; lost on push                                                                        |
| State and config           | YAML state in `~/.local/state`, bases and backups, config YAML, multi-file, `watch`       | Doc id in md frontmatter, snapshots in `.sync/`, no config                               | Doc id and version in frontmatter, per-machine state JSON, config JSON                    | one state file JSON next to the md                                                           |
| CLI UX                     | 18 subcommands, dry-run only on one, exit codes 1/2/3/130                                 | push/pull/status/clone, no dry-run, exit 0/1                                             | ~45 subcommands, four output modes, no dry-run, `--help` self-updates over the network    | init/pull/push/sync/status, `--dry-run` on all, documented exit codes                     |
| Dependencies               | google client libs, PyYAML, external pandoc and git                                       | google client libs, markdown-it-py, mdformat-gfm, python-frontmatter                     | google client libs, requests                                                              | google client libs only, PEP 723 inline                                                   |
| Size                       | package, ~20 modules                                                                      | package, ~15 modules                                                                     | 5,600-line cli.py plus package                                                            | one file, target under 500 lines                                                          |
| Main risk for this project | pandoc dependency, no checkboxes, whole-doc replace anyway                                | no auto-merge, push alignment breaks on any remote structural edit                       | no merge, false conflicts on cosmetic Docs edits                                          | unproven in-place update, normalizer coverage                                             |

## Per-tool notes

Paths are inside each repository. Nothing was executed; the clones were read as data.

**gdoc-sync** (MattHandzel, Python >= 3.10, v0.9.0, created 2026-07, CI on Linux and macOS)

- Write pipeline is markdown to pandoc docx to `files.update` on the same id; multi-tab docs instead compile the
  pandoc AST into Docs API requests (`src/gdoc_sync/push.py`, `mdrequests.py`, `tabs.py`). Needs pandoc installed.
- Reads with `documents.get(includeTabsContent=True)` and its own renderer `doc_to_markdown`
  (`src/gdoc_sync/convert.py:137-266`): headings, bullets, code detected by monospace font, tables, footnotes.
  Blockquotes do not round-trip. Suggestions are rendered as if accepted.
- Change detection keeps two snapshots per file, `base_local` and `base_remote`, and compares each side only to
  its own snapshot. `revisionId` is explicitly rejected because Google churns it; a sha256 text fingerprint guards
  the render-to-upload race (`convert.py:596-640`, `push.py:95-102`).
- Merge is `git merge-file --diff3` with a pure-Python diff3 fallback (`src/gdoc_sync/merge.py`, about 300 lines,
  no Google dependency). Conflicts leave git-style markers or a `.remote.md` sidecar and set a sticky conflict state
  until `resolve`. Backups kept (20). Refuses to push if the file shrank below 20% or the Doc rendered below 50% of
  the baseline, a cheap guard against pushing an empty file.
- Comments round-trip as CriticMarkup `{>>Author: text<<}`; replies and resolves push through the Drive comments
  API. New anchored comments are impossible (a Google bug is cited).
- Checkboxes: nothing in the source; pandoc would emit U+2610/U+2612 glyphs, so `- [ ]` would arrive as text.
- 18 subcommands including `watch`, `doctor`, `share`, `restore`; `--dry-run` only on one novelty command.
  State in `~/.local/state/gdoc-sync/state.yaml` plus `bases/` and `backups/`; config in `~/.config/gdoc-sync/`.

**md-gdoc** (MattFisher, Python >= 3.10, v0.2.0, two contributors, one of them "claude")

- Writes through the Docs API only, on purpose: `documents.create` then `batchUpdate` with insertText,
  updateParagraphStyle, updateTextStyle, createParagraphBullets, insertTable (`src/md_gdoc/requests_builder.py`).
  Incremental pushes diff local blocks with `difflib.SequenceMatcher` and replace only changed ranges, which keeps
  comment anchors on untouched blocks; `--replace` clears the body. Alignment requires the Doc's block count to
  equal the snapshot's, so any structural edit made in the UI forces `--replace`.
- Reads with `files.export(text/markdown)` then `clean()` (`src/md_gdoc/unescape.py`): CRLF to LF, strips the
  backslash escapes Google adds to `` \ ` * _ { } [ ] ( ) # + - . ! | < > ~ " ' ``, collapses blank runs, turns
  code-font paragraphs back into fences; then `mdformat` with the gfm plugin normalizes bullets, trailing spaces,
  and `:----` separators. The e2e golden file documents what Google emits (`tests/e2e/fixtures/`).
- Two snapshots in `.sync/` next to the file; pull overwrites local when only the Doc changed, otherwise writes
  `<file>.remote.md` and leaves the merge to a human. Push refuses on divergence unless `--force`. No three-way
  merge by design (`docs/superpowers/specs/2026-07-02-gdoc-sync-design.md`).
- Request ordering lesson worth keeping: insert a whole list as one insertText with tab prefixes, apply paragraph
  styles, then text styles, then createParagraphBullets last because it consumes the tabs
  (`requests_builder.py:175-211`). `batch_update` has 429 backoff (`api.py:109-120`).
- Comments are read-only into `<file>.comments.md`; push warns when a changed block holds a comment's quoted text.
  Images are dropped on push and extracted to `<name>.assets/` on pull. Footnotes only with `--replace`.
- Checkboxes: `- [ ]` is pushed as a bullet whose text is the literal `[ ]`; native Docs checklists are not handled.
- Doc id and url live in the markdown file's YAML frontmatter (`gdoc_id`, `gdoc_url`, `tab_id`).

**gdoc** (LucaDeLeo, Python >= 3.10, v0.23.0, 20 stars, 5 contributors, about 1,850 tests, CLI plus MCP server)

- Whole-document write is exactly this project's call: `files.update` with media mimetype `text/markdown`, body
  mimeType `application/vnd.google-apps.document`, `fields="version"`, same file id so the link survives
  (`gdoc/api/drive.py:176-200`). `new --file` uses `files.create` with `text/markdown`. Partial edits, inserts,
  suggestions, and tables go through `batchUpdate` with a custom markdown-to-requests parser (`gdoc/mdparse.py`).
- Reads with `files.export(text/markdown)` raw; no normalization on the pull path. A de-escape loop
  `re.sub(r"\\([^\w\s])", r"\1", s)` exists only for diff display (`gdoc/revdiff.py:171-188`).
- Change signal is the Drive `version` integer stamped into frontmatter as `gdoc-version: N`; `version` is read
  before the export so the stamp can only be older than the content, never newer. Push refuses (exit 3) when the
  Doc's version moved past the stamp unless the current export already equals the local body; `--force` is
  last-writer-wins. The code acknowledges false conflicts from cosmetic Docs edits (`cli.py:2102`). No snapshot,
  no merge; recovery is pull to a new path and `gdoc diff`.
- Ships Claude Code PreToolUse/PostToolUse hooks that auto-pull before an agent reads a stamped `.md` and auto-push
  after it writes (`cli.py:2446-2800`). This is the closest existing thing to "AI edits the markdown, human edits
  the Doc".
- Full Drive comments API (list, add, reply, resolve, reopen, delete), anchored comments only when the Cloud
  project is in Google's Workspace preview program, suggestions via `suggest`.
- Checkboxes: none; `gdoc/listnest.py` refuses checkbox-glyph lists outright.
- Surprises: `gdoc --help` updates itself over the network; README claims MIT but no LICENSE file is in the tree;
  `cli.py` is 5,600 lines, so pieces are copied, not imported.
