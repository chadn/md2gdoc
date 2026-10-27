set -u
MD=/Users/chad/src/md2gdoc/md2gdoc.py
run() { echo; echo "\$ md2gdoc $*"; uv run --script $MD "$@"; echo "exit $?"; }
run init live.md --name "PT-009 live proof" --json
echo; echo "\$ comments.py add"; uv run --script comments.py add
echo; echo "\$ comments.py show"; uv run --script comments.py show
echo; echo "--- edit: Call -> Phone the vendor; a new paragraph under Notes; T-004 after T-003"
python3 - <<'PY'
import pathlib
p = pathlib.Path("live.md"); s = p.read_text()
s = s.replace("Call the vendor", "Phone the vendor").replace("## Notes\n", "## Notes\n\nA new paragraph, written by the edit path.\n")
s = s.replace("and **bold**\n", "and **bold**\n- [ ] T-004 a new box, inherited from T-003\n")
p.write_text(s)
PY
run push live.md --json
run status live.md
echo; echo "\$ comments.py show"; uv run --script comments.py show
echo; echo "--- edit: tick T-002; T-003 Done -> Finished"
python3 - <<'PY'
import pathlib
p = pathlib.Path("live.md"); s = p.read_text()
p.write_text(s.replace("- [ ] T-002", "- [x] T-002").replace("T-003 Done item", "T-003 Finished item"))
PY
run sync live.md --json
echo; echo "\$ comments.py show"; uv run --script comments.py show
run sync live.md
echo; echo "--- the file after the run"; cat live.md
echo; echo "--- the state file's snapshot equals its local text:"; python3 -c "import json; s=json.load(open('live.md.gdoc.json')); print(s['snapshot']==s['local'], 'version', s['version'])"
