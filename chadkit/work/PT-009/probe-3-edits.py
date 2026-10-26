# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""On the probe Doc: insert a new item into the checklist after the ticked one, make `Text.` a checkbox
list item with BULLET_CHECKBOX, strike through `unticked`; then export and show what each became."""
import sys
sys.path.insert(0, "/Users/chad/src/md2gdoc")
import md2gdoc
from googleapiclient.discovery import build

doc_id = sys.argv[1]
d = md2gdoc.connect(None)
docs = build("docs", "v1", credentials=d.api._http.credentials, cache_discovery=False)
print("export before:")
print(d.export(doc_id))
# indexes from the dump: 'unticked' 7-16, 'ticked' 16-23, 'plain bullet' 23-36, 'Text.' follows at 37
docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
    {"updateTextStyle": {"range": {"startIndex": 7, "endIndex": 15}, "textStyle": {"strikethrough": True},
                         "fields": "strikethrough"}},
    {"insertText": {"location": {"index": 22}, "text": "\nadded after ticked"}},
]}).execute()
doc = docs.documents().get(documentId=doc_id).execute()
for el in doc["body"]["content"]:
    p = el.get("paragraph")
    if p and "Text." in "".join(r.get("textRun", {}).get("content", "") for r in p["elements"]):
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
            {"createParagraphBullets": {"range": {"startIndex": el["startIndex"], "endIndex": el["endIndex"]},
                                        "bulletPreset": "BULLET_CHECKBOX"}}]}).execute()
        print(f"BULLET_CHECKBOX applied to {el['startIndex']}-{el['endIndex']}")
print("export after:")
print(d.export(doc_id))
