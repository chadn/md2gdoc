# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""PT-034 live probe: a Doc-side edit through the Docs API on this repository's task Doc, as a person typing in the
Doc would leave it: the words ' (live edit)' go at the end of the PT-029 line. `live-edit.py <repo-root>`."""
import json, sys
from pathlib import Path
ROOT = Path(sys.argv[1]); sys.path.insert(0, str(ROOT))
import md2gdoc as m
d = m.connect(None); s = json.load(open(ROOT / "chadkit/tasks.md.gdoc.json"))
doc = d.get_doc(s["doc_id"])
for el in doc["body"]["content"]:
    p = el.get("paragraph")
    if p and "PT-029" in "".join(e.get("textRun", {}).get("content", "") for e in p["elements"]):
        d.batch_update(s["doc_id"], [{"insertText": {"location": {"index": el["endIndex"] - 1}, "text": " (live edit)"}}])
        print("inserted ' (live edit)' at the end of the PT-029 paragraph; version now", d.version(s["doc_id"]))
        break
