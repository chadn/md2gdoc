# Design

The script's design, promoted from the PT-002 spike on 2026-10-21 and kept current by the tasks that build it
(PT-004 to PT-009). Setup is in `setup.md`; what else exists is in `similar.md`; feature status is in
`features.md`. The spike's evidence and sources stay in `chadkit/work/PT-002.md`.

## Goal and test case

Two-way sync between a local markdown task list and one native Google Doc. Either side may add a task, edit its
text, or tick it done; the script reconciles both. The script is a reusable single-file Python CLI, not tied to any
repository's conventions. The first proof is a scratch Doc, not a real list.

## What is proven (2026-10-21, through the Google Drive connector, same converter as the API)

- Uploading `text/markdown` creates a native Doc. Checkboxes (`- [ ]`, `- [x]`), nested items, headings, bold,
  italic, inline code, links, tables, footnotes, rules survive. A raw fenced code block does not; a code run
  does (Push form, below; PT-013).
- Exporting as `text/markdown` returns the content, including checkbox state and lines typed or ticked in the Docs
  UI, with deterministic noise (see Normalizer under Script design). A second round trip is stable.
- Text typed in the Docs UI inherits the formatting of the text before it: T-004, typed after a bold line, came
  back as `**T-004 ...**`. Treat inline bold or italic on a task line as noise unless the local side had it.

## End state

What the script is built toward, decided in [PD-002](../chadkit/decisions/PD-002-architecture-direction.md): one
downloadable file that runs on Windows, macOS and Linux under `uv` or plain Python; installable as the command
`md2gdoc`; a per-user config directory holding one profile per Google account and scope, each with its own
client file and token, switched by `--account`; `drive.file` by default and `drive` for existing Docs; the state
file next to the markdown, committed; GitHub Flavored Markdown and then GitHub.com's platform layer as the
flavour, proven by fixtures; prose and `--json` output; no line target for the file. Everything below describes
how far the current state has got; where the two differ, the end state wins and a task closes the gap.

## What is not proven (needs real credentials; PT-004 does these first on a scratch Doc)

1. `files.update` with a `text/markdown` media body replaces a native Doc's content in place and keeps its id and
   link. Google's upload guide lists Markdown as an import format for both create and update, and the gdoc project
   relies on it (see [similar.md](similar.md)); still confirm on a scratch Doc. Proven 2026-10-22 by PT-003's probe
   ([chadkit/work/PT-003.md](../chadkit/work/PT-003.md)): same id and link, version 4 to 7.
2. The Drive `version` integer from `files.get` moves on every UI edit, including cosmetic ones, so it is a safe
   but noisy push guard; pair it with an export equality check. Probed 2026-10-22 by PT-004
   ([chadkit/work/PT-004.md](../chadkit/work/PT-004.md)) for API edits: a Docs API `batchUpdate`, style-only or
   `insertText`, moved neither `version` nor `modifiedTime` within about 30 seconds, although it wrote a
   revision; `files.update` moved `version` at once. So a matching `version` does not prove the Doc unchanged,
   and the export comparison cannot be skipped on its word. The UI edit, the case the guard exists for, was read
   by PT-018 the same day: one cosmetic edit in the Docs UI (a bolded phrase) moved `version` from 10 to 15
   within about 100 seconds and to 17 three minutes later, with `modifiedTime` following in two steps, so a UI
   edit does move it, late and by several steps. Settled: `version` is a changed-since signal that may lag, never
   an unchanged proof; the guard compares the export (PT-006), and PT-007 may use a moved `version` only as a
   reason to look sooner.
3. How the Docs UI exports a checkbox nested under a checkbox at deeper levels (one level exported at 6 spaces).
   Settled 2026-10-22 by fixture 08 (PT-004): a child's indent is its parent's content column, 6 under a
   checkbox, 2 under a bullet, 3 under an ordered item, at every depth, and the normalizer's relative levels
   already read it back.

## Google API facts

- Drive API v3, no Docs API needed for whole-document replace:
  `files.create(body={"name": ..., "mimeType": "application/vnd.google-apps.document"}, media_body=<text/markdown>)`,
  `files.update(fileId, media_body=<text/markdown>)`, `files.export(fileId, mimeType="text/markdown")` (10 MB
  limit), `files.get(fileId, fields="id,modifiedTime,headRevisionId,version")`, `revisions.list(fileId)`.
- The real v3 API queries by `name`; the Claude connector queried by `title`. Do not copy connector syntax into code.
- No API names a version. No API creates a code block. No API inserts HTML into an existing Doc.
- Quotas: Drive 325,000 units/min per user; Docs API 60 writes/min per user. Irrelevant at any sync cadence.
- Docs API `batchUpdate` is the only way to edit part of a Doc. It addresses UTF-16 indexes that shift after every
  insert, so it is the expensive path; see "Whole-document replace" below.

## Python

