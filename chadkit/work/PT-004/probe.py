# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""PT-004 probe: the two items left under docs/design.md "What is not proven".

`probe.py <root> push`: creates one scratch Doc from tests/fixtures/08-nested-checkboxes.in.md, exports it to
the fixture's .out.md, then records what moves the Drive `version`: two exports, a style-only batchUpdate, an
insertText, and a files.update with the same content, read back at once. `probe.py <root> steps <docId>` repeats
the edits on an existing Doc with a pause after each, since `version` lags the edit. The Doc is kept, so a person
can make a cosmetic edit in the Docs UI and run `probe.py <root> version <docId>` to read the version after it;
`probe.py <root> inspect <docId> [text]` also prints the export's state, the revision list, and the exported
line holding `text`. Prints one line per step. Reuses <root>/token.json; never opens a browser (run PT-003's probe for that).
"""
import datetime, io, sys, time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

ROOT, MODE = Path(sys.argv[1]), sys.argv[2]
FIXTURE = ROOT / "tests" / "fixtures" / "08-nested-checkboxes"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
FIELDS = "id,version,headRevisionId,modifiedTime"

creds = Credentials.from_authorized_user_file(ROOT / "token.json", SCOPES)
if not creds.valid:
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        sys.exit("token.json is not usable without a browser login; run PT-003's probe first")
drive = build("drive", "v3", credentials=creds)
docs = build("docs", "v1", credentials=creds)


def state(doc_id, label):
    f = drive.files().get(fileId=doc_id, fields=FIELDS).execute()
    print(f"{label}: version {f['version']} headRevisionId {f.get('headRevisionId', 'absent')} modifiedTime {f['modifiedTime']}")
    return f


def export(doc_id):
    return drive.files().export(fileId=doc_id, mimeType="text/markdown").execute().decode()


if MODE in ("version", "inspect"):
    doc_id = sys.argv[3]
    if MODE == "version":
        state(doc_id, "re-read")
        sys.exit()
    f = drive.files().get(fileId=doc_id, fields="version,modifiedTime").execute()
    now = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    print(f"re-read at {now}: version {f['version']} modifiedTime {f['modifiedTime']}")
    exp = export(doc_id)
    print("export holds the steps probe's inserted line:", "steps probe" in exp,
          "| italic/bold heading:", repr(exp.split(chr(10))[0]))
    revs = drive.revisions().list(fileId=doc_id, fields="revisions(id,modifiedTime)").execute()
    for r in revs.get("revisions", []):
        print("revision", r["id"], r["modifiedTime"])
    if len(sys.argv) > 4:
        line = next((l for l in exp.split("\n") if sys.argv[4] in l), "(line not found)")
        print(f"the line holding {sys.argv[4]!r} exports as {line!r}")
    sys.exit()

md = FIXTURE.with_suffix(".in.md").read_text()


def paused(doc_id, label, seconds=15):
    time.sleep(seconds)
    state(doc_id, f"{label}, {seconds}s later")


if MODE == "steps":
    doc_id = sys.argv[3]
    state(doc_id, "before")
    paused(doc_id, "nothing done")
    export(doc_id)
    paused(doc_id, "after an export")
    docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
        {"updateTextStyle": {"range": {"startIndex": 1, "endIndex": 7}, "textStyle": {"italic": True},
                             "fields": "italic"}}]}).execute()
    paused(doc_id, "after a style-only batchUpdate (italic)")
    docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
        {"insertText": {"endOfSegmentLocation": {}, "text": "Inserted by the steps probe\n"}}]}).execute()
    paused(doc_id, "after an insertText batchUpdate")
    drive.files().update(fileId=doc_id, media_body=MediaIoBaseUpload(io.BytesIO(md.encode()),
                         mimetype="text/markdown"), fields=FIELDS).execute()
    paused(doc_id, "after files.update with the original content")
    paused(doc_id, "nothing done", 30)
    sys.exit()
f = drive.files().create(
    body={"name": "md2gdoc PT-004 probe", "mimeType": "application/vnd.google-apps.document"},
    media_body=MediaIoBaseUpload(io.BytesIO(md.encode()), mimetype="text/markdown"),
    fields=FIELDS + ",webViewLink",
).execute()
doc_id = f["id"]
print(f"created {doc_id} link {f['webViewLink']}")
state(doc_id, "after create")

out = export(doc_id)
FIXTURE.with_suffix(".out.md").write_text(out)
print(f"exported {len(out)} bytes to the fixture's .out.md")
state(doc_id, "after one export")
export(doc_id)
state(doc_id, "after a second export")

docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
    {"updateTextStyle": {"range": {"startIndex": 1, "endIndex": 7}, "textStyle": {"bold": True}, "fields": "bold"}}
]}).execute()
state(doc_id, "after a style-only batchUpdate (bold)")

docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
    {"insertText": {"endOfSegmentLocation": {}, "text": "Inserted by batchUpdate\n"}}]}).execute()
state(doc_id, "after an insertText batchUpdate")

drive.files().update(fileId=doc_id, media_body=MediaIoBaseUpload(io.BytesIO(md.encode()), mimetype="text/markdown"),
                     fields=FIELDS).execute()
state(doc_id, "after files.update with the original content")
same = export(doc_id) == out
print(f"export after the update equals the first export: {same}")
print("kept the Doc for a UI edit; trash it when done")
