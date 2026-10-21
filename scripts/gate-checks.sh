#!/usr/bin/env bash
#
# DOES:      Runs the QA gate's checks (chadkit/workflows/qa-gate.md, Checks) over the
#            changes about to land: `chadkit validate`; `chadkit doctor`, failing on any
#            health note except a task waiting on a human and an already-landed commit
#            with no QA-Gate trailer; `chadkit language check` on the changed Markdown
#            (printed, never failing); the script's tests (tests/test_*.py) when the
#            change touches a .py file or fixtures/; and over added lines in .md, .py
#            and .sh files, no line past 120 characters (table rows, URLs, the log and
#            the task lines excepted) and no em dash. Prints the session id the t_qa
#            record and the Session: trailer carry.
# REQUIRES:  The chadkit CLI, git, python3. Run from anywhere inside the repository.
# CHANGES:   Nothing. Reads the tree and the git index only.
#
# EXAMPLE RUN:
#
#   scripts/gate-checks.sh            # changes since main: commits, index, working tree, untracked
#   scripts/gate-checks.sh HEAD~1     # changes since that commit instead of main
#
# EXIT CODE: 0 all checks passed; 1 a check failed.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

since=${1:-main}
status=0
git rev-parse --verify --quiet "$since^{commit}" >/dev/null \
    || { echo "gate: $since is not a commit or branch"; exit 1; }

run() {
    echo "== $*"
    "$@" || { echo "gate: failed: $*"; status=1; }
}

echo "== session ${CLAUDE_CODE_SESSION_ID:-unset (not a Claude Code session)}"

# Changed files: commits since $since, plus the index, plus the working tree, plus untracked.
changed=$( { git diff --name-only "$since"...HEAD 2>/dev/null || git diff --name-only "$since" HEAD;
             git diff --name-only --cached; git diff --name-only;
             git ls-files --others --exclude-standard; } | sort -u | grep -v '^$' )

run chadkit validate

echo "== chadkit doctor"
chadkit doctor
notes=$(chadkit --json doctor | python3 -c '
import json, sys
notes = [n for n in json.load(sys.stdin)["data"]["notes"]
         if n["check"] not in ("waiting", "qa-gate-trailer")]
print(len(notes))')
if [ -z "$notes" ]; then
    echo "gate: could not read doctor's JSON output"
    status=1
elif [ "$notes" != "0" ]; then
    echo "gate: doctor has $notes health note(s) to resolve or record before landing"
    status=1
fi

md=$(printf '%s\n' "$changed" | grep '\.md$' | while read -r f; do [ -f "$f" ] && echo "$f"; done)
if [ -n "$md" ]; then
    echo "== chadkit language check (changed prose; warnings never fail)"
    # shellcheck disable=SC2086
    chadkit language check $md
else
    echo "== chadkit language check: no changed Markdown"
fi

if printf '%s\n' "$changed" | grep -qE '\.py$|^fixtures/'; then
    if ls tests/test_*.py >/dev/null 2>&1; then
        run python3 -m unittest discover -s tests -p 'test_*.py'
    else
        echo "== tests: none yet under tests/ (a .py or fixture change would run them)"
    fi
else
    echo "== tests: not due (no .py or fixture change)"
fi

# Lines past 120 characters, in what a person reads or edits: added lines only, so old text is not judged; a
# table row, a URL, the log and the task lines are exempt. Untracked files are not judged until staged. awk's
# length() counts bytes on macOS, so under LC_ALL=C the UTF-8 continuation bytes are dropped first to count characters.
long=$( git diff -U0 "$since" 2>/dev/null \
    | LC_ALL=C awk '/^\+\+\+ b\//{f=substr($0,7)}
           /^\+[^+]/ && f ~ /\.(md|py|sh)$/ && f !~ /chadkit\/(log|tasks)\.md/ \
           && (t=$0) && gsub(/[\200-\277]/, "", t) >= 0 && length(t) > 121 \
           && $0 !~ /https?:\/\// && $0 !~ /^\+\|/ \
           {print f": "length(t)-1" chars: "substr($0,2,60)"..."}' \
    | sort -u)
if [ -n "$long" ]; then
    echo "== long lines: added lines past 120 characters (wrap them)"
    printf '%s\n' "$long"
    status=1
else
    echo "== long lines: none added"
fi

# Em dashes: none in an added line of the same files. A pattern that must match one writes it as the
# escape, backslash u2014.
emdash=$( git diff -U0 "$since" 2>/dev/null \
    | LC_ALL=C awk '/^\+\+\+ b\//{f=substr($0,7)}
           /^\+[^+]/ && f ~ /\.(md|py|sh)$/ && index($0, "\342\200\224") \
           {print f": "substr($0,2,70)"..."}' \
    | sort -u)
if [ -n "$emdash" ]; then
    echo "== em dashes: added lines carry one (write a normal dash, or \\u2014 in a pattern)"
    printf '%s\n' "$emdash"
    status=1
else
    echo "== em dashes: none added"
fi

if [ "$status" -ne 0 ]; then
    echo "== gate checks FAILED"
    exit 1
fi
echo "== gate checks passed"
