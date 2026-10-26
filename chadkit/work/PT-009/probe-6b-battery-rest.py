# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""The battery's remaining steps on the survey Doc, after probe6 stopped at the image step."""
import json
import traceback
from googleapiclient.errors import HttpError
import h

doc_id = open("survey-doc-id.txt").read().strip()

def utf16(s):
    return len(s.encode("utf-16-le")) // 2

def step(name, fn, export=True):
    print(f"\n=== {name}")
    try:
        fn()
        if export:
            print("--- export")
            print("\n".join(l for l in h.export_md(doc_id).splitlines() if not l.startswith("[image1]:")))
    except HttpError as e:
        print("HttpError", e.status_code, e.reason)
    except Exception:
        traceback.print_exc()

def a_word_in_styled_paragraph():
    doc = h.get(doc_id)
    s, e, t, p = h.find(doc, "A paragraph with")
    i = s + utf16(t[:t.index("more")])
    j = s + utf16(t[:t.index("😀")]) + utf16("😀")
    assert i > j
    print("python index of 'more':", t.index("more"), "utf-16 index:", i - s)
    h.batch(doc_id, [
        {"deleteContentRange": {"range": {"startIndex": i, "endIndex": i + 4}}},
        {"insertText": {"location": {"index": i}, "text": "MORE"}},
        {"insertText": {"location": {"index": j}, "text": " (inserted after the emoji by utf-16 index)"}},
    ])

def d2_nesting():
    doc = h.get(doc_id)
    n = h.find(doc, "nested by tab")
    pt = lambda v: {"magnitude": v, "unit": "PT"}
    # try 1: indent the existing item one level deeper, as the UI's Tab does
    h.batch(doc_id, [{"updateParagraphStyle": {"range": {"startIndex": n[0], "endIndex": n[1]},
                                               "paragraphStyle": {"indentStart": pt(72), "indentFirstLine": pt(54)},
                                               "fields": "indentStart,indentFirstLine"}}])
    x = h.find(h.get(doc_id), "nested by tab")
    print("after indent 72/54: bullet", x[3].get("bullet"))
    print("--- export after indenting")
    print("\n".join(l for l in h.export_md(doc_id).splitlines() if "bullet" in l or "nested" in l))
    # try 2: a fresh item, inserted after 'bullet two' with a tab, bullets removed then re-created
    doc = h.get(doc_id)
    b2 = h.find(doc, "bullet two")
    h.batch(doc_id, [{"insertText": {"location": {"index": b2[1] - 1}, "text": "\n\tnested fresh"}}])
    doc = h.get(doc_id)
    nf = h.find(doc, "nested fresh")
    h.batch(doc_id, [{"deleteParagraphBullets": {"range": {"startIndex": nf[0], "endIndex": nf[1]}}}])
    doc = h.get(doc_id)
    nf = h.find(doc, "nested fresh")
    print("text after deleteParagraphBullets:", repr(nf[2]))
    h.batch(doc_id, [{"createParagraphBullets": {"range": {"startIndex": nf[0], "endIndex": nf[1]},
                                                 "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}}])
    x = h.find(h.get(doc_id), "nested fresh")
    print("after delete+create with tab: bullet", x[3].get("bullet"), "text", repr(x[2]))
    old = h.find(h.get(doc_id), "bullet two")[3]["bullet"]["listId"]
    print("same list as 'bullet two':", x[3].get("bullet", {}).get("listId") == old)

def k_heading_level():
    doc = h.get(doc_id)
    s, e, t, p = h.find(doc, "Heading two")
    h.batch(doc_id, [{"updateParagraphStyle": {"range": {"startIndex": s, "endIndex": e},
                                               "paragraphStyle": {"namedStyleType": "HEADING_3"},
                                               "fields": "namedStyleType"}}])

def o_write_control():
    doc = h.get(doc_id)
    rev = doc["revisionId"]
    s, e, t, p = h.find(doc, "Last paragraph")
    r = h.batch(doc_id, [{"insertText": {"location": {"index": s}, "text": "(rev-guarded) "}}],
                requiredRevisionId=rev)
    print("first write ok; response revisionId differs from the one sent:", r["writeControl"]["requiredRevisionId"] != rev)
    try:
        h.batch(doc_id, [{"insertText": {"location": {"index": s}, "text": "(stale) "}}], requiredRevisionId=rev)
        print("stale write ACCEPTED")
    except HttpError as ex:
        print("stale write refused:", ex.status_code, ex.reason)
    v1 = h.d.version(doc_id)
    h.batch(doc_id, [{"insertText": {"location": {"index": s}, "text": "(bump) "}}])
    print("Drive version moved on a batchUpdate:", v1, "->", h.d.version(doc_id))

def p_suggest_mode():
    doc = h.get(doc_id)
    s, e, t, p = h.find(doc, "Last paragraph")
    r = h.batch(doc_id, [{"insertText": {"location": {"index": s}, "text": "SUGGESTED "}}], writeMode="SUGGEST")
    print("response:", json.dumps(r)[:300])
    doc = h.get(doc_id)
    x = h.find(doc, "Last paragraph")
    for pe in x[3]["elements"]:
        tr = pe.get("textRun")
        if tr and "SUGGESTED" in tr["content"]:
            print("run:", repr(tr["content"]), "suggestedInsertionIds:", tr.get("suggestedInsertionIds"))
    print("export line:", [l for l in h.export_md(doc_id).splitlines() if "Last paragraph" in l])

def r_highlight_then_whole_replace():
    doc = h.get(doc_id)
    s, e, t, p = h.find(doc, "bullet two")
    yellow = {"backgroundColor": {"color": {"rgbColor": {"red": 1, "green": 1, "blue": 0}}}}
    h.batch(doc_id, [{"updateTextStyle": {"range": {"startIndex": s, "endIndex": e - 1}, "textStyle": yellow,
                                          "fields": "backgroundColor"}}])
    def runs(key):
        doc = h.get(doc_id)
        return [tr["content"] for _, _, _, p in h.paragraphs(doc) for pe in p["elements"]
                if (tr := pe.get("textRun")) and (tr.get("textStyle", {}).get(key) or tr.get(key))]
    print("highlighted before whole replace:", runs("backgroundColor"))
    print("suggested before whole replace:", runs("suggestedInsertionIds"))
    md = h.export_md(doc_id)
    print("paragraphs before:", len(h.paragraphs(h.get(doc_id))), "export lines:", len(md.splitlines()))
    h.d.update(doc_id, h.md2gdoc.normalize(md))
    print("highlighted after whole replace:", runs("backgroundColor"))
    print("suggested after whole replace:", runs("suggestedInsertionIds"))
    print("paragraphs after:", len(h.paragraphs(h.get(doc_id))), "export lines:", len(h.export_md(doc_id).splitlines()))

for name, fn, ex in [
    ("a. a word changed and text inserted after an emoji, inside a paragraph with bold and a link", a_word_in_styled_paragraph, True),
    ("d2. nesting an existing list item: by indent, and by delete+create with a tab", d2_nesting, True),
    ("k. a heading's level changed", k_heading_level, True),
    ("o. writeControl.requiredRevisionId as a push guard; Drive version after batchUpdate", o_write_control, False),
    ("p. SUGGEST write mode", p_suggest_mode, False),
    ("r. a highlight set by hand and the suggestion, then the script's whole replace", r_highlight_then_whole_replace, True),
]:
    step(name, fn, ex)
