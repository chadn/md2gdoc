# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""Print the two checkbox paragraphs of the probe Doc in full, and the list they belong to without text styles."""
import json, sys
sys.path.insert(0, "/Users/chad/src/md2gdoc")
import md2gdoc
from googleapiclient.discovery import build

d = md2gdoc.connect(None)
docs = build("docs", "v1", credentials=d.api._http.credentials, cache_discovery=False)
doc = docs.documents().get(documentId=sys.argv[1]).execute()
for el in doc["body"]["content"]:
    p = el.get("paragraph")
    if not p:
        continue
    text = "".join(r.get("textRun", {}).get("content", "") for r in p["elements"]).rstrip("\n")
    if "tick" in text or "plain" in text:
        print(f"=== {el['startIndex']}-{el['endIndex']} {text!r}")
        print(json.dumps(p, indent=1))
for lid, l in doc.get("lists", {}).items():
    props = l["listProperties"]
    print("=== list", lid, "nesting levels:", len(props["nestingLevels"]))
    for i, n in enumerate(props["nestingLevels"][:2]):
        print("  level", i, {k: v for k, v in n.items() if k != "textStyle"})
print("top-level keys of the doc:", sorted(doc.keys()))
