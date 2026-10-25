#!/usr/bin/env bash
#
# DOES:      Runs the QA gate's checks (chadkit/workflows/qa-gate.md, Checks) over the
#            changes about to land: `chadkit validate`; `chadkit doctor`, failing on any
#            health note except a task waiting on a human and an already-landed commit
#            with no QA-Gate trailer; `chadkit language check` on the changed Markdown
#            (printed, never failing); the script's tests (tests/test_*.py) when the
#            change touches a .py file or tests/; over added lines in .md, .py and .sh
#            files, no line past 120 characters (table rows, URLs, the log, the task
#            lines and the evidence folders under chadkit/work/ excepted) and no em dash;
#            and linked references: an added line of a .md file that names a tracked
#            file or folder, in backticks or not, links to it (the log, the task lines,
#            fenced blocks and the evidence folders excepted); and evidence citations: every
#            fixture docs/features.md cites exists under tests/fixtures/ and each tested row of
#            its converter table cites a fixture pair. Prints the session id the t_qa record and the
#            Session: trailer carry.
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

if printf '%s\n' "$changed" | grep -qE '\.py$|^tests/'; then
    if ls tests/test_*.py >/dev/null 2>&1; then
        run python3 -m unittest discover -s tests -p 'test_*.py'
    else
        echo "== tests: none yet under tests/ (a .py or fixture change would run them)"
    fi
else
    echo "== tests: not due (no .py or fixture change)"
fi

