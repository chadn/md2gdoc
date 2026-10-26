# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""Make a Doc from markdown with every construct the script handles, then survey how documents.get shows each
one: the structural element, the paragraph style, the text style, the list glyphs. The Doc id is printed and kept
for the edit battery."""
import json
import sys
import h

SRC = """# Heading one

A paragraph with **bold**, *italic*, `code span`, a [link](https://example.com/x), and an emoji 😀 then more.

## Heading two

- bullet one
  - nested bullet
- bullet two

1. first
2. second

- [ ] unticked
- [x] ticked

> a quote line

```python
print("hi")
```

---

| a | b |
|---|---|
| 1 | 2 |

Last paragraph.
"""
f = h.d.create("PT-009 probe 4 survey", h.md2gdoc.push_form(SRC), None)
doc_id = f["doc_id"]
print("doc", doc_id, f["link"])
doc = h.get(doc_id)
h.show(doc)
print("--- lists")
for lid, lst in doc.get("lists", {}).items():
    lvls = lst["listProperties"]["nestingLevels"][:2]
    print(lid[-6:], [(l.get("glyphType"), l.get("glyphSymbol"), l.get("glyphFormat")) for l in lvls])
print("--- text runs of the inline paragraph and the code paragraph")
for needle in ("A paragraph", "print("):
    s, e, t, p = h.find(doc, needle)
    for r in p["elements"]:
        tr = r.get("textRun")
        if tr:
            print(repr(tr["content"]), json.dumps(tr.get("textStyle", {}), ensure_ascii=False))
print("--- quote paragraph style")
print(json.dumps(h.find(doc, "a quote")[3]["paragraphStyle"]))
print("--- every element kind in body")
for el in doc["body"]["content"]:
    kinds = [k for k in el if k not in ("startIndex", "endIndex")]
    if kinds != ["paragraph"]:
        print(el["startIndex"], el["endIndex"], kinds)
print("--- export")
print(h.export_md(doc_id))
with open("survey-doc.json", "w") as fh:
    fh.write(h.dumps(doc))
with open("survey-doc-id.txt", "w") as fh:
    fh.write(doc_id)
