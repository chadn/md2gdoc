# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""PT-028: three suggestions made through the API's SUGGEST write mode on the live Doc (an insertion, a deletion,
a style change), then what `documents.get` and the markdown export show of them. `resolve` tries to clear the
inserted one by deleting its text in the normal write mode."""
import json
import sys

import h
import md2gdoc

doc_id = json.load(open("live.md.gdoc.json"))["doc_id"]


def keys(node, path=""):
    """Every `suggested...` key of the document, where it sits."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k.startswith("suggested") and v:
                print(f"  {path}.{k} = {v if isinstance(v, list) else list(v)}")
            else:
                keys(v, f"{path}.{k}")
    elif isinstance(node, list):
        for n, v in enumerate(node):
            keys(v, f"{path}[{n}]")


def show():
    doc = h.get(doc_id)
    print("pending suggestions:", sorted(md2gdoc.pending_suggestions(doc)))
    keys(doc)
    print("--- the export")
    print(h.export_md(doc_id))


if sys.argv[1] == "add":
    doc = h.get(doc_id)
    p = h.find(doc, "suggest an insertion")
    h.batch(doc_id, [{"insertText": {"location": {"index": p[0]}, "text": "SUGGESTED "}}], writeMode="SUGGEST")
    doc = h.get(doc_id)
    p = h.find(doc, "REMOVEME")
    i = p[0] + p[2].index("REMOVEME")
    h.batch(doc_id, [{"deleteContentRange": {"range": {"startIndex": i, "endIndex": i + len("REMOVEME ")}}}],
            writeMode="SUGGEST")
    doc = h.get(doc_id)
    p = h.find(doc, "making bold")
    i = p[0] + p[2].index("bold")
    h.batch(doc_id, [{"updateTextStyle": {"range": {"startIndex": i, "endIndex": i + 4}, "textStyle": {"bold": True},
                                          "fields": "bold"}}], writeMode="SUGGEST")
    show()
elif sys.argv[1] == "resolve":
    doc = h.get(doc_id)
    p = h.find(doc, "SUGGESTED")
    i = p[0] + p[2].index("SUGGESTED")
    h.batch(doc_id, [{"deleteContentRange": {"range": {"startIndex": i, "endIndex": i + len("SUGGESTED ")}}}])
    print("after deleting the suggested insertion's text in the normal write mode:")
    show()
else:
    show()