# Lines past 120 characters, in what a person reads or edits: added lines only, so old text is not judged; a
# table row, a URL, the log, the task lines, a work folder's evidence files and a fixture's export (both kept
# byte for byte) are exempt. Untracked files are not judged until staged. awk's length() counts bytes on macOS,
# so under LC_ALL=C the UTF-8 continuation bytes are dropped first to count characters.
long=$( git diff -U0 "$since" 2>/dev/null \
    | LC_ALL=C awk '/^\+\+\+ b\//{f=substr($0,7)}
           /^\+[^+]/ && f ~ /\.(md|py|sh)$/ && f !~ /chadkit\/(log|tasks)\.md/ && f !~ /chadkit\/work\/[^\/]+\// \
           && f !~ /tests\/fixtures\/.*\.out\.md$/ \
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

# Linked references: an added line of a .md file that names a file or folder of the repository links to it. A
# reference is a run of path characters that, taken from the repository root or from the file's own folder, names
# a tracked path (the index included), inside backticks or not; the text and target of a markdown link and a
# reference-link definition are not references. The log, the task lines, lines inside a fenced block and a work
# folder's evidence files are exempt.
unlinked=$( git diff -U0 "$since" 2>/dev/null | python3 -c '
import posixpath, re, subprocess, sys
tracked = set(subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split("\n")) - {""}
folders = {p[: i + 1] for p in tracked for i, ch in enumerate(p) if ch == "/"}
exempt = re.compile(r"^chadkit/(log|tasks)\.md$|^chadkit/work/[^/]+/")
link = re.compile(r"!?\[[^\]]*\]\([^)]*\)|<https?://[^>]*>")
definition = re.compile(r"^[ \t]*\[[^\]]+\]:[ \t]*\S+")
token = re.compile(r"[A-Za-z0-9_./-]+")
fence = re.compile(r"^[ \t]*(`{3,}|~{3,})")
path, lineno, fenced = None, 0, []
for raw in sys.stdin:
    line = raw.rstrip("\n")
    if line.startswith("+++ b/"):
        path = line[6:]
        if not path.endswith(".md") or exempt.search(path):
            path = None
            continue
        fenced, opener = [], None
        for text in open(path, encoding="utf-8", errors="replace"):
            fenced.append(opener is not None)
            m = fence.match(text)
            if m and opener is None:
                opener = m.group(1)
            elif m and m.group(1)[0] == opener[0] and len(m.group(1)) >= len(opener):
                opener = None
        continue
    m = re.match(r"^@@ -\S+ \+(\d+)", line)
    if m:
        lineno = int(m.group(1))
        continue
    if path is None or not line.startswith("+"):
        continue
    n, lineno = lineno, lineno + 1
    if n <= len(fenced) and fenced[n - 1]:
        continue
    folder = path.rsplit("/", 1)[0] + "/" if "/" in path else ""
    for t in token.findall(link.sub(" ", definition.sub(" ", line[1:]))):
        t = t.strip(".,:;")
        if not re.search(r"[A-Za-z]", t):
            continue
        here = posixpath.normpath(folder + t) + ("/" if t.endswith("/") else "")
        if t in tracked or t in folders or here in tracked or here in folders:
            print(f"{path}:{n}: {t} is not a link")
' | sort -u)
if [ -n "$unlinked" ]; then
    echo "== linked references: added lines name a file or folder without linking to it"
    printf '%s\n' "$unlinked"
    status=1
else
    echo "== linked references: every added reference is a link"
fi

# Evidence citations: every fixture docs/features.md cites, on any line, exists under tests/fixtures/, and each
# tested row of the converter table cites a fixture pair (an .in.* and an .out.md). A citation is "fixture NN",
# "fixtures NN, NN" or "fixtures NN and NN"; a backticked `.suffix.md` or `.suffix.html` names the file NN-*.suffix
# of the fixture cited last before it. The whole file is judged, not only added lines, since a fixture can be
# renamed or removed under a citation that did not change. A failure of the check itself fails the gate.
cited=$( python3 -c '
import glob, re
converter = "## Markdown through Google\u0027s converter"
number = re.compile(r"\b[Ff]ixtures?\s+(\d{2}(?:(?:,\s*|,?\s+and\s+)\d{2})*)\b")
suffix = re.compile(r"`(\.[A-Za-z0-9.-]*\.(?:md|html))`")
cell = re.compile(r"\|(?=(?:[^`]*`[^`]*`)*[^`]*$)")   # a pipe outside a code span
def pair(nn):
    return glob.glob(f"tests/fixtures/{nn}-*.in.*") and glob.glob(f"tests/fixtures/{nn}-*.out.md")
section = None
for n, line in enumerate(open("docs/features.md", encoding="utf-8"), 1):
    if line.startswith("## "):
        section = line.rstrip("\n")
    cites = [(m.end(), re.split(r",\s*|\s+and\s+", m.group(1))) for m in number.finditer(line)]
    numbers = [nn for _, nns in cites for nn in nns]
    for nn in sorted(set(numbers)):
        if not glob.glob(f"tests/fixtures/{nn}-*"):
            print(f"docs/features.md:{n}: fixture {nn} has no file under tests/fixtures/")
    for m in suffix.finditer(line):
        before = [nns[-1] for end, nns in cites if end <= m.start()]
        if before and not glob.glob(f"tests/fixtures/{before[-1]}-*{m.group(1)}"):
            print(f"docs/features.md:{n}: no fixture {before[-1]} file ends in {m.group(1)}")
    if section != converter or not line.startswith("|"):
        continue
    cells = [c.strip() for c in cell.split(line.strip().strip("|"))]
    if len(cells) < 3 or cells[0] == "Feature" or cells[0].startswith("---"):
        continue
    if cells[1].strip("`").startswith("tested") and not any(pair(nn) for nn in numbers):
        print(f"docs/features.md:{n}: tested row cites no fixture pair: {cells[0]}")
' | sort -u ) || { echo "gate: the evidence-citation check could not run"; status=1; }
if [ -n "$cited" ]; then
    echo "== evidence citations: docs/features.md cites a fixture that does not exist, or a tested row cites no pair"
    printf '%s\n' "$cited"
    status=1
else
    echo "== evidence citations: every cited fixture exists; every tested converter row cites a pair"
fi

if [ "$status" -ne 0 ]; then
    echo "== gate checks FAILED"
    exit 1
fi
echo "== gate checks passed"
