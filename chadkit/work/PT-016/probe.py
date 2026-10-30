# /// script
# requires-python = ">=3.11"
# dependencies = ["google-auth", "google-api-python-client", "google-auth-httplib2"]
# ///
"""PT-016 probe: does the default profile's refresh token, issued 2026-10-22, still refresh with no browser?

Loads the profile's token.json, prints what can be shown of it (never the tokens), forces one refresh through
Google's token endpoint, then reads the task list's Doc through the Drive API. No OAuth flow is imported, so a
browser cannot open; a dead refresh token would raise here.
"""
import datetime as dt, json, os, sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

profile = Path(sys.argv[1]).expanduser()
token = profile / "token.json"
st = token.stat()
print(f"token.json created {dt.datetime.fromtimestamp(st.st_birthtime):%Y-%m-%d %H:%M} local, "
      f"last written {dt.datetime.fromtimestamp(st.st_mtime):%Y-%m-%d %H:%M} local")
creds = Credentials.from_authorized_user_file(token)
before = creds.refresh_token
print(f"before: scopes {creds.scopes}, access token expiry {creds.expiry:%Y-%m-%dT%H:%M:%S}Z, "
      f"expired {creds.expired}, refresh token present {bool(before)}")
creds.refresh(Request())
token.write_text(creds.to_json())
print(f"after:  access token expiry {creds.expiry:%Y-%m-%dT%H:%M:%S}Z, valid {creds.valid}, "
      f"refresh token unchanged {creds.refresh_token == before}")
doc_id = json.loads(Path(sys.argv[2]).read_text())["doc_id"]
f = build("drive", "v3", credentials=creds).files().get(fileId=doc_id, fields="name,version").execute()
print(f"drive files.get ok on the task list's Doc: name {f['name']!r}, version {f['version']}")
