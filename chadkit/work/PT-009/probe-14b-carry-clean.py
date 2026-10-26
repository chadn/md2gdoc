# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""Probe 14 on a fresh Doc, since its first run had already replaced the carrier Doc once before failing: two
comments by insertComment (one with a reply), the anchored text read before the whole replace, the replace through
the markdown body as the script does, each comment re-inserted at its text with the author named, its reply
re-added, the orphan deleted."""
import h
from googleapiclient.errors import HttpError

SRC = """# Carry

First paragraph with an ALPHA word.

Second paragraph with a BETA word.
"""
f = h.d.create("PT-009 probe 14b carry comments", h.md2gdoc.push_form(SRC), None)
doc_id = f["doc_id"]
print("doc", doc_id)
open("carry-doc-id.txt", "w").write(doc_id)

def comments():
    d = h.docs.documents().get(documentId=doc_id, includeTabsContent=True, suggestionsViewMode="SUGGESTIONS_INLINE",
                               commentsViewMode="COMMENTS_VIEW_MODE_INCLUDED").execute()
    tab = d["tabs"][0]["documentTab"]
    anchors = tab.get("commentAnchors", {})
    body = "".join(t for _, _, t, _ in h.paragraphs({"body": tab["body"]}))
    out = []
    for c in d.get("comments", []):
        a = anchors.get(c["anchorId"])
        r = a["ranges"][0] if a else None
        out.append({"id": c["commentId"], "status": c["status"], "author": c["headPost"]["author"].get("displayName"),
                    "content": c["headPost"]["content"], "quote": c.get("plainTextQuote"),
                    "anchored": body[r["startIndex"] - 1:r["endIndex"] - 1] if r else None,
                    "replies": [(p["author"].get("displayName"), p["content"]) for p in c.get("replies", [])]})
    return out

def brief(cs):
    return "\n".join(f"  {c['id'][-6:]} {c['status']} anchored={c['anchored']!r} quote={c['quote']!r} by {c['author']!r} "
                     f"{c['content'][:45]!r} replies={c['replies']}" for c in cs)

doc = h.get(doc_id)
for word in ("ALPHA", "BETA"):
    p = h.find(doc, word)
    i = p[0] + p[2].index(word)
    h.batch(doc_id, [{"insertComment": {"content": f"comment on {word}", "range": {"startIndex": i, "endIndex": i + 5}}}])
first = comments()[0]["id"]
h.batch(doc_id, [{"addCommentReply": {"commentId": first, "post": {"content": "a reply"}}}])
before = comments()
print("--- before the whole replace")
print(brief(before))
h.d.update(doc_id, h.md2gdoc.push_form(h.md2gdoc.normalize(h.export_md(doc_id))))
print("--- after the whole replace")
print(brief(comments()))
body = "".join(t for _, _, t, _ in h.paragraphs(h.get(doc_id)))
for c in before:
    needle = c["anchored"]
    i = body.index(needle) + 1
    r = h.batch(doc_id, [{"insertComment": {"content": f"{c['content']} (carried; was by {c['author']})",
                                            "range": {"startIndex": i, "endIndex": i + len(needle)}}}])
    new_id = r["replies"][0]["insertComment"]["commentThread"]["commentId"]
    for author, content in c["replies"]:
        h.batch(doc_id, [{"addCommentReply": {"commentId": new_id, "post": {"content": f"{content} (carried; was by {author})"}}}])
    try:
        h.batch(doc_id, [{"deleteComment": {"commentId": c["id"]}}])
    except HttpError as e:
        print(f"deleteComment {c['id'][-6:]} refused: {e.status_code} {e.reason[:80]}")
print("--- after the carry-over")
print(brief(comments()))
document, _ = h.export_docx(doc_id)
print("docx anchors:", h.comment_anchors(document))
