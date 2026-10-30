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
| `push`: write the file's changes to the Doc, same link: edits in place, else the whole replace | tested | [tests/test_cli.py](../tests/test_cli.py); the real run in [chadkit/work/PT-006.md](../chadkit/work/PT-006.md); in-place update PT-003's probe |
| `status`: what changed on each side since the last sync | tested | [tests/test_cli.py](../tests/test_cli.py); compares the normalized export, since a matching `version` is not proof |
| `sync`: pull, three-way merge against the snapshot, push | tested | [tests/test_cli.py](../tests/test_cli.py); the real run in [chadkit/work/PT-007.md](../chadkit/work/PT-007.md) |
| `--dry-run` on every command | tested | [tests/test_cli.py](../tests/test_cli.py); `status --dry-run` reads the local side only |
| `--help` that covers setup, files, and exit codes | tested | [tests/test_cli.py](../tests/test_cli.py) |
| State file next to the markdown file: Doc id, link, Drive `version`, snapshot, the file's text at last sync | tested | `FILE.gdoc.json`; [tests/test_cli.py](../tests/test_cli.py) |
| Normalizer: reverse Google's export noise so both sides compare | tested | `normalize()`, fixtures 04, 05, 06; rules in [design.md](design.md) |
| Push form: rewrite the file for Google's import (code runs, hard breaks) | tested | `push_form()`, fixtures 05, 06; rules in [design.md](design.md) |
| Three-way merge on normalized lines; added lines kept, one-sided edits taken | tested | `merge3()`; [tests/test_cli.py](../tests/test_cli.py); lines added at the same place on both sides are all kept, the file's first |
| A checkbox ticked on one side wins over an untouched box | tested | [tests/test_cli.py](../tests/test_cli.py); a one-sided change like any other |
| A line deleted on one side and edited on the other is a conflict | tested | [tests/test_cli.py](../tests/test_cli.py) |
| Conflict markers `api-edited` / `hand-edited`, exit 2, no push | tested | [tests/test_cli.py](../tests/test_cli.py); written to the file, and a file still holding them is refused |
| Push guard: normalized-export comparison, exit 3 when the Doc moved; `version` shown, never trusted alone, never `revisionId` | tested | [tests/test_cli.py](../tests/test_cli.py); a matching `version` is not proof ([chadkit/work/PT-004.md](../chadkit/work/PT-004.md)); `pull` has the mirror guard, `--force` lifts it |
| `pull`, `sync` and `init --doc` stop while the Doc holds a pending suggestion, exit 3, nothing written | tested | [tests/test_cli.py](../tests/test_cli.py); the live run in [chadkit/work/PT-028/live.out.txt](../chadkit/work/PT-028/live.out.txt): an insertion, a deletion and a style change suggested through the API, all three counted from one `documents.get` and refused by every one of the six command forms, while the export shows the insertion and the style change as accepted and the deleted word as kept; without the Docs API, or for a profile Google shows no suggestions to, the command warns and reads on ([tests/test_cli.py](../tests/test_cli.py)); the decision and what is not measured: [chadkit/work/PT-028.md](../chadkit/work/PT-028.md) |
| Skip a push when normalized content is unchanged, so no empty revisions | tested | [tests/test_cli.py](../tests/test_cli.py) |
| Re-pull after a successful push and store the new `version` and snapshot | tested | [tests/test_cli.py](../tests/test_cli.py); after `init` too |
| Targeted edits through the Docs API so comments and formatting on untouched text survive | tested | [tests/test_cli.py](../tests/test_cli.py) on the `documents.get` of fixtures 04 and 13 (`.doc.json`); the live run in [chadkit/work/PT-009/live-proof.out.txt](../chadkit/work/PT-009/live-proof.out.txt): a changed word, a new box and a new paragraph by 10 requests, both comments still anchored; what falls back to the whole replace and why: [design.md](design.md), "Whole-document replace"; the measurements behind it: [chadkit/work/PT-009.md](../chadkit/work/PT-009.md) |
| Comments carried over a whole replace: each written again at its text, its replies after it, the orphan deleted | tested | [tests/test_cli.py](../tests/test_cli.py); the live run above: the tick's replace carried both comments and the reply; each is authored by the token's user and names the author in its body; one on text the push changed stays an orphan, named in the output; an orphan by another user stays listed, since the API deletes a comment for its author only ([DeleteCommentRequest](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/request#DeleteCommentRequest), not measured) |
| `push` a `.docx` body, which keeps comments and formatting, without the import turning the checklist into bullets or copying each comment | not possible | the checklist comes back as bullets even when an unchanged export goes back, and each trip adds a copy of the comment, 7 after 6; none of four Word checkbox forms imports as a checklist ([chadkit/work/PT-009.md](../chadkit/work/PT-009.md), probes 11, 12, 14; [design.md](design.md) option d) |
| Write edits as suggestions a person accepts in the Doc | idea | the Docs API's `SUGGEST` write mode, "apply all updates as suggestions" per [WriteControl](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate#WriteControl), measured on one `insertText` ([chadkit/work/PT-009.md](../chadkit/work/PT-009.md)); the targeted-edit path it needs exists (PT-009) |
| Which changes a push edits in place and which replace the whole Doc | tested | the table below; [tests/test_cli.py](../tests/test_cli.py) (`Plan`), the live run above |
| Agent hooks: a sync when the agent's session starts and after it writes the synced file | built | [agents.md](agents.md), a Claude Code hook recipe, not code in the script (PD-002); gdoc ships these as code ([similar.md](similar.md)) |
| Sync several files or a folder in one run | idea | - |
| Named versions of a Doc | not possible | no API names a revision; `files.copy` a titled snapshot instead |

### Which push writes what

A push edits the changed paragraphs in place when every change in the diff is in the first column; one change or Doc
state from the second column, anywhere, replaces the whole Doc, with the comments carried over and the suggestions
and hand formatting lost. The word in brackets is what `--json` reports as `why` ([agents.md](agents.md)); the
mechanism and the measurements are in [design.md](design.md), "Whole-document replace". The `Plan` tests in
[tests/test_cli.py](../tests/test_cli.py) pin each row's path and word; the live run proves three cells in a Doc.

| Change | In place | Whole replace |
| --- | --- | --- |
| Prose paragraph | text changed, added, removed; a blank line between blocks | two lines of one paragraph, or prose right after a list item with no blank (`layout`) |
| Heading | text, level, added, removed | an item rewritten as a heading (`list`) |
| Bulleted or numbered list | an item's text; a new item after an item of the same list, the numbers after it renumbered or not (a file left unrenumbered reads back renumbered, reported as `converter_diff`); an item removed | a new list where none is, or a new first item (`list`); a marker (`-` to `*`, `1.` to `1)`) changed (`list`); the kind (bullet to numbered) changed (`list`, `layout` when one item among others); a blank line between items (`blank`) |
| Checklist | an item's text; a new unticked item, after a checklist item, prose or a heading; an item removed | a box ticked or unticked, or a new item born ticked (`tick`); a new box right after a bullet or numbered item (`layout`) |
| Nested item | untouched ones stay as they are; one removed; prose or a heading added after one | its text changed, or a new item right after one (`nesting`); its level changed (`list`) |
| Inline styles | code span, `**bold**`, `*italic*`, `~~struck~~`, `[text](url)`, escapes | `_italic_`, an entity, raw HTML, an image mid-line, a link title (`inline`) |
| Table, fenced code, blockquote, rule, image, HTML block, footnote | - | every push of a Doc that holds one, changed or not (`structure`) |
| The Doc itself | - | a line break inside a paragraph (Shift+Enter), a title or subtitle, an indented paragraph, a second section (`structure`); a pending suggestion (`suggestion`; `sync` stops before it, so only `push` meets it, PT-029); its paragraphs not matching its export (`mapping`); the Docs API not enabled in the Cloud project (`docs_api`) |

## Setup and access

| Feature | Status | Owner / evidence |
| --- | --- | --- |
| Single Python file with PEP 723 inline dependencies; `uv run` installs them | tested | every command of the real run in [chadkit/work/PT-006.md](../chadkit/work/PT-006.md) ran under `uv run --script` |
| OAuth desktop client, `drive.file` by default or `drive` per profile, token cached after one browser login | built | PT-003 made the client and proved it on both APIs ([chadkit/work/PT-003.md](../chadkit/work/PT-003.md)); the script reuses and refreshes the cached token (the real run in [chadkit/work/PT-006.md](../chadkit/work/PT-006.md)); its browser login is the same flow as PT-003's probe, not run from the script yet |
| Credentials and token kept out of git | tested | `.gitignore`; the gate's checks run on every commit |
| Open a Doc the script did not create | tested | `init FILE --doc ID` on a `--scope drive` profile (PT-020, PT-022): a Doc the main account made through another app and shared, and a Doc the second account made by hand in the Docs UI: both attached, a local edit pushed by `sync` on both, an edit made in the Docs UI pulled by `sync` on the shared one and a box ticked in the UI kept through attach on the other, both Docs refused to the `drive.file` profile, in [chadkit/work/PT-022/](../chadkit/work/PT-022/); [setup.md](setup.md) Secondary-account setup |
| Runs unattended: git hook, cron | built | no browser once the token exists; no hook example yet; CI out of scope until a service-account path exists (PD-002) |
| Config directory: client file and token per profile under `~/.config/md2gdoc` (`%APPDATA%` on Windows), `--account`, `MD2GDOC_ACCOUNT`, `MD2GDOC_CONFIG_DIR` | tested | `config_dir()`, `profile_dir()`, `token_scope()` in [tests/test_cli.py](../tests/test_cli.py); the live run in [chadkit/work/PT-020.md](../chadkit/work/PT-020.md) |
| Windows, macOS and Linux, tests in CI on all three; CRLF kept; UTF-8 output | tested | [.github/workflows/tests.yml](../.github/workflows/tests.yml) runs the tests on the three with Python 3.11, 3.13 and 3.14 on every push to GitHub; CRLF read as LF and written back as CRLF, the state file always LF, UTF-8 forced on stdout and stderr ([tests/test_cli.py](../tests/test_cli.py) pins the line endings; the first CI run on GitHub, nine jobs green, PLR-20261022-14) |
| `--json` on every command for agents: one object with exit, reason, message, the diffs and what was written or pushed | tested | [tests/test_cli.py](../tests/test_cli.py); the fields in [agents.md](agents.md) |
| Installable as the command `md2gdoc` with `uv tool install` from GitHub | built | [pyproject.toml](../pyproject.toml), entry point `md2gdoc:cli`; installed from the working tree in [chadkit/work/PT-021/install.out.txt](../chadkit/work/PT-021/install.out.txt), the GitHub URL being the same path once the branch is merged |
| Exit codes documented: 0 ok, 1 error, 2 conflict, 3 push or pull refused | tested | [tests/test_cli.py](../tests/test_cli.py), usage errors included |

## Markdown through Google's converter

What survives a round trip, file to Doc to file. `tests/fixtures/` holds the byte-for-byte evidence.

| Feature | Status | Owner / evidence |
| --- | --- | --- |
| Headings H1-H6 | tested | fixtures 01, 03 (H1-H3), 09 (H4-H6); the export wraps every heading in `**`, which the normalizer strips |
| Setext headings (underlined with `===` or `---`) | tested | fixture 09: text and level survive, but they come back as ATX `#` and `##`, so a pull rewrites them |
| Bold, italic, links | tested | fixture 01; `_italic_` and `__strong__` come back as `*italic*` and `**strong**` (fixtures 03, 11), `***both***` as it was |
| Strikethrough `~~text~~` | tested | fixture 11 |
| Inline code (single backtick) | tested | fixtures 01, 05: backticks inside, stars, tags, table cells, task lines all survive |
| Nested bullet and numbered lists; a list starting at 5 keeps its start | tested | fixtures 01, 03 (the start at 5); nesting comes back at 2 spaces |
| Bullet markers `*`, `+`, `-`; numbering `1.` and `1)`; a start at 3; nested mixed markers | tested | fixture 12: each comes back as written |
| Two tight lists back to back with a blank line between | tested | fixtures 01, 10: the blank line is dropped, so a pull joins them; where the marker or numbering style changes the lists still re-parse apart; a paragraph between them keeps the blank (fixture 12); a loose list that follows keeps it through its own whitespace line (fixture 10) |
| Checkboxes `- [ ]` / `- [x]`, including state ticked in the Docs UI | tested | fixture 04 |
| Tables, including bold cells | workaround | fixture 01; alignment colons come back on every column, so the normalizer writes `| --- |` and alignment is lost |
| Blockquotes, nested quotes, a list inside a quote | tested | fixtures 01, 10: text and nesting survive; in the Doc a quote is an indented paragraph; a plain quote and a quoted list come back as written, while a quote holding a nested quote comes back with an empty `>` line before its first line and after the nested one, so a pull adds them; a normalizer rule could drop them once the padding is understood |
| Horizontal rules | tested | fixtures 01, 03, 09: `***`, `___` and `- - -` all come back as `---` |
| Footnotes | tested | fixture 01; real Docs footnotes |
| Escaped characters (`\-`, `\[`, `\#`, ...) | workaround | fixtures 03, 04, 07; the normalizer unescapes outside code spans, so a deliberate escape there is dropped on pull unless it keeps a line from becoming a block; the export also escapes a dash right after a code span, dropped since PT-008's real run ([chadkit/work/PT-008.md](../chadkit/work/PT-008.md)); `\+`, `\~` and a `\)` right after digits the export adds stay in the file today, and a `\(` or `\)` the file holds comes back plain (seen in use 2026-10-29 and on this repository's task list; PT-035) |
| Soft line breaks inside a paragraph or list item | workaround | fixture 06: pushed as hard breaks so the Doc keeps the file's lines; a hard break the file had comes back soft; raw, fixture 03 shows them joined; a quote's lines the same since fixture 14 |
| Text typed in the Docs UI after a bold line | tested | fixture 04; it inherits bold, treated as noise unless local had it |
| Fenced code blocks (triple backtick) | workaround | fixture 05: a fence at the left margin is pushed as a code run ([design.md](design.md) "Push form", built by PT-005); lost: the Doc shows monospace lines with no code background, the fence style, a trailing blank line |
| Language tag on a fence | workaround | fixture 05 tests: the Doc cannot hold it; kept from the local file, empty on a fresh pull |
| Indentation, tabs, and blank lines inside a fenced block | tested | fixture 05; pushed as entities, come back as whitespace |
| Trailing whitespace inside a code line | idea | PT-013 [probe 4](../chadkit/work/PT-013/probe-4-whitespace-in-spans.out.md), "Trailing spaces inside code": the export moves them outside the span, so they are no longer code; an entity was not tried |
| Indented code (four spaces) | tested | fixtures 01 `.round2.out.md`, 10: the indent is lost and each line becomes a paragraph, the push form treating it as one today; rewriting it to a fence in the push form is an idea no task owns |
| Fenced code inside a list item | idea | sent as it is today and loses its shape (PT-013 [probe 1](../chadkit/work/PT-013/probe-1-raw-fences.out.md), "Fenced in a list"); a code run inside the item keeps its lines ([probe 6](../chadkit/work/PT-013/probe-6-entities-and-lists.out.md)); no test pins it |
| Native Docs "Code block" building block | not possible | UI only, paid Workspace editions; no API request creates one |
| Raw HTML inside markdown: inline styles such as colour | tested | fixtures 01, 11: the text survives, the tag and its colour are gone; colour cannot show in a markdown export |
| Raw inline HTML tags `<b>`, `<em>`, `<br>`, `<span>`, `<script>` | tested | fixture 11: `<b>` and `<em>` come back as `**` and `*`, `<br>` as a paragraph break, `<span>` as its text, `<script>` and its content dropped |
| HTML comments (`<!-- -->`) | planned | the import drops them, so no export has one; a sync on a Doc-only change, a `pull` and the attach write the export over the file and the comment goes with it, and a line starting with `<` sends every push to the whole replace (`structure`); seen in use 2026-10-29, no fixture yet; PT-034 keeps the file's side ([chadkit/work/PT-034.md](../chadkit/work/PT-034.md)) |
| A resolved task line `- [-]` | planned | seen 2026-10-30 on this repository's task list ([chadkit/work/PT-030.md](../chadkit/work/PT-030.md)): the import makes an open box of it and the export returns `[ ]`, which a sync on a Doc-only change writes back over the `[-]` (PT-034 keeps the file's line); beside checkbox lines it sends every push to the whole replace (`layout`), which no task owns |
| Entity and numeric character references (`&amp;`, `&copy;`, `&#x1F600;`, `&nbsp;`) | tested | fixture 11: decoded to the characters, `&nbsp;` to a real no-break space (U+00A0), and not re-encoded on export (`<` comes back as `\<`, which the normalizer unescapes) |
| Autolinks `<https://...>`, `<mailto:...>` | tested | fixture 11: `<url>` comes back as the bare URL (the export writes `[url](url)`, which the normalizer collapses), `<mailto:a@b>` as `[mailto:a@b](mailto:a@b)` |
| Bare URLs, `www.` names and e-mail addresses (GFM autolink extension) | tested | fixture 11: `https://...` comes back bare, `www.example.com` as `[www.example.com](http://www.example.com)`, an address as `[a@b](mailto:a@b)` |
| Link titles `[text](url "title")` | tested | fixture 11: the title is dropped, the link survives |
| Reference-style links `[text][ref]`, `[ref][]`, `[ref]` and their definitions | tested | fixture 11: each comes back as an inline link and the definitions are gone |
| Tabs and Unicode in text: a tab, accented letters, CJK, emoji, curly quotes, an en dash | tested | fixtures 10, 11 |
| Mermaid and other diagram fences | tested | fixture 14: a code run like any fence, the info string back from the file's own fence; the Doc shows the source lines, not a diagram |
| Alerts (`> [!NOTE]`, `[!WARNING]`, `[!TIP]` pinned; `[!IMPORTANT]` and `[!CAUTION]` share the syntax) | workaround | fixture 14: the push form gives a quote's lines hard breaks, as a paragraph's, so the marker keeps its own line; without them the marker and the text come back on one line, a plain quote ([chadkit/work/PT-024/alerts-no-breaks.out.md](../chadkit/work/PT-024/alerts-no-breaks.out.md)); the export escapes the marker as `\[\!NOTE\]` and the normalizer unescapes it; two alerts back to back come back as one quote with an empty `>` line between, which GitHub would read as one alert (how it renders the second marker is not measured), a layout GitHub's own page advises against; a paragraph between keeps them apart |
| Math: inline `$...$`, a `$$` block, a math fence | workaround | fixture 14: the export escapes `$`, `\` and `_`, which the normalizer drops; a `$` price outside math survives; lost: a `\$` a person wrote inside a formula comes back without its backslash, dropped by the normalizer like the export's own escapes ([tests/test_normalize.py](../tests/test_normalize.py) pins that part; whether the import drops it first is not measured; the `` $`...`$ `` form is not pinned); the Doc shows the source, not the formula |
| Emoji shortcodes (`:tada:`) | tested | fixture 14: the import turns each into its character, so a pull writes `🎉` for `:tada:`; GitHub renders both the same |
| Color chips in code spans (`#0969DA`, `rgb()`, `hsl()`) | tested | fixture 14: code spans as any other |
| Mentions, issue references and commit SHAs | tested | fixture 14: plain text (the export escapes `#1`, the normalizer unescapes it); GitHub links them again |
| `<details>` | not possible | fixtures 01, 14: the tags are dropped; fixture 01's one-line block came back merged into the heading after it, fixture 14's block, with blank lines inside and a paragraph after, as one paragraph of its own; what decides which is not measured |
| Images `![alt](url "title")` | tested | fixture 11: the Doc holds the image; the export writes `![alt][image1]` and a `[image1]: <data:image/png;base64,...> "title"` definition at the end, the URL gone; that form pushes back and exports the same (`.round2.out.md`) |
| Comments and suggestions in the Doc | workaround | a push that edits lines in place keeps every comment on untouched text (the Sync rows above) and the hand formatting there (probe 5's red word, [chadkit/work/PT-009.md](../chadkit/work/PT-009.md)); a whole replace orphans every comment (it stays in the Doc's comment list, its anchor gone) and the script writes each again at its text, re-authored; suggestions and hand formatting still drop on a replace, and an edited paragraph's hand formatting goes with the edit; `pull`, `sync` and `init --doc` stop while a suggestion is pending (the Sync rows above) |
| A list item right after a paragraph line, no blank line between | idea | the real run in [chadkit/work/PT-006.md](../chadkit/work/PT-006.md): the export puts a blank line before the list, so after a push the Doc's text differs from the file's until `pull --force` writes the blank line; a fixture and a normalizer rule could reverse it |
| A loose list (a blank line between items) | tested | fixture 10: the export puts a whitespace-only line before the first item and after each item but the last, which the normalizer reads as blank lines, so the list comes back loose; PT-007's [loose-list probe](../chadkit/work/PT-007/loose-list-probe.out.txt) showed a list loose in one place comes back loose throughout; a tight list stays tight (fixtures 04, 12) and over three round trips (PT-007's [roundtrips probe](../chadkit/work/PT-007/roundtrips-probe.out.txt)) |
| Nested checkbox under a checkbox at deeper levels | tested | fixture 08: a child's indent is its parent's content column (6 under a checkbox, 2 under a bullet, 3 under an ordered item), and the normalizer reads levels relative to the open items |
