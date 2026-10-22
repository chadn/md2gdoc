# Goals

## PG-01 - Two-way sync of one markdown file with one native Google Doc

Either side may add a line, edit it, or tick a task done, and gets its change back after a sync. A true conflict
is shown and stops the sync; it is never resolved silently. The text on either side is never lost: what a sync
replaces stays restorable from that side's history.

## PG-02 - Runs for anyone, on any desktop

One file that any person or agent downloads and runs on their own desktop, set up from its own help alone, asking
for the least access to Google the chosen job needs, and running unattended and deterministically.

## PG-03 - Quality assured, audited, and improving

Every change is independently examined before it lands, and what the examination finds is recorded
as evidence rather than fixed silently. The evidence has two uses: it stops defects reaching
adopters, and it shows where the checks themselves fall short, so the checks improve from their own
record.

## PG-04 - Markdown fidelity is proven and documented

The markdown features people use most survive the round trip. Which ones do is proven by fixtures, not assumed,
and which ones do not is written where a user looks before syncing a file.
