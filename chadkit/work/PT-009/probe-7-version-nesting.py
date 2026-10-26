# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""Two follow-ups on the survey Doc: does the Drive `version` move after a batchUpdate, and when; can
createParagraphBullets nest by leading tabs when the whole list is made in one request."""
import time
import h

doc_id = open("survey-doc-id.txt").read().strip()

print("=== Drive version after a batchUpdate")
v0 = h.d.version(doc_id)
doc = h.get(doc_id)
s, e, t, p = h.find(doc, "Intro under")
h.batch(doc_id, [{"insertText": {"location": {"index": s}, "text": "(v) "}}])
print("before:", v0, "right after:", h.d.version(doc_id))
for wait in (5, 15, 30, 60):
    time.sleep(wait)
    print(f"after {wait}s more:", h.d.version(doc_id))

print("\n=== a fresh three-level list from tabbed paragraphs in one createParagraphBullets")
doc = h.get(doc_id)
s, e, t, p = h.find(doc, "quoted by the API")
h.batch(doc_id, [{"insertText": {"location": {"index": e - 1}, "text": "\nlevel a\n\tlevel b\n\t\tlevel c"}}])
doc = h.get(doc_id)
a = h.find(doc, "level a")
c = h.find(doc, "level c")
# the inserted paragraphs inherited the quote's indents; clear them first so only the tabs count
pt0 = {"magnitude": 0, "unit": "PT"}
h.batch(doc_id, [
    {"updateParagraphStyle": {"range": {"startIndex": a[0], "endIndex": c[1]},
                              "paragraphStyle": {"indentStart": pt0, "indentFirstLine": pt0, "indentEnd": pt0},
                              "fields": "indentStart,indentFirstLine,indentEnd"}},
    {"createParagraphBullets": {"range": {"startIndex": a[0], "endIndex": c[1]}, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}},
])
doc = h.get(doc_id)
for needle in ("level a", "level b", "level c"):
    x = h.find(doc, needle)
    print(f"{needle!r}: text={x[2]!r} bullet={x[3].get('bullet')} indentStart={x[3]['paragraphStyle'].get('indentStart')}")
print("--- export lines")
print("\n".join(l for l in h.export_md(doc_id).splitlines() if "level" in l))
