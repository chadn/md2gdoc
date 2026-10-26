# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""The Docs API's own comment support (discovery revision 20261021) on the probe-5 Doc, whose four comments a
whole replace orphaned: read them with commentsViewMode, insert one anchored to a range, read it back three ways."""
import json
import h

doc_id = open("comments-doc-id.txt").read().strip()

def comments_view(label):
    doc = h.docs.documents().get(documentId=doc_id, commentsViewMode="COMMENTS_VIEW_MODE_INCLUDED", includeTabsContent=True, suggestionsViewMode="SUGGESTIONS_INLINE").execute()
    print("top-level keys:", sorted(doc))
    tab = doc["tabs"][0]["documentTab"]
    print("tab keys:", sorted(tab))
    if "body" not in doc:
        doc["body"] = tab["body"]
    if "comments" not in doc:
        doc["comments"] = tab.get("comments", []) or doc.get("tabs", [{}])[0].get("comments", [])
    print("anchors:", json.dumps(tab.get("commentAnchors", doc.get("commentAnchors")), ensure_ascii=False)[:800])
    print(f"--- documents.get comments {label}: commentsViewMode={doc.get('commentsViewMode')}")
    for c in doc.get("comments", []):
        print("  ", json.dumps(c, ensure_ascii=False)[:600])
    return doc

doc = comments_view("after the whole replace")
s, e, t, p = h.find(doc, "Delta paragraph")
i = s + t.index("red word")
r = h.batch(doc_id, [{"insertComment": {"content": "API comment on the red word", "range": {"startIndex": i, "endIndex": i + 8}}}])
print("--- insertComment response")
print(json.dumps(r["replies"], ensure_ascii=False)[:800])
comments_view("after insertComment")
document, comments = h.export_docx(doc_id)
print("--- docx export anchors:", h.comment_anchors(document), "comments:", h.comment_texts(comments))
print("--- drive comments.list")
for c in h.drive.comments().list(fileId=doc_id, fields="comments(id,content,anchor,author,quotedFileContent)").execute()["comments"]:
    print("  ", json.dumps(c, ensure_ascii=False)[:300])
