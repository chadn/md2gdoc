# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""Live proof helper: `add` writes two comments and a reply through the Docs API on the live Doc; `show` prints
every comment with its anchored text, and the .docx export's anchors."""
import json
import sys

sys.path.insert(0, "/Users/chad/src/md2gdoc/chadkit/work/PT-009")
import h  # noqa: E402

doc_id = json.load(open("live.md.gdoc.json"))["doc_id"]
resp = h.docs.documents().get(documentId=doc_id, includeTabsContent=True, suggestionsViewMode="SUGGESTIONS_INLINE",
                              commentsViewMode="COMMENTS_VIEW_MODE_INCLUDED").execute()
if sys.argv[1] == "add":
    doc = h.get(doc_id)
    for word in ("vendor", "ampersand"):
        p = h.find(doc, word)
        i = p[0] + p[2].index(word)
        r = h.batch(doc_id, [{"insertComment": {"content": f"a comment on {word}",
                                                "range": {"startIndex": i, "endIndex": i + len(word)}}}])
        cid = r["replies"][0]["insertComment"]["commentThread"]["commentId"]
        if word == "vendor":
            h.batch(doc_id, [{"addCommentReply": {"commentId": cid, "post": {"content": "a reply about the vendor"}}}])
    print("added 2 comments and a reply")
else:
    cs = h.md2gdoc.anchored_comments(resp)
    print(f"--- {len(cs)} open comments")
    for c in cs:
        print(f"  anchored={c['anchored']!r} in {c['para']!r} content={c['content']!r} replies={c['replies']}")
    document, _ = h.export_docx(doc_id)
    print("  docx anchors:", h.comment_anchors(document))
