# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""PT-003 probe: does client_secret.json work with drive.file on both the Drive API and the Docs API?

Runs the browser consent once, saves token.json next to the client file, then on one scratch Doc:
Drive files.create (markdown -> Doc), Docs documents.get, Docs batchUpdate, Drive files.export, Drive
files.update in place, then trashes the Doc. Prints one line per step.
"""
import io, json, sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

ROOT = Path(sys.argv[1])
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
MD1 = "# PT-003 probe\n\n- [ ] T-001 first line\n- [x] T-002 second line\n"
MD2 = "# PT-003 probe, replaced\n\n- [x] T-001 first line\n- [x] T-002 second line\n- [ ] T-003 added by push\n"

token = ROOT / "token.json"
creds = Credentials.from_authorized_user_file(token, SCOPES) if token.exists() else None
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        creds = InstalledAppFlow.from_client_secrets_file(ROOT / "client_secret.json", SCOPES).run_local_server(port=0)
    token.write_text(creds.to_json())
print(f"auth ok: token.json written, refresh_token present: {bool(creds.refresh_token)}, scopes: {creds.scopes}")

drive = build("drive", "v3", credentials=creds)
docs = build("docs", "v1", credentials=creds)

f = drive.files().create(
    body={"name": "md2gdoc PT-003 probe", "mimeType": "application/vnd.google-apps.document"},
    media_body=MediaIoBaseUpload(io.BytesIO(MD1.encode()), mimetype="text/markdown"),
    fields="id,webViewLink,version",
).execute()
doc_id = f["id"]
print(f"drive files.create ok: id {doc_id} version {f['version']} link {f['webViewLink']}")

d = docs.documents().get(documentId=doc_id).execute()
print(f"docs documents.get ok: title {d['title']!r}, {len(d['body']['content'])} structural elements")

r = docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
    {"insertText": {"location": {"index": 1}, "text": "Inserted by batchUpdate under drive.file\n"}}]}).execute()
print(f"docs batchUpdate ok: {len(r.get('replies', []))} reply")

exp = drive.files().export(fileId=doc_id, mimeType="text/markdown").execute().decode()
print("drive files.export ok, first lines:", json.dumps(exp.split("\n")[:3]))

u = drive.files().update(
    fileId=doc_id,
    media_body=MediaIoBaseUpload(io.BytesIO(MD2.encode()), mimetype="text/markdown"),
    fields="id,version",
).execute()
exp2 = drive.files().export(fileId=doc_id, mimeType="text/markdown").execute().decode()
print(f"drive files.update ok: same id {u['id'] == doc_id}, version {f['version']} -> {u['version']}, "
      f"export now starts {exp2.split(chr(10))[0]!r}, T-003 present: {'T-003' in exp2}")

drive.files().update(fileId=doc_id, body={"trashed": True}).execute()
print("trashed the probe Doc")