- Single file, PEP 723 inline metadata so `uv run md2gdoc.py ...` installs deps:
  `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`. [pyproject.toml](../pyproject.toml)
  beside it repeats the three for `uv tool install`, which reads project metadata and not the header, and names
  `md2gdoc:cli` as the command (PD-002, PT-021); the tests import the file directly, never the package.
- Any desktop (PD-002, PT-025): the markdown file is read with universal newlines and written back with CRLF when
  it had a CRLF, else LF, on every platform; the state file is always LF, so a Windows checkout does not rewrite a
  committed file; stdout and stderr are reconfigured to UTF-8 at the entry point, so a diff with non-ASCII text
  prints under any console code page. [.github/workflows/tests.yml](../.github/workflows/tests.yml) runs the tests
  on Ubuntu, macOS and Windows.
- Media upload: `googleapiclient.http.MediaIoBaseUpload(io.BytesIO(md.encode()), mimetype="text/markdown")`.
- Import the Google client libraries lazily, inside the auth path, so `tests/` can import the script and run the
  normalizer and merge tests without the libraries installed or any network.

## Script design

- Subcommands: `init` (create the Doc from the markdown file, write the state file), `pull`, `push`, `sync`,
  `status`, each with `--dry-run` and `--json` (one object on stdout and nothing on stderr: `exit`, a fixed
  `reason` word, `message` holding the prose, and what the command recorded, [agents.md](agents.md); PT-026).
  `--help` must explain setup, files, and exit codes. Built by PT-006 and PT-007;
  `--account NAME` picks a profile, a folder under the config directory holding that account's client file
  and token, `--scope` chooses `drive.file` or `drive` at the profile's first login and the token remembers it
  (PD-002, PT-020).
- State file next to the markdown (for example `tasks.md.gdoc.json`): Doc id, link, Drive `version` at last sync,
  the normalized snapshot of what the Doc held after the last sync (the merge base), and the normalized text the
  file held then (`local`, so a converter change in the Doc does not read as a local edit, PT-006). It is
  committed to git, so a clone syncs the same Doc; only the credentials and token stay out (decided 2026-10-21).
- Normalizer (applied to both sides before any comparison; export noise observed in the fixtures and PT-013's
  probes, all reversible; a fence the text already holds and the inside of a code span are left as they are):
  strip `**` wrapping a heading; unescape `\-`, `\[`, `\]`, `\#`, `\_`, `\<`, `\>`, `\:`, `\*`, `\.`, except
  an escape that keeps a line from becoming a bullet, heading, quote, or ordered item, which stays (so a
  deliberate escape elsewhere in a line is dropped on pull); collapse an autolink `[url](url)` to `url`; make a
  table delimiter row `| --- |`; drop trailing whitespace on every line (hard breaks included); re-indent list
  items to 4 spaces per level, the level read from the item's indent relative to the open items above it
  (the export indents a child to its parent's content column: 2 under a bullet, 3 under an ordered item, 6
  under a checkbox; fixture 08); restore the final newline; join nothing (soft
  line breaks are already joined by Docs, which is why the push form sends them as hard breaks). Fold a code
  run back into a fence: two or more consecutive lines that are each one code span, with optional leading
  whitespace outside the span and a hard break (two or more trailing spaces) after every line but the last,
  become a backtick fence whose lines are the spans' text (one pad space stripped from each end when both are
  present) with that leading whitespace kept; a whitespace-only line in the run, first lines included, is a blank
  code line, and a trailing blank line is dropped (the push form adds one to a one-line block, so a lone span is
  never a run). The fence's info string and style are not in the
  Doc: the n-th run takes the info string of the n-th fenced block in the local file when the counts match, else
  none; a tilde fence comes back as a backtick fence.
- Push form (applied to the file just before a push, never written back; fixture 05 `.in.md` is the reference):
  a fenced or tilde-fenced block at the left margin (one indented under a list item is sent as it is and loses
  its shape, the `idea` row in [features.md](features.md)) becomes a code run, one line per code line, each
  wrapped in one more backtick than its longest backtick sequence and padded with a space on both ends when it
  starts or ends with a backtick,
  lines joined by hard breaks (two trailing spaces); leading spaces become `&nbsp;` entities and leading tabs
  `&#9;`, both outside the span, since Google's import strips real leading whitespace on a continuation line; a
  blank code line becomes `&nbsp;` with the hard break, and a one-line block gets one appended (it exports as a
  lone-space line, fixture 06). Trailing whitespace inside a code line is lost (the export moves it outside the
  span). A line the Doc would join onto the next (a paragraph line, list item, or continuation line followed by
  another line of the same paragraph or item) gets a hard break, so the Doc keeps the file's lines (fixture 06),
  except a span-only line before another span-only or blank line, which would read as a code run; a hard break
  the file already had comes back as a soft one. Everything else passes through. Built in
  [md2gdoc.py](../md2gdoc.py) as `push_form()` and `normalize()`, tested by
  [tests/test_normalize.py](../tests/test_normalize.py).
