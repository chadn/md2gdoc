# /// script
# requires-python = ">=3.11"
# ///
"""The Docs API discovery document, read for what the reference pages scatter: every batchUpdate request type,
the bullet and list schemas, the comment schemas, the write control."""
import json
import urllib.request

with urllib.request.urlopen("https://docs.googleapis.com/$discovery/rest?version=v1") as r:
    d = json.load(r)
s = d["schemas"]
print("discovery revision:", d.get("revision"))
req = sorted(s["Request"]["properties"])
print(len(req), "request types:", ", ".join(req))
for name in ("Bullet", "NestingLevel", "CreateParagraphBulletsRequest", "WriteControl", "InsertCommentRequest",
             "CommentThread", "CommentAnchor", "ParagraphElement"):
    props = s[name]["properties"]
    print(f"{name}: {', '.join(props)}")
    for k, v in props.items():
        if "enum" in v:
            print(f"  {k} enum: {v['enum']}")
g = d["resources"]["documents"]["methods"]["get"]["parameters"]
print("documents.get parameters:", ", ".join(g))
print("commentsViewMode:", g["commentsViewMode"]["enum"])
print("suggestionsViewMode:", g["suggestionsViewMode"]["enum"])
