# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""Build probe 1: the questions the hybrid's mapping rests on, on a Doc made from fixture 04 by the script's own
import. The pristine documents.get JSON is kept as a test fixture before any edit."""
import json
import sys

sys.path.insert(0, "/Users/chad/src/md2gdoc/chadkit/work/PT-009")
import h  # noqa: E402

SRC = open("/Users/chad/src/md2gdoc/tests/fixtures/04-task-list.in.md", encoding="utf-8").read()
f = h.d.create("PT-009 build probe 1", h.md2gdoc.push_form(SRC), None)
doc_id = f["doc_id"]
open("build-probe-1-doc-id.txt", "w").write(doc_id)
print("doc", doc_id)
doc = h.get(doc_id)
json.dump(doc, open("04-task-list.doc.json", "w"), indent=1, ensure_ascii=False)
h.show(doc, "pristine")
print("lists:", json.dumps({k: v["listProperties"]["nestingLevels"][0] for k, v in doc.get("lists", {}).items()}))
print("--- export pristine"); print(h.export_md(doc_id))

def step(label, requests, **wc):
    print(f"=== {label}")
    try:
        h.batch(doc_id, requests, **wc)
    except Exception as e:
        print("FAILED:", str(e)[:300]); return None
    d = h.get(doc_id); h.show(d, label); print("--- export"); print(h.export_md(doc_id)); return d

# a. a new item after the ticked item: unticked or ticked?
p = h.find(doc, "T-003")
doc = step("a: insert \\nT-004 after the ticked item", [
    {"insertText": {"location": {"index": p[1] - 1}, "text": "\nT-004 new after the ticked item"}}])
# b. a new item before the first item: joins the list?
p = h.find(doc, "T-001")
doc = step("b: insert 'T-000 before the first\\n' at the first item's start", [
    {"insertText": {"location": {"index": p[0]}, "text": "T-000 before the first\n"}}])
# c. reset styles by field mask, then one bold word, on the Plain paragraph with ADDED text
p = h.find(doc, "Plain paragraph")
s, e = p[0], p[1]
doc = step("c: append ' ADDED' then reset every text style over the paragraph, then bold 'dash'", [
    {"insertText": {"location": {"index": e - 1}, "text": " ADDED"}},
    {"updateTextStyle": {"range": {"startIndex": s, "endIndex": e - 1 + 6}, "textStyle": {},
                         "fields": "bold,italic,strikethrough,underline,weightedFontFamily,foregroundColor,"
                                   "backgroundColor,link"}},
    {"updateTextStyle": {"range": {"startIndex": s + p[2].index("dash"), "endIndex": s + p[2].index("dash") + 4},
                         "textStyle": {"bold": True}, "fields": "bold"}}])
# d. a paragraph at the very top, then NORMAL_TEXT
doc = step("d: insert 'Top line\\n' at index 1", [{"insertText": {"location": {"index": 1}, "text": "Top line\n"}}])
doc = step("d2: NORMAL_TEXT on it", [{"updateParagraphStyle": {"range": {"startIndex": 1, "endIndex": 10},
                                                           "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                                                           "fields": "namedStyleType"}}])
# e. edit inside the styled item: Done -> Finished, then restyle the whole paragraph from the markdown spans
p = h.find(doc, "T-003")
s, e, t = p[0], p[1], p[2]
i = s + t.index("Done")
new_t = t.replace("Done", "Finished")
reqs = [{"deleteContentRange": {"range": {"startIndex": i, "endIndex": i + 4}}},
        {"insertText": {"location": {"index": i}, "text": "Finished"}},
        {"updateTextStyle": {"range": {"startIndex": s, "endIndex": s + len(new_t) - 1}, "textStyle": {},
                             "fields": "bold,italic,strikethrough,underline,weightedFontFamily,foregroundColor,"
                                       "backgroundColor,link"}}]
for word, style, fields in (("inline code", {"weightedFontFamily": {"fontFamily": "Roboto Mono", "weight": 400}},
                             "weightedFontFamily"), ("bold", {"bold": True}, "bold")):
    j = s + new_t.index(word)
    reqs.append({"updateTextStyle": {"range": {"startIndex": j, "endIndex": j + len(word)}, "textStyle": style,
                                     "fields": fields}})
doc = step("e: Done -> Finished inside the styled item, reset, re-span", reqs)
# f. a fresh one-item list after the Notes paragraph, not adjacent to another list
p = h.find(doc, "ADDED")
doc = step("f: insert '\\nfresh item' after the Notes paragraph and createParagraphBullets on it", [
    {"insertText": {"location": {"index": p[1] - 1}, "text": "\nfresh item"}},
    {"createParagraphBullets": {"range": {"startIndex": p[1], "endIndex": p[1] + 10},
                                "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}}])
# g. a fresh checklist item after the fresh item's list (adjacent, different preset)
p = h.find(doc, "fresh item")
doc = step("g: insert '\\nfresh box' after it, deleteParagraphBullets, createParagraphBullets BULLET_CHECKBOX", [
    {"insertText": {"location": {"index": p[1] - 1}, "text": "\nfresh box"}},
    {"deleteParagraphBullets": {"range": {"startIndex": p[1], "endIndex": p[1] + 9}}},
    {"createParagraphBullets": {"range": {"startIndex": p[1], "endIndex": p[1] + 9}, "bulletPreset": "BULLET_CHECKBOX"}}])
# h. a link with the import's look
p = h.find(doc, "T-002")
j = p[0] + p[2].index("vendor")
doc = step("h: link on 'vendor'", [{"updateTextStyle": {"range": {"startIndex": j, "endIndex": j + 6}, "textStyle": {
    "link": {"url": "https://example.com/v"}, "underline": True,
    "foregroundColor": {"color": {"rgbColor": {"red": 0.0666, "green": 0.3333, "blue": 0.8}}}},
    "fields": "link,underline,foregroundColor"}}])
# i. delete the last paragraph: the range from the previous newline
ps = h.paragraphs(doc)
last, prev = ps[-1], ps[-2]
doc = step("i: delete the last paragraph through the previous newline", [
    {"deleteContentRange": {"range": {"startIndex": prev[1] - 1, "endIndex": last[1] - 1}}}])
print("final normalized export:"); print(h.md2gdoc.normalize(h.export_md(doc_id)))
