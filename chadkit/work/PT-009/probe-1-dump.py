# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""Create a Doc from a two-box task list and print how each paragraph and its list look in documents.get."""
import json, sys
sys.path.insert(0, "/Users/chad/src/md2gdoc")
import md2gdoc
from googleapiclient.discovery import build

d = md2gdoc.connect(None)
made = d.create("md2gdoc PT-009 checkbox probe", "# Probe\n\n- [ ] unticked\n- [x] ticked\n- plain bullet\n\nText.\n", None)
print("created", made["doc_id"])
docs = build("docs", "v1", credentials=d.api._http.credentials, cache_discovery=False)
doc = docs.documents().get(documentId=made["doc_id"]).execute()
for el in doc["body"]["content"]:
    p = el.get("paragraph")
    if not p:
        continue
    text = "".join(r.get("textRun", {}).get("content", "") for r in p["elements"]).rstrip("\n")
    print(f"--- {el['startIndex']}-{el['endIndex']} {text!r}")
    print("   bullet:", json.dumps(p.get("bullet")))
    print("   style keys:", sorted(k for k in p.get("paragraphStyle", {})))
    for r in p["elements"]:
        if "textRun" in r:
            print("   textRun style:", json.dumps(r["textRun"].get("textStyle")))
print("lists:", json.dumps(doc.get("lists"), indent=1)[:3000])
print("doc id for the next step:", made["doc_id"])
