# ChadKit directory

ChadKit-owned project state lives here. The ChadKit version this project follows is
declared once, in `config.yaml`.

Artifacts appear only once something is first written to them, so an absent `goals.md`,
`tasks.md`, `tasks-archive.md`, `log.md`, `language.md`, `decisions/`, or `workflows/` is
normal, not a missing piece.

Who writes what:

- Structured record mutation, such as allocating a PT- or PLR- id, completing a task, changing
  a task's bracket fields, or appending a log record, goes through the `chadkit` CLI.
- Prose, such as goals, terminology, decision records, workflows, and task or goal text,
  including this file, is edited normally.
- `thoughts.md` is never edited by tooling or agents (`init` only seeds it); jot anything, no format.

See the ChadKit model for the rules this directory follows; `chadkit model` says where it is.
