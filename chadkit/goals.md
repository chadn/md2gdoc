# Goals

## PG-01 - Two-way sync of one markdown file with one native Google Doc

Either side may add a line, edit it, or tick a task done; `sync` reconciles both without losing either side's
change. A true conflict is shown with markers and stops the push; it is never resolved silently.

## PG-02 - Reusable by any project

One Python file with no repository-specific conventions. `--help` and in-file comments are enough to set it up and
run it. It can run unattended: git hook, cron, CI, no LLM in the loop.

## PG-03 - Quality assured, audited, and improving

Every change is independently examined before it lands, and what the examination finds is recorded
as evidence rather than fixed silently. The evidence has two uses: it stops defects reaching
adopters, and it shows where the checks themselves fall short, so the checks improve from their own
record.