- Merge: three-way on normalized lines, base = snapshot, ours = local file, theirs = Doc export. Added lines on
  either side are kept; a line changed on one side only takes that change; a checkbox ticked on one side wins
  over an untouched box. A line deleted on one side and edited on the other is a conflict, not a silent delete.
  Lines added at the same place on both sides are all kept, the file's first, since nothing is lost that way; git
  would call that a conflict. Nothing in the Doc outside the markdown's content needs to survive a push (PD-001).
  Recovery when a merge goes wrong is history on each side: git for the file, Drive version history for the Doc,
  which is what PG-01 rests on. The merge is `merge3()` in [md2gdoc.py](../md2gdoc.py): pure Python on
  `difflib` matching blocks, no `git merge-file` (gdoc-sync's first choice, below), so it runs the same on every
  desktop with nothing installed (PT-007). The file is written only when the merge changed it, and then in
  normalized form, as `pull` writes it.
- True conflict (same line changed differently on both sides): keep both lines, marked
  `<<<<<<< api-edited` ... `=======` ... `>>>>>>> hand-edited`, written to the file, exit code 2, no push; a file
  that still holds a marker line is refused with exit 2 until it is resolved.
- Push guard: before `files.update`, export and compare normalized text to the snapshot; abort (exit 3) if the
  content moved. The Drive `version` is stored and shown but never trusted alone, since a match is not proof
  ("What is not proven", item 2; PT-007 may let it skip the export once PT-018 reads the UI case). `pull` has the
  mirror guard on the file, lifted by `--force`. Skip the push when the file's normalized text is what the last
  sync sent, so no empty revisions. Do not use `revisionId` (see [similar.md](similar.md)).
- After a successful push, pull once more and store the new `version` and snapshot. In `sync` the guard is a
  second export right before the push, compared to the one the merge read: a Doc that changed meanwhile refuses the
  push with exit 3, and the merge already written to the file waits for the next run. The `version` is not
  consulted, since a UI edit moves it late (item 2). When one side is unchanged since the last sync the other side
  is the result without a merge, so the converter's own difference between the two stored texts (the blank line
  before a list, [features.md](features.md)) never reads as a conflict.

## Whole-document replace: must every push replace the Doc?

Not necessarily, but the alternative is costly. Options, in order of effort:

a. Whole replace via `files.update` (recommended for v1): one call, deterministic. Side effects: comments and
   suggestions anchored in the Doc are lost on the next push, manual formatting in the Doc is lost, and version
   history gains one unnamed revision per push (skipping no-op pushes limits this).
b. Targeted edits via Docs API `batchUpdate`: pull the document JSON, map paragraphs to markdown lines, delete and
   insert only the changed paragraphs, re-apply the checkbox bullet. Untouched paragraphs keep their comments.
   Whether the Docs API can set a checkbox's checked state is unverified; if it cannot, option b cannot tick a box
   and would need to be combined with a. Expect several days of work and index arithmetic bugs.
c. Hybrid: b for small diffs, a when the diff is large or b fails. Needs b first.

## Borrowed pieces and what the tool review settled

- From benstein/md2gdoc (PT-017, [similar.md](similar.md)): *account profiles*, `--account NAME`, which PD-002
  widens to a client file and token per profile under the config directory; setup steps printed by the script
  itself when the client file is missing; `supportsAllDrives=True` on the create so a folder on a shared drive
  works; the config directory `~/.config/md2gdoc/` itself (PT-020). The command name `md2gdoc` is shared with
  that tool by decision (PD-002).

- In-place update is proven in the wild: gdoc ships `files.update` with a `text/markdown` body on the same Doc id
  (`gdoc/api/drive.py:176-200`) and its 20-star user base depends on the link surviving. Item 1 under "What is not
  proven" drops from a design risk to a confirmation step on the first scratch run.
- `revisionId` is the wrong change signal: two projects found this independently. gdoc-sync rejects it because
  Google issues new ids without content changes and uses a text fingerprint instead; gdoc uses the Drive `version`
  integer and still records false conflicts when someone only touches formatting in the UI. The push guard
  therefore reads `version`, and on a mismatch exports and compares normalized text to the snapshot; only a real
  content change aborts the push. `revisionId` is not stored at all.
- None of the three does checkboxes, so there is nothing to fork. Build, borrowing three pieces:
  gdoc-sync `src/gdoc_sync/merge.py` (diff3 via `git merge-file` with pure-Python fallback, no Google deps),
  md-gdoc `src/md_gdoc/unescape.py` `clean()` (the escape list), gdoc `gdoc/api/drive.py` `update_doc_content`
  and `export_doc` (the two Drive calls with `fields="version"`).
- Keep `drive.file`; all three take full Drive access, which is the main reason not to adopt any of them as is.
