# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""PT-023 probe: one fixture through Google's converter, the script's own way.

`probe.py <repo-root> <fixture-stem>...`: for each stem, creates a Doc from tests/fixtures/<stem>.in.md (for
`<stem>=round2`, from <stem>.out.md, the export fed back in, written to <stem>.round2.out.md) with the
script's `Drive.create` (the same files.create with text/markdown that `init` makes), exports it with
`Drive.export` (the same text/markdown export `pull` makes) into <stem>.out.md, byte for byte, and trashes the Doc.
Uses the `default` profile's cached token (MD2GDOC_ACCOUNT and MD2GDOC_CONFIG_DIR apply); never opens a browser.
"""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT))
import md2gdoc  # noqa: E402

d = md2gdoc.connect(None)
for stem in sys.argv[2:]:
    stem, _, again = stem.partition("=")
    fixture = ROOT / "tests" / "fixtures" / stem
    source, target = (".out.md", ".round2.out.md") if again else (".in.md", ".out.md")
    text = fixture.with_suffix(source).read_text(encoding="utf-8")
    made = d.create(f"md2gdoc PT-023 {stem}", text, None)
    out = d.export(made["doc_id"])
    fixture.with_suffix(target).write_text(out, encoding="utf-8", newline="\n")
    d.api.files().update(fileId=made["doc_id"], body={"trashed": True}).execute()
    print(f"{stem}: {len(text)} chars in, {len(out)} chars out, version {made['version']}, Doc trashed")
