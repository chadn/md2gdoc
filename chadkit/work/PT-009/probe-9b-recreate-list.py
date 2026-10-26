# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""Nesting by re-creating the whole list: drop every bullet from 'bullet one' to 'bullet three', zero the
indents, put one tab before the two items that should nest, and create the bullets over the whole range."""
import h

doc_id = open("survey-doc-id.txt").read().strip()
pt0 = {"magnitude": 0, "unit": "PT"}
doc = h.get(doc_id)
first, last = h.find(doc, "bullet one"), h.find(doc, "bullet three")
h.batch(doc_id, [{"deleteParagraphBullets": {"range": {"startIndex": first[0], "endIndex": last[1]}}}])
doc = h.get(doc_id)
first, last = h.find(doc, "bullet one"), h.find(doc, "bullet three")
print("after deleteParagraphBullets, 'nested bullet' indent:", h.find(doc, "nested bullet")[3]["paragraphStyle"].get("indentStart"),
      "text:", repr(h.find(doc, "nested bullet")[2]))
tabs = sorted([h.find(doc, "nested by tab")[0], h.find(doc, "nested bullet")[0]], reverse=True)
reqs = [{"insertText": {"location": {"index": i}, "text": "\t"}} for i in tabs]
reqs.append({"updateParagraphStyle": {"range": {"startIndex": first[0], "endIndex": last[1] + 2},
                                      "paragraphStyle": {"indentStart": pt0, "indentFirstLine": pt0},
                                      "fields": "indentStart,indentFirstLine"}})
reqs.append({"createParagraphBullets": {"range": {"startIndex": first[0], "endIndex": last[1] + 2},
                                        "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
h.batch(doc_id, reqs)
doc = h.get(doc_id)
for needle in ("bullet one", "nested by tab", "nested bullet", "bullet two", "nested fresh", "bullet three"):
    x = h.find(doc, needle)
    print(f"{needle!r}: level={x[3].get('bullet', {}).get('nestingLevel', 0)} list={x[3].get('bullet', {}).get('listId', '')[-6:]}")
print("\n".join(l for l in h.export_md(doc_id).splitlines() if "bullet" in l or "nested" in l))
