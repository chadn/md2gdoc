# QA gate

The independent adversarial examination a change takes before it lands, and the record it leaves. The procedure
is user-ck's `chadkit/workflows/qa-gate.md` at the revision `workflows.qa-gate.from` names in `chadkit/config.yaml`;
this file holds only this repository's parts, the shared file's Local list. Thresholds are the shared defaults.

## Which commits take it

- Any commit touching a path where a change can alter what the tool promises or how the gate itself works: the
  README and the feature list, which adopters read; the goals, the decision records, the gate workflow and its
  script. The list lives in one place,
  `workflows.qa-gate.paths` in `chadkit/config.yaml`, so `chadkit doctor` names a commit on them that carries no
  trailer. Everything else, the sync script, its tests and the fixtures, is caught by the line count, which leaves
  out `chadkit/tasks.md`, `chadkit/log.md` and `chadkit/work/` (the shared file, Tiers).
- Any diff at or above the light floor, on any path.
- Anything a human asks to have gated, by naming the scope and the focus.

## Standing questions

Beneficiaries: PG-01 a person or agent editing the task list on either side; PG-02 a person or agent who downloads the
one file and runs it on their own machine; PG-03 Chad reading the gate's record; PG-04 a user whose file goes through
Google's converter.

- PG-01: If I change this on either side, do I get my change back, does a real conflict stop rather than guess, and
  can I get back what a sync replaced?
- PG-02: Could I download this one file, run it on my machine from `--help` alone, with no access it does not need?
- PG-03: Was this examined independently before it landed, and does the record show what the examination missed?
- PG-04: Is what survives the round trip proven by a fixture, and is what does not survive written down?

## Checks

`scripts/gate-checks.sh` runs `chadkit validate`; `chadkit doctor`, failing on any health note except a task
waiting on a human and a commit with no QA-Gate trailer, which the stamp about to land resolves; `chadkit language
check` on the changed Markdown (printed, never failing); the sync script's tests under `tests/` when the change
touches a Python file or a fixture; over added lines in `.md`, `.py` and `.sh` files, no line past 120
characters (the evidence folders under [chadkit/work/](../work/) and the `.out.md` exports under
[tests/fixtures/](../../tests/fixtures/), both kept as returned, excepted) and no em
dash; and *linked references*: an added line of a `.md` file that names a file or folder of this repository, in
backticks or not, links to it, so a reader lands on the evidence (the log, the task lines, fenced blocks and the
evidence folders are exempt); and *evidence citations*: every fixture [docs/features.md](../../docs/features.md)
cites exists under [tests/fixtures/](../../tests/fixtures/), and each `tested` row of its converter table cites
a fixture pair, so a status rests on files and not on memory. It prints the session id the trailer below needs.

## The brief, item 2

The decision records the change touches (`chadkit/decisions/`, cited as `PD-NNN`) and the `language.md` rows for
terms the diff uses. There is no separate rules document: the goals and the decision records are the rules.

## Trailers and telemetry

The `t_qa` summary carries, after the gate revision, the manager's session in the fixed shape `session <id>` where
the id is `$CLAUDE_CODE_SESSION_ID`. The commit carries a second trailer, `Session:` with that id.

## History

Adopted 2026-10-21 (PT-010) with the shape of smb-reports' local file, at the shared revision current that day; the
revision followed is always the one the config names. The evidence-citation check was added 2026-10-22 (PT-015)
after the mis-cited-evidence class was confirmed four times (PLR-20261021-05, -07, -08 and PLR-20261022-01).
