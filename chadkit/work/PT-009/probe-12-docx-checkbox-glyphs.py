# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""The .docx export writes a checklist as a list with an empty glyph, which comes back as bullets. Does the import
read any .docx form as a checklist? Three variants of the carrier's numbering, each sent through files.update and
read through the markdown export: Word's ballot-box glyphs U+2610 and U+2611 as the level text, the same in the
MS Gothic font Word uses, and a w14:checkbox content control on the run."""
import io
import re
import zipfile
from googleapiclient.http import MediaIoBaseUpload
import h

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
doc_id = open("carrier-doc-id.txt").read().strip()
raw = open("carrier-export.docx", "rb").read()

def rewrite(raw, edits):
    """edits: {member: fn(xml) -> xml}"""
    src = zipfile.ZipFile(io.BytesIO(raw))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename in edits:
                data = edits[item.filename](data.decode("utf-8")).encode("utf-8")
            z.writestr(item, data)
    return out.getvalue()

def send(data, label):
    h.drive.files().update(fileId=doc_id, media_body=MediaIoBaseUpload(io.BytesIO(data), mimetype=DOCX),
                           fields="version", supportsAllDrives=True).execute()
    print(f"\n--- {label}")
    print("\n".join(l for l in h.export_md(doc_id).splitlines() if "tick" in l))
    doc = h.get(doc_id)
    for lid, lst in doc.get("lists", {}).items():
        l0 = lst["listProperties"]["nestingLevels"][0]
        print("  list", lid[-6:], "glyphType", l0.get("glyphType"), "glyphSymbol", repr(l0.get("glyphSymbol")))

numbering = zipfile.ZipFile(io.BytesIO(raw)).read("word/numbering.xml").decode()
print("first abstractNum level 0 as exported:")
print(re.search(r"<w:lvl w:ilvl=\"0\".*?</w:lvl>", numbering, re.S).group(0)[:600])

# variant 1: level text U+2610 (ballot box), numFmt bullet
def glyph(ch, font=None):
    def fn(xml):
        def lvl(m):
            s = m.group(0)
            s = re.sub(r'<w:lvlText w:val="[^"]*"/>', f'<w:lvlText w:val="{ch}"/>', s)
            if font:
                s = re.sub(r"<w:rPr>.*?</w:rPr>", f'<w:rPr><w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:eastAsia="{font}" w:hint="eastAsia"/></w:rPr>', s, flags=re.S)
                if "<w:rPr>" not in s:
                    s = s.replace("</w:lvl>", f'<w:rPr><w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:eastAsia="{font}" w:hint="eastAsia"/></w:rPr></w:lvl>')
            return s
        return re.sub(r'<w:lvl w:ilvl="0".*?</w:lvl>', lvl, xml, flags=re.S)
    return fn

send(rewrite(raw, {"word/numbering.xml": glyph("☐")}), "level text U+2610 ballot box")
send(rewrite(raw, {"word/numbering.xml": glyph("☑", "MS Gothic")}), "level text U+2611 ballot box with check, MS Gothic")
send(rewrite(raw, {"word/numbering.xml": glyph("", "Wingdings")}), "level text Wingdings F0A8 (Word's checkbox bullet)")

# variant 4: a w14:checkbox content control before the text of 'tick me via docx', numbering removed from that paragraph
def control(xml):
    sdt = ('<w:sdt><w:sdtPr><w14:checkbox><w14:checked w14:val="1"/><w14:checkedState w14:val="2612" w14:font="MS Gothic"/>'
           '<w14:uncheckedState w14:val="2610" w14:font="MS Gothic"/></w14:checkbox></w:sdtPr><w:sdtContent>'
           '<w:r><w:rPr><w:rFonts w:ascii="MS Gothic" w:hAnsi="MS Gothic" w:eastAsia="MS Gothic"/></w:rPr><w:t>☒</w:t></w:r>'
           '</w:sdtContent></w:sdt>')
    def para(m):
        s = m.group(0)
        s = re.sub(r"<w:numPr>.*?</w:numPr>", "", s, flags=re.S)
        return s.replace("<w:r ", sdt + "<w:r ", 1)
    return re.sub(r"<w:p\b(?:(?!<w:p\b).)*?tick me via docx.*?</w:p>", para, xml, flags=re.S)

send(rewrite(raw, {"word/document.xml": control}), "w14:checkbox content control, checked, on the third item")
