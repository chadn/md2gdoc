# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client", "google-auth-oauthlib", "google-auth-httplib2"]
# ///
"""The rest of the survey, on the Doc probe4 made."""
import json
import h
doc_id = open("survey-doc-id.txt").read().strip()
doc = h.get(doc_id)
print("--- every element kind in body, and paragraph elements that are not text runs")
for el in doc["body"]["content"]:
    kinds = [k for k in el if k not in ("startIndex", "endIndex")]
    if kinds != ["paragraph"]:
        print(el.get("startIndex"), el["endIndex"], kinds)
    p = el.get("paragraph")
    if p:
        for pe in p["elements"]:
            kinds = [k for k in pe if k not in ("startIndex", "endIndex")]
            if kinds != ["textRun"]:
                print("  paragraph element", pe["startIndex"], pe["endIndex"], kinds)
t = [el for el in doc["body"]["content"] if "table" in el][0]
print("--- table", t["startIndex"], t["endIndex"], "rows", t["table"]["rows"], "cols", t["table"]["columns"])
for row in t["table"]["tableRows"]:
    for cell in row["tableCells"]:
        print("  cell", cell["startIndex"], cell["endIndex"], repr("".join(h.text_of(c["paragraph"]) for c in cell["content"])))
print("--- export")
print(h.export_md(doc_id))
with open("survey-doc.json", "w") as fh:
    fh.write(h.dumps(doc))
