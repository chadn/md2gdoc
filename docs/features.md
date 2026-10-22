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
| `init`: create a native Doc from a markdown file and write the state file | tested | [tests/test_cli.py](../tests/test_cli.py); the real run in [chadkit/work/PT-006.md](../chadkit/work/PT-006.md) |
| `pull`: export the Doc as markdown, normalize, write the file | tested | [tests/test_cli.py](../tests/test_cli.py); the real run in [chadkit/work/PT-006.md](../chadkit/work/PT-006.md) |
| `push`: replace the whole Doc from the file, same link | tested | [tests/test_cli.py](../tests/test_cli.py); the real run in [chadkit/work/PT-006.md](../chadkit/work/PT-006.md); in-place update PT-003's probe |
| `status`: what changed on each side since the last sync | tested | [tests/test_cli.py](../tests/test_cli.py); compares the normalized export, since a matching `version` is not proof |
| `sync`: pull, three-way merge against the snapshot, push | planned | PT-007 |
| `--dry-run` on every command | tested | [tests/test_cli.py](../tests/test_cli.py); `status --dry-run` reads the local side only |
| `--help` that covers setup, files, and exit codes | tested | [tests/test_cli.py](../tests/test_cli.py) |
| State file next to the markdown file: Doc id, link, Drive `version`, snapshot, the file's text at last sync | tested | `FILE.gdoc.json`; [tests/test_cli.py](../tests/test_cli.py) |
| Normalizer: reverse Google's export noise so both sides compare | tested | `normalize()`, fixtures 04, 05, 06; rules in [design.md](design.md) |
| Push form: rewrite the file for Google's import (code runs, hard breaks) | tested | `push_form()`, fixtures 05, 06; rules in [design.md](design.md) |
| Three-way merge on normalized lines; added lines kept, one-sided edits taken | planned | PT-007 |
| A checkbox ticked on one side wins over an untouched box | planned | PT-007 |
| A line deleted on one side and edited on the other is a conflict | planned | PT-007 |
| Conflict markers `api-edited` / `hand-edited`, exit 2, no push | planned | PT-007 |
| Push guard: normalized-export comparison, exit 3 when the Doc moved; `version` shown, never trusted alone, never `revisionId` | tested | [tests/test_cli.py](../tests/test_cli.py); a matching `version` is not proof ([chadkit/work/PT-004.md](../chadkit/work/PT-004.md)); `pull` has the mirror guard, `--force` lifts it |
| Skip a push when normalized content is unchanged, so no empty revisions | tested | [tests/test_cli.py](../tests/test_cli.py) |
| Re-pull after a successful push and store the new `version` and snapshot | tested | [tests/test_cli.py](../tests/test_cli.py); after `init` too |
| Targeted edits through the Docs API so comments and formatting on untouched text survive | planned | PT-009 |
| Agent hooks: auto-pull before an agent reads a synced file, auto-push after it writes | idea | gdoc ships these (`similar.md`) |
| Sync several files or a folder in one run | idea | - |
| Named versions of a Doc | not possible | no API names a revision; `files.copy` a titled snapshot instead |

## Setup and access

| Feature | Status | Owner / evidence |
| --- | --- | --- |
| Single Python file with PEP 723 inline dependencies; `uv run` installs them | tested | every command of the real run in [chadkit/work/PT-006.md](../chadkit/work/PT-006.md) ran under `uv run --script` |
| OAuth desktop client, `drive.file` scope only, token cached after one browser login | built | PT-003 made the client and proved it on both APIs ([chadkit/work/PT-003.md](../chadkit/work/PT-003.md)); the script reuses and refreshes the cached token (the real run in [chadkit/work/PT-006.md](../chadkit/work/PT-006.md)); its browser login is the same flow as PT-003's probe, not run from the script yet |
| Credentials and token kept out of git | tested | `.gitignore`; the gate's checks run on every commit |
| Open a Doc a human created by hand | idea | needs the `drive` scope on a secondary account or a service account, and a script option to request it; `--account NAME` already picks the token (the account half); [setup.md](setup.md) "Other setups" |
| Runs unattended: git hook, cron, CI | built | no browser once `token.json` exists; no hook or CI example yet |
| Exit codes documented: 0 ok, 1 error, 2 conflict, 3 push or pull refused | tested | [tests/test_cli.py](../tests/test_cli.py), usage errors included |

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
| A list item right after a paragraph line, no blank line between | idea | the real run in [chadkit/work/PT-006.md](../chadkit/work/PT-006.md): the export puts a blank line before the list, so after a push the Doc's text differs from the file's until `pull --force` writes the blank line; a fixture and a normalizer rule could reverse it |
| Nested checkbox under a checkbox at deeper levels | tested | fixture 08: a child's indent is its parent's content column (6 under a checkbox, 2 under a bullet, 3 under an ordered item), and the normalizer reads levels relative to the open items |
