# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""Carrying comments over a whole replace: read each open comment's anchored text before, replace through the
markdown body as the script does, find the text again, insertComment there with the original author named in the
body, deleteComment the orphan. What survives and what changes."""
import json
import h

doc_id = open("carrier-doc-id.txt").read().strip()

def comments():
    d = h.docs.documents().get(documentId=doc_id, includeTabsContent=True, suggestionsViewMode="SUGGESTIONS_INLINE",
                               commentsViewMode="COMMENTS_VIEW_MODE_INCLUDED").execute()
    tab = d["tabs"][0]["documentTab"]
    anchors = tab.get("commentAnchors", {})
    body = "".join(t for _, _, t, _ in h.paragraphs({"body": tab["body"]}))
    out = []
    for c in d.get("comments", []):
        a = anchors.get(c["anchorId"])
        quoted = None
        if a:
            r = a["ranges"][0]
            # indexes are UTF-16; this body is ASCII so Python slicing matches
            quoted = body[r["startIndex"] - 1:r["endIndex"] - 1]
        out.append({"commentId": c["commentId"], "status": c["status"], "author": c["headPost"]["author"].get("displayName"),
                    "content": c["headPost"]["content"], "plainTextQuote": c.get("plainTextQuote"), "anchored_text": quoted,
                    "replies": len(c.get("replies", []))})
    return out

from googleapiclient.errors import HttpError

def brief(cs):
    return [f"{c['commentId'][-6:]} {c['status']} anchored={c['anchored_text']!r} quote={c['plainTextQuote']!r} replies={c['replies']} {c['content'][:40]!r}" for c in cs]

before = comments()
print(f"--- before: {len(before)} comments (the .docx round trips of probes 11 and 12 re-imported the one comment each time)")
print("\n".join(brief(before)))
h.batch(doc_id, [{"addCommentReply": {"commentId": before[0]["commentId"], "post": {"content": "a reply to carry"}}}])
before = comments()
md = h.export_md(doc_id)
h.d.update(doc_id, h.md2gdoc.push_form(h.md2gdoc.normalize(md)))
print("--- after the whole replace")
print("\n".join(brief(comments())))
doc = h.get(doc_id)
body = "".join(t for _, _, t, _ in h.paragraphs(doc))
carried = deleted = 0
for c in before:
    needle = c["plainTextQuote"] or c["anchored_text"]
    if not needle or needle not in body:
        print("no place for", c["commentId"][-6:])
        continue
    i = body.index(needle) + 1
    h.batch(doc_id, [{"insertComment": {"content": f"{c['content']} (carried over; was by {c['author']})",
                                        "range": {"startIndex": i, "endIndex": i + len(needle)}}}])
    carried += 1
    try:
        h.batch(doc_id, [{"deleteComment": {"commentId": c["commentId"]}}])
        deleted += 1
    except HttpError as e:
        print(f"deleteComment {c['commentId'][-6:]} refused: {e.status_code} {e.reason[:90]}")
print(f"carried {carried}, deleted {deleted}")
print("--- after carry-over")
print("\n".join(brief(comments())))
document, _ = h.export_docx(doc_id)
print("docx anchors:", h.comment_anchors(document))
