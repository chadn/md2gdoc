# Features

The complete list of known features, whether built or not. One row per feature. Status column is one of

- `idea` (named, no task)
- `planned` (a task owns it)
- `built` (exists, but no test proves it)
- `tested` (a test under `tests/` or a fixture pair proves it)
- `workaround` (partially works through an approach of this project's own; the row says what is lost)
- `not possible` (Google offers no way; the row stays so nobody retries it).

Converter rows describe what Google's markdown import and export do, which the script inherits; they move to
`tested` when a fixture pair pins them. Add a row when a feature is first named, even as an idea.

## Sync

| Feature | Status | Owner / evidence |
| --- | --- | --- |
| `init`: create a native Doc from a markdown file and write the state file | planned | PT-006 |
| `pull`: export the Doc as markdown, normalize, write the file | planned | PT-006 |
| `push`: replace the whole Doc from the file, same link | planned | PT-006; in-place update PT-004 |
| `status`: what changed on each side since the last sync | planned | PT-006 |
| `sync`: pull, three-way merge against the snapshot, push | planned | PT-007 |
| `--dry-run` on every command | planned | PT-006 |
| `--help` that covers setup, files, and exit codes | planned | PT-006 |
| State file next to the markdown file: Doc id, link, Drive `version`, snapshot | planned | PT-006 |
| Normalizer: reverse Google's export noise so both sides compare | planned | PT-005; rules in `design.md` |
| Three-way merge on normalized lines; added lines kept, one-sided edits taken | planned | PT-007 |
| A checkbox ticked on one side wins over an untouched box | planned | PT-007 |
| A line deleted on one side and edited on the other is a conflict | planned | PT-007 |
| Conflict markers `api-edited` / `hand-edited`, exit 2, no push | planned | PT-007 |
| Push guard: Drive `version` plus normalized-export comparison; no `revisionId` | planned | PT-007 |
| Skip a push when normalized content is unchanged, so no empty revisions | planned | PT-007 |
| Re-pull after a successful push and store the new `version` and snapshot | planned | PT-007 |
| Targeted edits through the Docs API so comments and formatting on untouched text survive | planned | PT-009 |
| Agent hooks: auto-pull before an agent reads a synced file, auto-push after it writes | idea | gdoc ships these (`similar.md`) |
| Sync several files or a folder in one run | idea | - |
| Named versions of a Doc | not possible | no API names a revision; `files.copy` a titled snapshot instead |

## Setup and access

| Feature | Status | Owner / evidence |
| --- | --- | --- |
| Single Python file with PEP 723 inline dependencies; `uv run` installs them | planned | PT-006 |
| OAuth desktop client, `drive.file` scope only, token cached after one browser login | planned | PT-003 |
| Credentials and token kept out of git | tested | `.gitignore`; the gate's checks run on every commit |
| Open a Doc a human created by hand | idea | needs the broader `drive` scope; `setup.md` "Limits worth knowing" |
| Runs unattended: git hook, cron, CI | planned | PT-006 |
| Exit codes documented: 0 ok, 2 conflict, others per `--help` | planned | PT-006 |

## Markdown through Google's converter

What survives a round trip, file to Doc to file. `tests/fixtures/` holds the byte-for-byte evidence.

| Feature | Status | Owner / evidence |
| --- | --- | --- |
| Headings H1-H6 | built | fixtures 01, 03 pin H1-H3; H4-H6 seen in PT-002's import test, no fixture; export wraps headings in `**` |
| Bold, italic, links | tested | fixture 01; fixture 03 shows `_italic_` comes back as `*italic*` |
| Inline code (single backtick) | tested | fixtures 01, 05: backticks inside, stars, tags, table cells, task lines all survive |
| Nested bullet and numbered lists; a list starting at 5 keeps its start | tested | fixtures 01, 03 (the start at 5); nesting comes back at 2 spaces |
| Checkboxes `- [ ]` / `- [x]`, including state ticked in the Docs UI | tested | fixture 04 |
| Tables, including bold cells | tested | fixture 01 |
| Blockquotes | tested | fixture 01; becomes an indented paragraph |
| Horizontal rules | tested | fixtures 01, 03 |
| Footnotes | tested | fixture 01; real Docs footnotes |
| Escaped characters (`\-`, `\[`, `\#`, ...) | tested | fixture 03 for `\-`, fixture 04 for `\[` and `\#`; the normalizer unescapes |
| Soft line breaks inside a paragraph | tested | fixture 03; joined into one line on export; keep one logical line per task |
| Text typed in the Docs UI after a bold line | tested | fixture 04; it inherits bold, treated as noise unless local had it |
| Fenced code blocks (triple backtick) | workaround | fixture 05: pushed as a code run (`design.md` "Push form"), PT-005 builds it; lost: the Doc shows monospace lines with no code background, the fence style, a trailing blank line |
| Language tag on a fence | workaround | the Doc cannot hold it; kept from the local file, empty on a fresh pull (PT-013.md) |
| Indentation, tabs, and blank lines inside a fenced block | tested | fixture 05; pushed as entities, come back as whitespace |
| Trailing whitespace inside a code line | idea | fixture 05 line 27: the export moves a pad space outside the span; an entity was not tried |
| Indented code (four spaces) | idea | fixture 01 `.round2.out.md`: the indent is lost on re-import; the normalizer could rewrite it to a fence |
| Fenced code inside a list item | idea | a PT-013 probe kept the lines in the item; no fixture pins it |
| Native Docs "Code block" building block | not possible | UI only, paid Workspace editions; no API request creates one |
| Raw HTML inside markdown: inline styles such as colour | idea | fixture 01 shows the text survives; colour cannot show in a markdown export |
| `<details>` | not possible | its text merges into the next heading |
| Images | idea | via `<img src>` in an HTML upload or `insertInlineImage`; not tested |
| Comments and suggestions in the Doc | not possible | lost on a whole-document push; PT-009 is the remedy |
| Nested checkbox under a checkbox at deeper levels | planned | PT-004 records how it exports |
