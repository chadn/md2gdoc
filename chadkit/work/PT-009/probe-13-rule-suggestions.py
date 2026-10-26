# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""Two workaround checks on the carrier Doc: a paragraph with a bottom border as a horizontal rule, and whether a
pending suggestion can be seen before a pull (documents.get with and without suggestions, and the export)."""
import h

doc_id = open("carrier-doc-id.txt").read().strip()
doc = h.get(doc_id)
c = h.find(doc, "Commented")
h.batch(doc_id, [{"insertText": {"location": {"index": c[1] - 1}, "text": "\nrule-below"}}])
doc = h.get(doc_id)
r = h.find(doc, "rule-below")
border = {"color": {"color": {"rgbColor": {}}}, "width": {"magnitude": 1, "unit": "PT"}, "padding": {"magnitude": 1, "unit": "PT"},
          "dashStyle": "SOLID"}
h.batch(doc_id, [
    {"updateParagraphStyle": {"range": {"startIndex": r[0], "endIndex": r[1]}, "paragraphStyle": {"borderBottom": border},
                              "fields": "borderBottom"}},
    {"deleteContentRange": {"range": {"startIndex": r[0], "endIndex": r[1] - 1}}},
])
print("--- export after an empty paragraph with a bottom border")
print(h.export_md(doc_id))

print("\n--- a pending suggestion, three views")
doc = h.get(doc_id)
c = h.find(doc, "Commented")
h.batch(doc_id, [{"insertText": {"location": {"index": c[0]}, "text": "SUGGESTED "}}], writeMode="SUGGEST")
def text(mode):
    d = h.docs.documents().get(documentId=doc_id, suggestionsViewMode=mode).execute()
    return "".join(t for _, _, t, _ in h.paragraphs(d))
inline, without, accepted = text("SUGGESTIONS_INLINE"), text("PREVIEW_WITHOUT_SUGGESTIONS"), text("PREVIEW_SUGGESTIONS_ACCEPTED")
print("SUGGESTIONS_INLINE has SUGGESTED:", "SUGGESTED" in inline)
print("PREVIEW_WITHOUT_SUGGESTIONS has SUGGESTED:", "SUGGESTED" in without)
print("PREVIEW_SUGGESTIONS_ACCEPTED has SUGGESTED:", "SUGGESTED" in accepted)
print("inline != without, so a pending suggestion is detectable:", inline != without)
print("markdown export line:", [l for l in h.export_md(doc_id).splitlines() if "Commented" in l])
d = h.docs.documents().get(documentId=doc_id).execute()
print("default view mode:", d.get("suggestionsViewMode"))
