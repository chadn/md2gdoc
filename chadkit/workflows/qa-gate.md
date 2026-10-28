# QA gate

The independent adversarial examination a change takes before it lands, and the record it leaves. The procedure
is user-ck's `chadkit/workflows/qa-gate.md` at the revision `workflows.qa-gate.from` names in `chadkit/config.yaml`;
this file holds only this repository's parts, the shared QA gate file's Local list. Thresholds are the shared
defaults. A change that takes the documentation focus follows user-ck's `chadkit/workflows/docs-gate.md` at the
revision `workflows.docs-gate.from` names, which wins over the shared QA gate file where they differ; its local parts
are under Documentation.

## Which commits take it

- Any commit touching a path where a change can alter what the tool promises or how the gate itself works: the
  README and the feature list, which adopters read; the goals, the decision records, the gate workflow and its
  script. The list lives in one place,
  `workflows.qa-gate.paths` in `chadkit/config.yaml`, so `chadkit doctor` names a commit on them that carries no
  trailer. Everything else, the sync script, its tests and the fixtures, is caught by the line count, which leaves
  out [chadkit/tasks.md](../tasks.md), [chadkit/log.md](../log.md) and [chadkit/work/](../work/) (the shared QA gate
  file, Tiers).
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

## Documentation

The shared documentation focus's Local list, for this repository.

- **Prose formats** beyond `.md` and `.txt`: none. The fixtures under [tests/fixtures/](../../tests/fixtures/) are
  `.md` files, so by the shared rule a change touching only fixtures and their README is all prose and takes the
  focus; a fixture's `.out.md` is Google's output kept as returned, not a claim, so the requester names the
  correctness focus for the fixture bytes as well.
- **Audience**: the question each document class answers and who asks it, for the brief's item 2.
  - [README.md](../../README.md) answers how to install and use the one file and where the rest is written, for
    someone who downloads it and runs it (PG-02).
  - [docs/setup.md](../../docs/setup.md) answers how to do the one-time Google Cloud steps and which access each
    setup grants, for a person at the Cloud console and a terminal.
  - [docs/features.md](../../docs/features.md) answers what the tool does and what survives the round trip, for a
    user deciding whether it fits a file (PG-04), and for the evidence-citation check.
  - [docs/design.md](../../docs/design.md) answers why the script is built this way and what is proven, for the doer
    resuming a task and a maintainer asking why.
  - [docs/agents.md](../../docs/agents.md) answers how an agent or a script drives the tool and reads its output,
    for an agent's author and the person installing its hooks.
  - [docs/similar.md](../../docs/similar.md) answers what else does this and how this tool differs, for someone
    choosing one.
  - [PRIVACY.md](../../PRIVACY.md) answers who receives the user's data, for someone about to consent on the OAuth
    screen.
  - [tests/fixtures/README.md](../../tests/fixtures/README.md) answers what each fixture pair proves and how one is
    made, for someone adding or reading a fixture; a fixture pair under [tests/fixtures/](../../tests/fixtures/)
    answers what Google's converter does to one markdown feature, for the normalizer's tests and for someone reading
    a feature row's evidence.
  - The `--help` text in [md2gdoc.py](../../md2gdoc.py) answers how to run the tool from the terminal, for a person
    with the file alone (PG-02); it sits in a `.py` file, so it takes the focus only when a requester names it.
  - A decision record under [chadkit/decisions/](../decisions/) answers why, and what was given up, for a
    maintainer a year on.
  - A work file under [chadkit/work/](../work/) answers where that task stands and what it measured, for the doer
    resuming it and for Chad reading cold.
  - [chadkit/goals.md](../goals.md) answers what every task is judged against, for the judge and for Chad deciding
    whether a task is worth doing.
  - [chadkit/language.md](../language.md) answers which word a concept goes by, for anyone writing here and for
    `chadkit language check`.
  - This file answers which changes take the gate here and what stays local, for the session acting as manager.
  - [chadkit/README.md](../README.md) answers who writes what in that directory, for a session arriving in it. The
    log, the task list and [chadkit/thoughts.md](../thoughts.md) have no audience line: the CLI owns the shape of
    the first two, and the third is Chad's notes.
- **Questions** this repository adds: none.
- **Variants** on the focus: none; no `docs-model` variant was declared here.

## History

Adopted 2026-10-21 (PT-010) with the shape of smb-reports' local file, at the shared revision current that day; the
revision followed is always the one the config names. The evidence-citation check was added 2026-10-22 (PT-015)
after the mis-cited-evidence class was confirmed four times (PLR-20261021-05, -07, -08 and PLR-20261022-01).
Documentation focus adopted by reference 2026-10-28 (PT-032).
