"""Trash one Doc by id; run with the three google libraries on the path (uv run --with ...)."""
import sys
sys.path.insert(0, "/Users/chad/src/md2gdoc")
import md2gdoc
d = md2gdoc.connect(None)
print(d.api.files().update(fileId=sys.argv[1], body={"trashed": True}, fields="id,trashed").execute())
