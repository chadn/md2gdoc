"""Shared helpers for the PT-009 probes: one connection, a Docs client, paragraph lookup by text."""
import copy
import io
import json
import re
import sys
import zipfile

sys.path.insert(0, "/Users/chad/src/md2gdoc")
import md2gdoc  # noqa: E402
from googleapiclient.discovery import build  # noqa: E402
from googleapiclient.http import MediaIoBaseUpload  # noqa: E402

d = md2gdoc.connect(None)
drive = d.api
docs = build("docs", "v1", credentials=drive._http.credentials, cache_discovery=False)


def get(doc_id):
    return docs.documents().get(documentId=doc_id).execute()


def text_of(p):
    return "".join(r.get("textRun", {}).get("content", "") for r in p["elements"])


def paragraphs(doc):
    """(start, end, text, paragraph) for every body paragraph, in order; table cells are skipped."""
    out = []
    for el in doc["body"]["content"]:
        p = el.get("paragraph")
        if p:
            out.append((el["startIndex"], el["endIndex"], text_of(p), p))
    return out


def find(doc, needle):
    """The paragraph whose text contains needle: (start, end, text, paragraph); the end includes the newline."""
    hits = [x for x in paragraphs(doc) if needle in x[2]]
    assert len(hits) == 1, (needle, [x[2] for x in hits])
    return hits[0]


def batch(doc_id, requests, **write_control):
    body = {"requests": requests}
    if write_control:
        body["writeControl"] = write_control
    return docs.documents().batchUpdate(documentId=doc_id, body=body).execute()


def export_md(doc_id):
    return d.export(doc_id)


def export_docx(doc_id):
    raw = drive.files().export(fileId=doc_id, mimeType="application/vnd.openxmlformats-officedocument."
                               "wordprocessingml.document").execute()
    z = zipfile.ZipFile(io.BytesIO(raw))
    names = z.namelist()
    document = z.read("word/document.xml").decode("utf-8")
    comments = z.read("word/comments.xml").decode("utf-8") if "word/comments.xml" in names else ""
    return document, comments


def comment_anchors(document_xml):
    """For each commentRangeStart id in the docx body, the plain text between its start and end marks."""
    out = {}
    for m in re.finditer(r'<w:commentRangeStart w:id="(\d+)"/>(.*?)<w:commentRangeEnd w:id="\1"/>', document_xml, re.S):
        out[m.group(1)] = re.sub(r"<[^>]+>", "", m.group(2))
    return out


def comment_texts(comments_xml):
    out = {}
    for m in re.finditer(r'<w:comment [^>]*w:id="(\d+)"[^>]*>(.*?)</w:comment>', comments_xml, re.S):
        out[m.group(1)] = re.sub(r"<[^>]+>", "", m.group(2))
    return out


def drive_comments(doc_id):
    r = drive.comments().list(fileId=doc_id, fields="comments(id,content,anchor,quotedFileContent,resolved,deleted)",
                              includeDeleted=True).execute()
    return r.get("comments", [])


def create_from(media_bytes, mimetype, name):
    f = drive.files().create(body={"name": name, "mimeType": "application/vnd.google-apps.document"},
                             media_body=MediaIoBaseUpload(io.BytesIO(media_bytes), mimetype=mimetype),
                             fields="id,webViewLink,version").execute()
    return f


def trash(doc_id):
    return drive.files().update(fileId=doc_id, body={"trashed": True}, fields="id,trashed").execute()


def show(doc, label=""):
    print(f"--- paragraphs {label}")
    for s, e, t, p in paragraphs(doc):
        style = p["paragraphStyle"].get("namedStyleType", "")
        bullet = p.get("bullet", {})
        extra = []
        if bullet:
            extra.append(f"bullet list={bullet['listId'][-6:]} lvl={bullet.get('nestingLevel', 0)}")
        if p["paragraphStyle"].get("indentStart"):
            extra.append(f"indentStart={p['paragraphStyle']['indentStart']}")
        print(f"{s:4}-{e:4} {style:12} {t!r} {' '.join(extra)}")
    others = [k for el in doc["body"]["content"] for k in el if k not in ("startIndex", "endIndex", "paragraph")]
    print("non-paragraph elements:", others)


def dumps(o):
    return json.dumps(o, indent=1, ensure_ascii=False)
