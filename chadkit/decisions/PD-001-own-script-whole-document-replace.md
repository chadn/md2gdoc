---
status: accepted
date: 2026-10-21
---

# PD-001 - Own script on the Drive API, whole-document replace per push

Related: PG-01, PG-02

## Context and problem

The PT-002 spike (`PT-002.md`) compared ways to read and write a native
Google Doc from markdown. The two Claude connectors need an LLM in the loop and either cannot update in place
(Drive connector: every push is a new file and link) or edit through UTF-16 index arithmetic that the model
recomputes each time (Docs connector). Two-way sync needs a deterministic, unattended writer that keeps one link.

## Considered options

- A. Drive connector in Claude: zero setup, create-only, new link per push.
- B. Google Docs connector in Claude: in-place edits and suggestion mode, non-deterministic, not usable from
  Claude Code, write access to every Doc in the account.
- C. Own script, Drive API only: `files.update` with a `text/markdown` body replaces the whole Doc and keeps its
  id; `files.export` reads it back. Proven in the wild by LucaDeLeo/gdoc.
- C'. Own script, Docs API `batchUpdate`: targeted paragraph edits keep comment anchors on untouched text, but
  cost days of index arithmetic, and whether a checkbox's state can be set is unverified.
- Apps Script: nothing the REST API lacks.

## Decision

C. A single-file Python CLI on the Drive API with the `drive.file` scope. Every push replaces the whole Doc. The
push guard is the Drive `version` integer plus a normalized-export comparison, never `revisionId`, which Google
churns without content changes. Merge is three-way on normalized lines with a stored snapshot as base.

## Consequences

- Comments, suggestions, images, and manual formatting added in the Doc are lost on the next push. Amended
  2026-10-26 (PT-009): the Docs API cannot set a checkbox's state, so C' cannot tick a box; a whole replace
  orphans comments rather than deleting them; the rest of what C' can do is measured in
  [chadkit/work/PT-009.md](../work/PT-009.md).
- Version history gains one unnamed revision per push; no-op pushes are skipped to limit this.
- Fenced code blocks do not survive the converter as written. Amended 2026-10-21 (PT-013): the push sends them
  as code runs, which do; [docs/features.md](../../docs/features.md) lists what that loses.
- Under `drive.file` the script sees only Docs it created; a hand-made Doc needs the broader `drive` scope.
- C' stays open as a later upgrade (hybrid: targeted edits for small diffs); PT-009 is the remedy, to take up when
  comments, suggestions, or formatting in a Doc matter to someone.
