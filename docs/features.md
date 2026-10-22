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
| Normalizer: reverse Google's export noise so both sides compare | tested | `normalize()`, fixtures 04, 05, 06; rules in [design.md](design.md) |
| Push form: rewrite the file for Google's import (code runs, hard breaks) | tested | `push_form()`, fixtures 05, 06; rules in [design.md](design.md) |
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
| Single Python file with PEP 723 inline dependencies; `uv run` installs them | built | [md2gdoc.py](../md2gdoc.py) carries the header; no command runs under `uv` yet (PT-006) |
| OAuth desktop client, `drive.file` scope only, token cached after one browser login | built | PT-003 made the client and proved it on both APIs ([chadkit/work/PT-003.md](../chadkit/work/PT-003.md)); the script's own token caching is PT-006 |
| Credentials and token kept out of git | tested | `.gitignore`; the gate's checks run on every commit |
| Open a Doc a human created by hand | idea | needs the `drive` scope on a secondary account or a service account, and a script option to request either; [setup.md](setup.md) "Other setups" |
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
| Tables, including bold cells | workaround | fixture 01; alignment colons come back on every column, so the normalizer writes `| --- |` and alignment is lost |
| Blockquotes | tested | fixture 01; becomes an indented paragraph |
| Horizontal rules | tested | fixtures 01, 03 |
| Footnotes | tested | fixture 01; real Docs footnotes |
| Escaped characters (`\-`, `\[`, `\#`, ...) | workaround | fixtures 03, 04, 07; the normalizer unescapes outside code spans, so a deliberate escape there is dropped on pull unless it keeps a line from becoming a block |
| Soft line breaks inside a paragraph or list item | workaround | fixture 06: pushed as hard breaks so the Doc keeps the file's lines; a hard break the file had comes back soft; raw, fixture 03 shows them joined |
| Text typed in the Docs UI after a bold line | tested | fixture 04; it inherits bold, treated as noise unless local had it |
| Fenced code blocks (triple backtick) | workaround | fixture 05: a fence at the left margin is pushed as a code run ([design.md](design.md) "Push form", built by PT-005); lost: the Doc shows monospace lines with no code background, the fence style, a trailing blank line |
| Language tag on a fence | workaround | fixture 05 tests: the Doc cannot hold it; kept from the local file, empty on a fresh pull |
| Indentation, tabs, and blank lines inside a fenced block | tested | fixture 05; pushed as entities, come back as whitespace |
| Trailing whitespace inside a code line | idea | PT-013 [probe 4](../chadkit/work/PT-013/probe-4-whitespace-in-spans.out.md), "Trailing spaces inside code": the export moves them outside the span, so they are no longer code; an entity was not tried |
| Indented code (four spaces) | idea | fixture 01 `.round2.out.md`: the indent is lost on re-import; the push form could rewrite it to a fence |
| Fenced code inside a list item | idea | sent as it is today and loses its shape (PT-013 [probe 1](../chadkit/work/PT-013/probe-1-raw-fences.out.md), "Fenced in a list"); a code run inside the item keeps its lines ([probe 6](../chadkit/work/PT-013/probe-6-entities-and-lists.out.md)); no test pins it |
| Native Docs "Code block" building block | not possible | UI only, paid Workspace editions; no API request creates one |
| Raw HTML inside markdown: inline styles such as colour | idea | fixture 01 shows the text survives; colour cannot show in a markdown export |
| `<details>` | not possible | its text merges into the next heading |
| Images | idea | via `<img src>` in an HTML upload or `insertInlineImage`; not tested |
| Comments and suggestions in the Doc | not possible | lost on a whole-document push; PT-009 is the remedy |
| Nested checkbox under a checkbox at deeper levels | planned | PT-004 records how it exports |
