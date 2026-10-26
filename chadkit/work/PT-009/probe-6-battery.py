# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""The edit battery on the survey Doc: every edit a markdown-to-Doc sync would need, each followed by the
markdown export, so the result is read the way the script reads it. Each step is independent; a failure prints
and the next runs."""
import json
import traceback
from googleapiclient.errors import HttpError
import h

doc_id = open("survey-doc-id.txt").read().strip()

def utf16(s):
    return len(s.encode("utf-16-le")) // 2

def step(name, fn):
    print(f"\n=== {name}")
    try:
        fn()
        print("--- export")
        print(h.export_md(doc_id))
    except HttpError as e:
        print("HttpError", e.status_code, e.reason)
    except Exception:
        traceback.print_exc()

def a_word_in_styled_paragraph():
    doc = h.get(doc_id)
    s, e, t, p = h.find(doc, "A paragraph with")
    i = s + utf16(t[:t.index("more")])
    j = s + utf16(t[:t.index("😀")]) + utf16("😀")
    assert j > i
    h.batch(doc_id, [
        {"insertText": {"location": {"index": j}, "text": " (inserted after the emoji by utf-16 index)"}},
        {"deleteContentRange": {"range": {"startIndex": i, "endIndex": i + 4}}},
        {"insertText": {"location": {"index": i}, "text": "MORE"}},
    ])

def b_heading_text():
    doc = h.get(doc_id)
    s, e, t, p = h.find(doc, "Heading one")
    h.batch(doc_id, [{"deleteContentRange": {"range": {"startIndex": s, "endIndex": e - 1}}},
                     {"insertText": {"location": {"index": s}, "text": "Heading uno"}}])
    print("style now:", h.find(h.get(doc_id), "Heading uno")[3]["paragraphStyle"]["namedStyleType"])

def c_paragraph_after_heading():
    doc = h.get(doc_id)
    s, e, t, p = h.find(doc, "Heading two")
    h.batch(doc_id, [{"insertText": {"location": {"index": e - 1}, "text": "\nIntro under heading two."}}])
    doc = h.get(doc_id)
    s2, e2, t2, p2 = h.find(doc, "Intro under")
    print("inherited style:", p2["paragraphStyle"]["namedStyleType"])
    print("--- export with the inherited style")
    print(h.export_md(doc_id))
    h.batch(doc_id, [{"updateParagraphStyle": {"range": {"startIndex": s2, "endIndex": e2},
                                               "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                                               "fields": "namedStyleType"}}])
    print("fixed style:", h.find(h.get(doc_id), "Intro under")[3]["paragraphStyle"]["namedStyleType"])

def d_list_items():
    doc = h.get(doc_id)
    s, e, t, p = h.find(doc, "bullet two")
    s1, e1, t1, p1 = h.find(doc, "bullet one")
    h.batch(doc_id, [
        {"insertText": {"location": {"index": e - 1}, "text": "\nbullet three\nafter the list, no bullet"}},
        {"insertText": {"location": {"index": e1 - 1}, "text": "\n\tnested by tab"}},
    ])
    doc = h.get(doc_id)
    for needle in ("bullet three", "after the list", "nested by tab"):
        x = h.find(doc, needle)
        print(f"inherited: {needle!r} bullet={x[3].get('bullet')}")
    print("--- export with inherited bullets")
    print(h.export_md(doc_id))
    x = h.find(doc, "after the list")
    n = h.find(doc, "nested by tab")
    h.batch(doc_id, [
        {"deleteParagraphBullets": {"range": {"startIndex": x[0], "endIndex": x[1]}}},
        {"createParagraphBullets": {"range": {"startIndex": n[0], "endIndex": n[1]},
                                    "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}},
    ])
    doc = h.get(doc_id)
    for needle in ("after the list", "nested by tab"):
        x = h.find(doc, needle)
        print(f"fixed: {needle!r} bullet={x[3].get('bullet')} indent={x[3]['paragraphStyle'].get('indentStart')}")

def e_delete_paragraph():
    doc = h.get(doc_id)
    s, e, t, p = h.find(doc, "second")
    h.batch(doc_id, [{"deleteContentRange": {"range": {"startIndex": s, "endIndex": e}}}])

def f_link_and_code():
    doc = h.get(doc_id)
    s, e, t, p = h.find(doc, "Last paragraph")
    add = "\nSee the site for more.\nx = 1  # font only\ny = 2  # font and colour"
    h.batch(doc_id, [{"insertText": {"location": {"index": e - 1}, "text": add}}])
    doc = h.get(doc_id)
    l = h.find(doc, "See the site")
    i = l[0] + l[2].index("the site")
    c1 = h.find(doc, "x = 1")
    c2 = h.find(doc, "y = 2")
    mono = {"weightedFontFamily": {"fontFamily": "Roboto Mono", "weight": 400}}
    green = {"foregroundColor": {"color": {"rgbColor": {"red": 0.09411765, "green": 0.5019608, "blue": 0.21960784}}}}
    h.batch(doc_id, [
        {"updateTextStyle": {"range": {"startIndex": i, "endIndex": i + len("the site")},
                             "textStyle": {"link": {"url": "https://example.org/"}}, "fields": "link"}},
        {"updateTextStyle": {"range": {"startIndex": c1[0], "endIndex": c1[1] - 1}, "textStyle": mono,
                             "fields": "weightedFontFamily"}},
        {"updateTextStyle": {"range": {"startIndex": c2[0], "endIndex": c2[1] - 1}, "textStyle": {**mono, **green},
                             "fields": "weightedFontFamily,foregroundColor"}},
    ])

def g_table():
    doc = h.get(doc_id)
    s, e, t, p = h.find(doc, "Last paragraph")
    h.batch(doc_id, [{"insertTable": {"location": {"index": e - 1}, "rows": 2, "columns": 2}}])
    doc = h.get(doc_id)
    tables = [el for el in doc["body"]["content"] if "table" in el]
    t2 = tables[-1]
    print("tables now:", len(tables), "new one at", t2["startIndex"], t2["endIndex"])
    cells = [c for row in t2["table"]["tableRows"] for c in row["tableCells"]]
    words = ["h1", "h2", "v1", "v2"]
    reqs = [{"insertText": {"location": {"index": c["content"][0]["startIndex"]}, "text": w}}
            for c, w in reversed(list(zip(cells, words)))]
    h.batch(doc_id, reqs)

def i_rule_and_quote():
    doc = h.get(doc_id)
    s, e, t, p = h.find(doc, "Last paragraph")
    h.batch(doc_id, [{"insertText": {"location": {"index": e - 1}, "text": "\n---\nquoted by the API"}}])
    doc = h.get(doc_id)
    q = h.find(doc, "quoted by the API")
    pt = lambda n: {"magnitude": n, "unit": "PT"}
    h.batch(doc_id, [{"updateParagraphStyle": {"range": {"startIndex": q[0], "endIndex": q[1]},
                                               "paragraphStyle": {"indentStart": pt(30), "indentFirstLine": pt(30),
                                                                  "indentEnd": pt(30)},
                                               "fields": "indentStart,indentFirstLine,indentEnd"}}])

def j_image():
    doc = h.get(doc_id)
    s, e, t, p = h.find(doc, "Last paragraph")
    h.batch(doc_id, [{"insertInlineImage": {"location": {"index": e - 1},
                                            "uri": "https://www.gstatic.com/images/branding/product/1x/docs_48dp.png"}}])
    md = h.export_md(doc_id)
    print("image lines:", [l[:80] for l in md.splitlines() if "image" in l])
    raise SystemExit  # the export is long; printed trimmed above

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
    r = h.batch(doc_id, [{"insertText": {"location": {"index": e - 1}, "text": " (rev-guarded)"}}],
                requiredRevisionId=rev)
    print("first write ok, new revisionId differs:", r["writeControl"]["requiredRevisionId"] != rev)
    try:
        h.batch(doc_id, [{"insertText": {"location": {"index": e - 1}, "text": " (stale)"}}], requiredRevisionId=rev)
        print("stale write ACCEPTED")
    except HttpError as ex:
        print("stale write refused:", ex.status_code, ex.reason)
    v1 = h.d.version(doc_id)
    h.batch(doc_id, [{"insertText": {"location": {"index": e - 1}, "text": " (bump)"}}])
    print("Drive version moved on a batchUpdate:", v1, "->", h.d.version(doc_id))

def p_suggest_mode():
    doc = h.get(doc_id)
    s, e, t, p = h.find(doc, "Last paragraph")
    r = h.batch(doc_id, [{"insertText": {"location": {"index": e - 1}, "text": " SUGGESTED"}}], writeMode="SUGGEST")
    print("response:", json.dumps(r)[:300])
    doc = h.get(doc_id)
    x = h.find(doc, "Last paragraph")
    for pe in x[3]["elements"]:
        tr = pe.get("textRun")
        if tr and "SUGGESTED" in tr["content"]:
            print("run:", repr(tr["content"]), "suggestedInsertionIds:", tr.get("suggestedInsertionIds"))

def r_highlight_then_whole_replace():
    doc = h.get(doc_id)
    s, e, t, p = h.find(doc, "bullet two")
    yellow = {"backgroundColor": {"color": {"rgbColor": {"red": 1, "green": 1, "blue": 0}}}}
    h.batch(doc_id, [{"updateTextStyle": {"range": {"startIndex": s, "endIndex": e - 1}, "textStyle": yellow,
                                          "fields": "backgroundColor"}}])
    def highlighted():
        doc = h.get(doc_id)
        return [tr["content"] for _, _, _, p in h.paragraphs(doc) for pe in p["elements"]
                if (tr := pe.get("textRun")) and tr.get("textStyle", {}).get("backgroundColor")]
    print("highlighted before whole replace:", highlighted())
    md = h.export_md(doc_id)
    h.d.update(doc_id, h.md2gdoc.normalize(md))
    print("highlighted after whole replace:", highlighted())
    doc = h.get(doc_id)
    print("suggestion runs after whole replace:", [tr["content"] for _, _, _, p in h.paragraphs(doc) for pe in p["elements"]
                                                   if (tr := pe.get("textRun")) and tr.get("suggestedInsertionIds")])

for name, fn in [
    ("a. a word changed and text inserted after an emoji, inside a paragraph with bold and a link", a_word_in_styled_paragraph),
    ("b. a heading's text replaced", b_heading_text),
    ("c. a paragraph inserted after a heading", c_paragraph_after_heading),
    ("d. list items inserted: at the end, after the list, nested by a tab", d_list_items),
    ("e. a numbered item deleted", e_delete_paragraph),
    ("f. a link and two code paragraphs added", f_link_and_code),
    ("g. a 2x2 table inserted and filled", g_table),
    ("i. a rule typed as --- and a quote by indents", i_rule_and_quote),
    ("j. an inline image from a URL", j_image),
    ("k. a heading's level changed", k_heading_level),
    ("o. writeControl.requiredRevisionId as a push guard; Drive version after batchUpdate", o_write_control),
    ("p. SUGGEST write mode", p_suggest_mode),
    ("r. a highlight set by hand, then the script's whole replace", r_highlight_then_whole_replace),
]:
    step(name, fn)
