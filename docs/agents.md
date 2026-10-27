# For agents

How an AI agent, or any script, drives [md2gdoc.py](../md2gdoc.py): `--json` for output it can parse, and hooks
that run a sync around the agent's own reads and writes. The hook recipes are documentation, not code in the
script (PD-002).

## `--json`

On every command, `--json` prints one JSON object on stdout and nothing on stderr; the exit code is the same as
without it. Fields:

| Field | On | Meaning |
|---|---|---|
| `command`, `file`, `dry_run` | every object | what ran, on which file, whether `--dry-run` was given; on an error, read from the arguments as given |
| `exit` | every object | the exit code: 0 done, 1 error, 2 conflict or markers, 3 refused |
| `reason` | every object | one fixed word: `created`, `attached`, `pulled`, `pushed`, `synced`, `status`, `in_sync`, `nothing_to_push`, `conflict`, `markers`, `refused_doc_changed`, `refused_file_changed`, `refused_suggestions`, `error` |
| `message` | every object | the prose the command would have printed, the stderr lines first, joined by newlines |
| `doc_id`, `link` | once the state file is read | the Doc |
| `written`, `pushed` | pull, push, sync, init, once past the refusals | whether the file was written, whether the Doc was; `pushed` is `false` on a dry run |
| `version`, `version_at_sync` | status, and pull, push, sync, init once a push or pull happened | the Drive `version` now, and at the last sync (status) |
| `local_changed`, `doc_changed` | status | which side changed since the last sync; `doc_changed` only without `--dry-run` |
| `suggestions`, `warnings` | pull, sync and `init --doc`, once the Doc was read | how many suggestions are pending in the Doc, counted through the Docs API before the export is read, since the export cannot tell one from the text: any refuses the command (`refused_suggestions`, exit 3, nothing written); `null` when the Doc could not be read that way (the Docs API not enabled, or a profile Google shows no suggestions to), and then `warnings` holds the line that says the Doc went unchecked and why |
| `conflicts` | sync | how many places changed differently on both sides; the markers are in the file |
| `diff` | pull and push with `--dry-run` | the unified diff of what would change |
| `diff_file`, `diff_doc` | sync with `--dry-run`; a conflict carries `diff_file` only | what the merge changes on each side |
| `converter_diff` | after a push or init | how the Doc's text differs from the file after Google's import, empty when it does not ([features.md](features.md) lists what the converter changes) |
| `name` | init | the Doc's title |
| `write`, `requests` | push and sync after a push | how the Doc was written: `edits`, with the number of `batchUpdate` requests, or `replace` |
| `why`, `carried`, `unplaced`, `undeleted` | push and sync after a `replace` | why the whole Doc was replaced, one word: `tick`, `nesting`, `list`, `structure`, `layout`, `blank`, `inline`, `mapping`, `suggestion`, `docs_api` ([design.md](design.md), "Whole-document replace"); the comments written again after it, the anchored texts of those with no place left, and the orphans Google refused to delete |

A usage error (a bad command or flag) is argparse's prose with exit 1, since the flags were not read yet; every
other error is `{"exit": 1, "reason": "error", "message": ...}`.

## Claude Code hooks

The pattern gdoc ships as code ([similar.md](similar.md)): sync before the agent reads the file, sync after it
writes. In Claude Code that is two hooks in the project's `.claude/settings.json`, here for this repository's
[task list](../chadkit/tasks.md) with the command installed by `uv tool install` ([README](../README.md), Install):

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "timeout": 60,
                     "command": "cd \"$CLAUDE_PROJECT_DIR\" && md2gdoc sync chadkit/tasks.md" } ] }
    ],
    "PostToolUse": [
      { "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "if": "Edit(/chadkit/tasks.md)", "timeout": 60,
            "command": "cd \"$CLAUDE_PROJECT_DIR\" && md2gdoc sync chadkit/tasks.md" }
        ] }
    ]
  }
}
```

What happens, per Claude Code's hooks reference (read 2026-10-22,
[hooks](https://code.claude.com/docs/en/hooks), [hooks guide](https://code.claude.com/docs/en/hooks-guide)):

- At session start, the sync runs and its stdout (`synced ...` or `in sync ...`) is added to the agent's context on
  exit 0. A conflict exits 2: for `SessionStart` the stderr goes to the user only, and the agent meets the
  markers when it reads the file. `"matcher": "startup"` on that group limits it to new sessions, skipping resume.
- After every `Edit` or `Write` of that file, the sync pushes the agent's change. The `if` field takes permission
  rules, and an `Edit(path)` rule covers every built-in tool that edits files, `Write` included, while a
  `Write(path)` rule never matches; the leading `/` anchors the path at the project root
  ([permissions](https://code.claude.com/docs/en/permissions)). On a conflict (exit 2) the hook's stderr, the
  `conflict: ...` line, is shown to the agent, which can resolve the markers and edit again; a refusal (exit 3) is a
  non-blocking error whose first stderr line is shown to the user.
- The prose output is what the hooks relay, so the recipe does not pass `--json`; a wrapper script that parses the
  object would.
- `$CLAUDE_PROJECT_DIR` is the project root where the session started; the default hook timeout is 600 seconds.
  The recipe is checked against the two references, not yet against a run in a Claude Code session.

Any unattended runner is the same shape: a cron line or a git `post-commit` hook running `md2gdoc sync FILE` on a
machine that logged in once ([setup.md](setup.md)).
