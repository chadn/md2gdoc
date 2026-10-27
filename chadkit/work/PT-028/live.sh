# Run from the folder that holds live.md, probe.py and h.py (h.py puts md2gdoc.py on the path); the state file
# live.md.gdoc.json the init writes names the Doc for probe.py.
set -u
MD=/Users/chad/src/md2gdoc/md2gdoc.py
run() { echo; echo "\$ md2gdoc $*"; uv run --script $MD "$@"; echo "exit $?"; }
run init live.md --name "PT-028 live proof" --json
echo; echo "\$ probe.py add"; uv run --script probe.py add
run pull live.md
run pull live.md --dry-run
run pull live.md --force
run sync live.md
run sync live.md --dry-run
run sync live.md --json
ID=$(python3 -c "import json; print(json.load(open('live.md.gdoc.json'))['doc_id'])")
rm -f attached.md attached.md.gdoc.json
run init attached.md --doc "$ID"
echo "attached.md exists: $(test -e attached.md && echo yes || echo no)"
run push live.md
echo; echo "--- the file is untouched:"; cat live.md
echo; echo "\$ probe.py resolve"; uv run --script probe.py resolve
run pull live.md
