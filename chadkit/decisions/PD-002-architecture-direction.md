---
status: accepted
date: 2026-10-22
---

# PD-002 - Architecture direction: one downloadable file for anyone, on any desktop

Related: PG-01, PG-02, PG-04, PD-001

## Context and problem

The docs and code had drifted into treating the current state as the end state: run from a clone with `uv`, the
client file and token beside the script, one account, this repository's markdown habits as the flavour, a
500-line target borrowed from a comparison table. Chad's direction (PT-019, the questions and answers in
[chadkit/work/PT-019.md](../work/PT-019.md)): the script is made the best version of itself, independent of its
history but informed by it and by single-file Python CLI practice, for anyone who downloads the one file.

## Decision

- **Distribution.** One file, [md2gdoc.py](../../md2gdoc.py), downloaded from GitHub
  (`github.com/chadn/md2gdoc`) and run as `uv run --script` or made executable, and installable as the command
  `md2gdoc` with
  `uv tool install` from the GitHub URL, which needs a `pyproject.toml` beside the file carrying the name, a
  version, the same three dependencies and a build system, since `uv tool install` reads project metadata, not the
  PEP 723 header. The script stays the one file a person downloads; the pyproject is install plumbing (PT-021). No
  PyPI package. `uv` is the documented way; the three Google libraries are the only
  dependencies, so `pip install` of them and plain `python` also work and the help says so.
- **Name.** `md2gdoc`, the command too. Another tool, benstein/md2gdoc, shares the name; that is fine, and
  [similar.md](../../docs/similar.md) records the overlap.
- **Platforms.** Windows, macOS and Linux, Python 3.11 or later, CI running the tests on all three; CRLF files
  read and written as found; UTF-8 forced on stdout and stderr.
- **Config directory.** A per-user directory holds everything but the state file: `$XDG_CONFIG_HOME/md2gdoc`,
  default `~/.config/md2gdoc`, on macOS and Linux; `%APPDATA%\md2gdoc` on Windows; `MD2GDOC_CONFIG_DIR`
  overrides. No new dependency for the path logic. Shared by name with benstein's tool; their client file is
  `client_secrets.json` and tokens `token-<name>.json`, so the layout below does not collide.
- **Account profiles.** One profile per Google account and scope, each a folder `<config dir>/<account>/` holding
  that account's `client_secret.json` (from a Cloud project under that account) and `token.json`; the scope is
  chosen at the first login (`--scope drive.file`, the default, or `--scope drive`) and remembered in the token.
  `--account NAME` picks the profile, `MD2GDOC_ACCOUNT` names the default, else `default`. So two client files
  from two Google accounts, one with `drive.file` and one with `drive`, switch on the command line.
- **Scope.** `drive.file` stays the default. `drive`, which edits every file the account can open, is for
  syncing existing Docs: the recommended way is a second Google account with few or no Docs, or a new md2gdoc
  account, its own Cloud project, and each existing Doc shared with it as Editor. Service accounts stay
  documented, not implemented, until someone asks.
- **State file.** `FILE.gdoc.json` next to the markdown file, committed, as PD-001 and PT-006 have it.
- **Shape.** One file, no line target; it grows as features land, with sections and readability as the limit.
- **Users.** People and agents equally: prose output by default, `--json` on every command, agent hook recipes as
  docs, not code. Unattended runs are cron and git hooks on a machine that logged in once; CI is out of scope
  until a service-account path exists.
- **One file per command** for now; a folder or list is a later task the state file's shape must not block.
- **Markdown flavour.** GitHub Flavored Markdown is the target, task lists included, then GitHub.com's platform
  layer (mermaid, alerts, math); each proven by fixtures as PG-04 asks. This repository's habits are a fixture
  set, not the definition.
- **User-facing text** (`--help`, README, the script's messages) never names a task id; those live in
  [docs/](../../docs/) and [chadkit/](../). Linking to `github.com/chadn/md2gdoc` from setup or help is fine.
- Kept from PD-001: whole-document replace per push until PT-009 lands; exit codes 0, 1, 2 conflict, 3 refused.

## Consequences

- [setup.md](../../docs/setup.md), [PRIVACY.md](../../PRIVACY.md), [design.md](../../docs/design.md) "Script
  design", the help text and [similar.md](../../docs/similar.md) say the client file and token are next to the
  script; PT-020 moves them, corrects every statement, and rewrites the help (profiles, the pip path).
- The README gains Install and Usage sections listing every command, environment variable and file (PT-021).
- The `drive` path is proven with a second account before its setup text lands (PT-022).
- GFM and the platform layer become fixture tasks (PT-023, PT-024); three-platform CI, CRLF and UTF-8 become
  PT-025; `--json` and the hook recipe PT-026.
- A `pyproject.toml` appears beside the script for `uv tool install` (PT-021); the tests keep importing the file
  directly. The script file is executable (mode 755) so the shebang works once downloaded.
- "Borrowed pieces" in design.md and the coexistence note in similar.md said the opposite of the name and config
  decisions; both are corrected in the PT-019 commit.
