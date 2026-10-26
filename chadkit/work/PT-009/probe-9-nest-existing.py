# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""An earlier try (not kept) had no tab left to count: the whole replace in probe6b had consumed it. The tab put
back, then the same steps."""
import h

doc_id = open("survey-doc-id.txt").read().strip()
pt0 = {"magnitude": 0, "unit": "PT"}
doc = h.get(doc_id)
n = h.find(doc, "nested by tab")
h.batch(doc_id, [{"deleteParagraphBullets": {"range": {"startIndex": n[0], "endIndex": n[1]}}},
                 {"insertText": {"location": {"index": n[0]}, "text": "\t"}}])
doc = h.get(doc_id)
n = h.find(doc, "nested by tab")
print("ready:", repr(n[2]), n[3].get("bullet"), n[3]["paragraphStyle"].get("indentStart"))
h.batch(doc_id, [
    {"updateParagraphStyle": {"range": {"startIndex": n[0], "endIndex": n[1]},
                              "paragraphStyle": {"indentStart": pt0, "indentFirstLine": pt0},
                              "fields": "indentStart,indentFirstLine"}},
    {"createParagraphBullets": {"range": {"startIndex": n[0], "endIndex": n[1]}, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}},
])
doc = h.get(doc_id)
n = h.find(doc, "nested by tab")
one = h.find(doc, "bullet one")[3]["bullet"]["listId"]
print("after:", repr(n[2]), n[3].get("bullet"), "same list as 'bullet one':", n[3].get("bullet", {}).get("listId") == one)
print("\n".join(l for l in h.export_md(doc_id).splitlines() if "bullet" in l or "nested" in l))
