# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""An edit made outside the script, standing in for the Docs UI: `edit DOC_ID OLD NEW` replaces text in the Doc
through files.update; `trash DOC_ID` trashes it. Argument 1 is the repository, for md2gdoc's connect()."""
import sys
sys.path.insert(0, sys.argv[1])
import md2gdoc
d = md2gdoc.connect(None)
cmd, doc_id = sys.argv[2], sys.argv[3]
if cmd == "edit":
    text = md2gdoc.normalize(d.export(doc_id))  # the Doc's text as the script reads it, edited, sent as a push
    assert sys.argv[4] in text, f"{sys.argv[4]!r} not in the Doc"
    v = d.update(doc_id, md2gdoc.push_form(text.replace(sys.argv[4], sys.argv[5])))
    print(f"outside edit: {sys.argv[4]!r} -> {sys.argv[5]!r}, version {v}")
else:
    d.api.files().update(fileId=doc_id, body={"trashed": True}, supportsAllDrives=True).execute()
    print("trashed the scratch Doc")
