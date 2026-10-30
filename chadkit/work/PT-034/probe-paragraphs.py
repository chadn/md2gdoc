# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""PT-034 probe: does the Doc Google makes of fixture 15's push form hold an empty paragraph where its export puts
a blank line before a list that follows a paragraph? `probe-paragraphs.py <repo-root>`; the Doc is trashed."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT))
import md2gdoc  # noqa: E402

d = md2gdoc.connect(None)
text = (ROOT / "tests/fixtures/15-html-comment.in.md").read_text(encoding="utf-8")
made = d.create("md2gdoc PT-034 paragraphs", text, None)
doc = d.get_doc(made["doc_id"])
paras = [el for el in doc["body"]["content"] if "paragraph" in el]
export = md2gdoc.normalize(d.export(made["doc_id"]), text)
print(f"{len(paras)} paragraphs; {len(export.rstrip(chr(10)).split(chr(10)))} export lines")
for el in paras:
    p = el["paragraph"]
    print(repr("".join(e.get("textRun", {}).get("content", "") for e in p["elements"]))[:70], "bullet" if "bullet" in p else "")
try:
    md2gdoc.plan_edits(doc, export, export.replace("track retention", "track retention, edited"))
    print("plan_edits: maps, edits possible")
except md2gdoc.Fallback as e:
    print("plan_edits: Fallback", e.args[0])
d.api.files().update(fileId=made["doc_id"], body={"trashed": True}).execute()
