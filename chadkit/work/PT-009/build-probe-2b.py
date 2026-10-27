# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""Build probe 2b: the export of probe 2's Doc, byte for byte, as fixture 13's .out.md; the .in.md is its source."""
import sys

sys.path.insert(0, "/Users/chad/src/md2gdoc/chadkit/work/PT-009")
import h  # noqa: E402

doc_id = open("build-probe-2-doc-id.txt").read().strip()
SRC = open("/Users/chad/src/md2gdoc/tests/fixtures/12-gfm-list-markers.in.md", encoding="utf-8").read()
SRC += "\n## Boxes\n\n- [ ] open box\n- [x] ticked box\n\nA paragraph with *italic*, ~~struck~~ and a [link](https://example.com/l) and `code`.\n"
open("/Users/chad/src/md2gdoc/tests/fixtures/13-list-kinds.in.md", "w", encoding="utf-8", newline="\n").write(SRC)
out = h.export_md(doc_id)
open("/Users/chad/src/md2gdoc/tests/fixtures/13-list-kinds.out.md", "w", encoding="utf-8", newline="\n").write(out)
print(repr(out[:300]))
print("normalize(out) == normalize(in):", h.md2gdoc.normalize(out) == h.md2gdoc.normalize(SRC))
