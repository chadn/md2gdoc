# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""Build probe 2: how documents.get tells a bullet list, an ordered list and a checklist apart, on a Doc made from
fixture 12 plus a checklist; the JSON kept as a test fixture."""
import json
import sys

sys.path.insert(0, "/Users/chad/src/md2gdoc/chadkit/work/PT-009")
import h  # noqa: E402

SRC = open("/Users/chad/src/md2gdoc/tests/fixtures/12-gfm-list-markers.in.md", encoding="utf-8").read()
SRC += "\n## Boxes\n\n- [ ] open box\n- [x] ticked box\n\nA paragraph with *italic*, ~~struck~~ and a [link](https://example.com/l) and `code`.\n"
f = h.d.create("PT-009 build probe 2", h.md2gdoc.push_form(SRC), None)
doc_id = f["doc_id"]
open("build-probe-2-doc-id.txt", "w").write(doc_id)
print("doc", doc_id)
doc = h.get(doc_id)
json.dump(doc, open("12-list-markers.doc.json", "w"), indent=1, ensure_ascii=False)
h.show(doc, "pristine")
for k, v in doc.get("lists", {}).items():
    lv = v["listProperties"]["nestingLevels"]
    print(k[-6:], [(l.get("glyphType"), l.get("glyphSymbol"), l.get("glyphFormat")) for l in lv[:3]])
print("--- export"); print(h.export_md(doc_id))
print("--- runs of the styled paragraph")
p = h.find(doc, "struck")
for el in p[3]["elements"]:
    r = el.get("textRun", {})
    print(repr(r.get("content")), json.dumps(r.get("textStyle")))
