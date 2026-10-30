"""The commands against a fake Drive: the state file, the dry runs, the push guard, the exit codes."""

import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from md2gdoc import (  # noqa: E402
    EXIT_CONFLICT, EXIT_MOVED, EXIT_OK, FOOTER_MARK, SCOPE_URL, Fallback, anchored_comments, carry_comments,
    config_dir, doc_view, error_object, inline, main, merge3, normalize, pending_suggestions, plan_edits, profile_dir,
    push_form, replay, split_footer, state_path, token_scope, with_footer, write_doc,
)

FIXTURES = ROOT / "tests" / "fixtures"


_PREFIX = re.compile(r"^((?:    )*(?:[-*+]|\d+[.)]) (?:\[[ xX]\] )?|#{1,6} )?(.*)$")
_MARKUP = re.compile(r"\*\*|~~|`")
_PRESETS = {"BULLET_CHECKBOX": "- [ ] ", "BULLET_DISC_CIRCLE_SQUARE": "* ", "NUMBERED_DECIMAL_ALPHA_ROMAN": "1. "}


class FakeHttpError(Exception):
    """What googleapiclient raises: the status on `resp.status`, the reason in the text."""

    def __init__(self, status, text):
        super().__init__(f"<HttpError {status} {text}>")
        self.resp = type("Resp", (), {"status": status})()


class FakeDoc:
    """A Doc as paragraphs of (prefix, markdown text): the prefix is what the export writes before the text, `# `,
    `- [ ] `, `    - `, or nothing. Indexes count as the Docs API does: the body starts at 1, a paragraph is its
    plain text plus a newline. `updateTextStyle` is ignored, so a paragraph keeps the inline markup it had."""

    def __init__(self, markdown: str):
        lines = markdown.rstrip("\n").split("\n")
        self.paras = [list(_PREFIX.match(line).groups("")) for i, line in enumerate(lines) if line.strip() or not (
            (i and lines[i - 1].startswith("#")) or (i + 1 < len(lines) and lines[i + 1].startswith("#")))]

    @staticmethod
    def plain(md: str) -> str:
        return _MARKUP.sub("", md)

    @staticmethod
    def md_offset(md: str, plain_offset: int) -> int:
        """The index in the markdown text of the plain-text offset, past any markup before it."""
        i = seen = 0
        while seen < plain_offset or (i < len(md) and _MARKUP.match(md, i)):
            m = _MARKUP.match(md, i)
            if m:
                i = m.end()
            else:
                i, seen = i + 1, seen + 1
        return i

    def locate(self, index: int) -> tuple[int, int]:
        """(paragraph number, plain offset) of a Docs index; the offset equal to the text's length is its newline."""
        at = 1
        for n, (_, md) in enumerate(self.paras):
            size = len(self.plain(md)) + 1
            if index < at + size:
                return n, index - at
            at += size
        raise IndexError(index)

    def markdown(self) -> str:
        """The export's layout: a blank line on each side of a heading, else only an empty paragraph is one."""
        out: list[str] = []
        for prefix, md in self.paras:
            if out and (prefix.startswith("#") or out[-1].startswith("#")) and out[-1] != "":
                out.append("")
            out.append(prefix + md)
        return "\n".join(out) + "\n"

    def json(self) -> dict:
        content = [{"startIndex": 0, "endIndex": 1, "sectionBreak": {}}]
        at = 1
        for prefix, md in self.paras:
            plain = self.plain(md) + "\n"
            p: dict = {"elements": [{"startIndex": at, "endIndex": at + len(plain),
                                     "textRun": {"content": plain, "textStyle": {}}}],
                       "paragraphStyle": {"namedStyleType": f"HEADING_{len(prefix) - 1}" if prefix.startswith("#")
                                          else "NORMAL_TEXT"}}
            if prefix and not prefix.startswith("#"):
                kind = "box" if "[" in prefix else "ordered" if prefix.lstrip()[0].isdigit() else "bullet"
                p["bullet"] = {"listId": f"kix.{kind}", "nestingLevel": (len(prefix) - len(prefix.lstrip())) // 4}
                if not p["bullet"]["nestingLevel"]:
                    del p["bullet"]["nestingLevel"]
            content.append({"startIndex": at, "endIndex": at + len(plain), "paragraph": p})
            at += len(plain)
        levels = {"box": {"glyphType": "GLYPH_TYPE_UNSPECIFIED"}, "bullet": {"glyphSymbol": "-"},
                  "ordered": {"glyphType": "DECIMAL"}}
        return {"body": {"content": content},
                "lists": {f"kix.{k}": {"listProperties": {"nestingLevels": [v] * 9}} for k, v in levels.items()}}

    def apply(self, req: dict) -> None:
        kind, body = next(iter(req.items()))
        if kind == "insertText":
            n, o = self.locate(body["location"]["index"])
            prefix, md = self.paras[n]
            i = self.md_offset(md, o)
            parts = body["text"].split("\n")
            self.paras[n][1] = md[:i] + parts[0]
            tail = md[i:]
            for k, part in enumerate(parts[1:], 1):
                self.paras.insert(n + k, [prefix, part + (tail if k == len(parts) - 1 else "")])
            if len(parts) == 1:
                self.paras[n][1] += tail
        elif kind == "deleteContentRange":
            n1, o1 = self.locate(body["range"]["startIndex"])
            n2, o2 = self.locate(body["range"]["endIndex"])
            md1, md2 = self.paras[n1][1], self.paras[n2][1]
            self.paras[n1][1] = md1[:self.md_offset(md1, o1)] + md2[self.md_offset(md2, o2):]
            del self.paras[n1 + 1:n2 + 1]
        elif kind == "updateParagraphStyle":
            n, _ = self.locate(body["range"]["startIndex"])
            named = body["paragraphStyle"]["namedStyleType"]
            prefix = self.paras[n][0]
            self.paras[n][0] = "#" * int(named[-1]) + " " if named.startswith("HEADING_") else (
                "" if prefix.startswith("#") else prefix)
        elif kind == "deleteParagraphBullets":
            n, _ = self.locate(body["range"]["startIndex"])
            if not self.paras[n][0].startswith("#"):
                self.paras[n][0] = ""
        elif kind == "createParagraphBullets":
            n, _ = self.locate(body["range"]["startIndex"])
            self.paras[n][0] = _PRESETS[body["bulletPreset"]]
        elif kind != "updateTextStyle":
            raise ValueError(kind)


class FakeDrive:
    """Holds one Doc as the markdown last written; exports it through fixture 04's known noise. The Docs API side is
    `FakeDoc`; comments are anchored to a text, and a whole replace orphans them as Google does."""

    def __init__(self):
        self.docs: dict[str, str] = {}
        self.versions: dict[str, int] = {}
        self.revisions: dict[str, int] = {}
        self.comments: dict[str, list[dict]] = {}
        self.suggestions: dict[str, list[tuple[str, str]]] = {}  # per Doc: (suggestion id, its text)
        self.calls: list[str] = []
        self.docs_api_enabled = True
        self.viewer = False  # a profile that may only view the Doc: Google refuses the view that shows suggestions

    @staticmethod
    def imported(markdown):
        """What Google's import makes of the markdown (fixture 15): an HTML comment block is dropped, a resolved task
        line `- [-]` is an open box, and an empty paragraph goes between a paragraph and the list that follows it."""
        text = re.sub(r"^((?:    )*- )\[-\] ", r"\1[ ] ", doc_view(markdown), flags=re.M)
        out: list[str] = []
        for line in text.split("\n"):
            if line.startswith("- ") and out and out[-1] and not out[-1].startswith(("-", " ", "#")):
                out.append("")
            elif line and not line.startswith(("-", " ", "#", "`")) and out and out[-1].startswith(("- ", "  ")):
                line = "  " + line  # a lazy continuation line under an item comes back indented (fixture 15)
            out.append(line)
        return "\n".join(out)

    def create(self, name, markdown, folder):
        self.calls.append("create")
        doc_id = f"doc-{len(self.docs) + 1}"
        self.docs[doc_id], self.versions[doc_id] = self.imported(markdown), 5
        return {"doc_id": doc_id, "link": f"https://docs.google.com/document/d/{doc_id}/edit", "version": 5}

    def export(self, doc_id):
        """The converter's habit on the way out: a bold heading; the blank line before a list is put in on the way in
        (`imported`), where Google puts it (chadkit/work/PT-034/probe-paragraphs.out.txt)."""
        self.calls.append("export")
        return "\n".join(f"# **{line[2:]}**" if line.startswith("# ") else line
                          for line in self.docs[doc_id].split("\n"))

    def update(self, doc_id, markdown):
        self.calls.append("update")
        self.docs[doc_id] = self.imported(markdown)
        self.versions[doc_id] += 1
        self.revisions[doc_id] = self.revisions.get(doc_id, 0) + 1
        for c in self.comments.get(doc_id, []):
            c["anchored"] = None
        return self.versions[doc_id]

    def version(self, doc_id):
        return self.versions[doc_id]

    def lookup(self, doc_id):
        self.calls.append("lookup")
        if doc_id not in self.docs:
            raise KeyError(doc_id)  # Google answers 404; the fake has no HttpError
        return {"doc_id": doc_id, "link": f"https://docs.google.com/document/d/{doc_id}/edit",
                "version": self.versions[doc_id]}

    def get_doc(self, doc_id, comments=False):
        self.calls.append("get_doc")
        if not self.docs_api_enabled:
            raise FakeHttpError(403, "Google Docs API has not been used in project ... accessNotConfigured")
        if self.viewer:
            raise FakeHttpError(403, "The caller does not have permission")
        doc = FakeDoc(self.docs[doc_id]).json()
        doc["revisionId"] = f"rev-{self.revisions.get(doc_id, 0)}"
        for sid, text in self.suggestions.get(doc_id, []):  # on the run that holds the text, as Google marks it
            run = next(el["paragraph"]["elements"][0]["textRun"] for el in doc["body"]["content"]
                       if "paragraph" in el and text in el["paragraph"]["elements"][0]["textRun"]["content"])
            run.setdefault("suggestedInsertionIds", []).append(sid)
        if not comments:
            return doc
        body = "".join(el["paragraph"]["elements"][0]["textRun"]["content"] for el in doc["body"]["content"][1:])
        anchors, threads = {}, []
        for c in self.comments.get(doc_id, []):
            if c["anchored"] is not None and c["anchored"] in body:
                i = body.index(c["anchored"]) + 1
                anchors[f"anchor-{c['id']}"] = {"ranges": [{"startIndex": i, "endIndex": i + len(c["anchored"])}]}
            threads.append({"commentId": c["id"], "status": c.get("status", "OPEN"), "anchorId": f"anchor-{c['id']}",
                            "headPost": {"author": {"displayName": c["author"]}, "content": c["content"]},
                            "replies": [{"author": {"displayName": a}, "content": t} for a, t in c["replies"]]})
        return {"tabs": [{"documentTab": {"body": doc["body"], "commentAnchors": anchors}}], "comments": threads}

    def batch_update(self, doc_id, requests, revision_id=None):
        self.calls.append("batch_update")
        if revision_id and revision_id != f"rev-{self.revisions.get(doc_id, 0)}":
            raise FakeHttpError(400, "The provided revision ID does not match the latest revision")
        doc = FakeDoc(self.docs[doc_id])
        for req in requests:
            doc.apply(req)
        self.docs[doc_id] = doc.markdown()
        self.versions[doc_id] += 1
        self.revisions[doc_id] = self.revisions.get(doc_id, 0) + 1
        return {}

    def comment_in_ui(self, doc_id, anchored, content, author="A Reader", replies=()):
        cs = self.comments.setdefault(doc_id, [])
        cs.append({"id": f"c{len(cs) + 1}", "author": author, "content": content, "anchored": anchored,
                   "replies": list(replies)})

    def insert_comment(self, doc_id, start, end, content):
        self.calls.append("insert_comment")
        body = "".join(FakeDoc.plain(md) + "\n" for _, md in FakeDoc(self.docs[doc_id]).paras)
        self.comment_in_ui(doc_id, body[start - 1:end - 1], content, author="token user")
        return self.comments[doc_id][-1]["id"]

    def reply(self, doc_id, comment_id, content):
        self.calls.append("reply")
        next(c for c in self.comments[doc_id] if c["id"] == comment_id)["replies"].append(("token user", content))

    def delete_comment(self, doc_id, comment_id):
        self.calls.append("delete_comment")
        c = next(c for c in self.comments[doc_id] if c["id"] == comment_id)
        if c["author"] != "token user":
            raise FakeHttpError(403, "The caller does not have permission to delete this comment")
        self.comments[doc_id].remove(c)

    def make_by_hand(self, markdown):
        """A Doc the script did not create, as the Docs UI would leave it."""
        doc_id = f"hand-{len(self.docs) + 1}"
        self.docs[doc_id], self.versions[doc_id] = markdown, 2
        return doc_id

    def edit_in_ui(self, doc_id, old, new):
        self.docs[doc_id] = self.docs[doc_id].replace(old, new)
        self.versions[doc_id] += 1
        self.revisions[doc_id] = self.revisions.get(doc_id, 0) + 1

    def suggest_in_ui(self, doc_id, old, new):
        """A suggestion typed in the Doc's Suggesting mode: the export shows it as accepted, `documents.get` marks
        its run with the suggestion's id."""
        self.edit_in_ui(doc_id, old, new)
        ids = self.suggestions.setdefault(doc_id, [])
        ids.append((f"suggest.{len(ids) + 1}", new.replace(old, "").strip() or new))


class _WithDoc(unittest.TestCase):
    footer = False  # the footer is on by default; these tests pin the rest of the commands without it (Footer has it)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.md = Path(self.tmp.name) / "tasks.md"
        self.md.write_text((FIXTURES / "04-task-list.in.md").read_text(encoding="utf-8"), encoding="utf-8")
        self.drive = FakeDrive()

    def tearDown(self):
        self.tmp.cleanup()

    def run_cmd(self, *argv):
        if not self.footer and argv[0] in ("init", "pull", "push", "sync") and "--no-footer" not in argv:
            argv = (*argv, "--no-footer")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv), drive=lambda account, scope: self.drive)
        return code, out.getvalue(), err.getvalue()


class Commands(_WithDoc):
    def test_init_creates_the_doc_and_the_state_file(self):
        code, out, err = self.run_cmd("init", str(self.md))
        self.assertEqual(code, EXIT_OK)
        self.assertIn("created https://docs.google.com/document/d/doc-1/edit", out)
        self.assertEqual(err, "")
        state = json.loads(state_path(self.md).read_text(encoding="utf-8"))
        self.assertEqual(state["doc_id"], "doc-1")
        self.assertEqual(state["snapshot"], normalize(self.md.read_text(encoding="utf-8")))
        self.assertEqual(self.drive.docs["doc-1"], push_form(self.md.read_text(encoding="utf-8")))
        self.assertEqual(self.drive.calls, ["create", "export"])

    def test_init_dry_run_touches_nothing(self):
        code, out, _ = self.run_cmd("init", str(self.md), "--dry-run")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("would create Doc 'tasks'", out)
        self.assertFalse(state_path(self.md).exists())
        self.assertEqual(self.drive.calls, [])

    def test_init_refuses_a_second_time(self):
        self.run_cmd("init", str(self.md))
        with self.assertRaises(SystemExit) as e:
            self.run_cmd("init", str(self.md))
        self.assertIn("already has a Doc", str(e.exception))

    def test_init_doc_attaches_a_hand_made_doc_and_pulls_its_text(self):
        doc_id = self.drive.make_by_hand(self.md.read_text(encoding="utf-8"))
        new = Path(self.tmp.name) / "hand.md"
        code, out, err = self.run_cmd("init", str(new), "--doc", doc_id)
        self.assertEqual(code, EXIT_OK)
        self.assertIn(f"attached {new} to https://docs.google.com/document/d/{doc_id}/edit", out)
        self.assertEqual(err, "")
        self.assertEqual(self.drive.calls, ["export", "get_doc", "lookup"])
        state = json.loads(state_path(new).read_text(encoding="utf-8"))
        self.assertEqual((state["doc_id"], state["version"]), (doc_id, 2))
        self.assertEqual(new.read_text(encoding="utf-8"), state["snapshot"])
        self.assertEqual(state["local"], state["snapshot"])
        self.assertEqual(state["snapshot"], normalize(self.md.read_text(encoding="utf-8")))
        new.write_text(new.read_text(encoding="utf-8").replace("- [ ] T-001", "- [x] T-001"), encoding="utf-8")
        self.drive.edit_in_ui(doc_id, "- [ ] T-002", "- [x] T-002")
        code, out, _ = self.run_cmd("sync", str(new))
        self.assertEqual(code, EXIT_OK)
        self.assertIn("- [x] T-001", self.drive.docs[doc_id])
        self.assertIn("- [x] T-002", new.read_text(encoding="utf-8"))

    def test_init_doc_takes_an_empty_file_and_refuses_a_filled_one(self):
        doc_id = self.drive.make_by_hand("# hand\n")
        empty = Path(self.tmp.name) / "empty.md"
        empty.write_text("\n", encoding="utf-8")
        code, _, _ = self.run_cmd("init", str(empty), "--doc", doc_id)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(empty.read_text(encoding="utf-8"), "# hand\n")
        with self.assertRaises(SystemExit) as e:
            self.run_cmd("init", str(self.md), "--doc", doc_id)
        self.assertIn("exists and is not empty", str(e.exception))
        self.assertFalse(state_path(self.md).exists())

    def test_init_doc_refuses_the_create_options_and_dry_runs_offline(self):
        with self.assertRaises(SystemExit) as e:
            self.run_cmd("init", str(self.md), "--doc", "hand-9", "--name", "x")
        self.assertIn("--name and --folder are for creating one", str(e.exception))
        new = Path(self.tmp.name) / "hand.md"
        code, out, _ = self.run_cmd("init", str(new), "--doc", "hand-9", "--dry-run", "--json")
        self.assertEqual(code, EXIT_OK)
        obj = json.loads(out)
        self.assertEqual((obj["reason"], obj["doc_id"], obj["written"]), ("attached", "hand-9", False))
        self.assertFalse(new.exists())
        self.assertEqual(self.drive.calls, [])

    def test_status_names_the_side_that_changed(self):
        self.run_cmd("init", str(self.md))
        code, out, _ = self.run_cmd("status", str(self.md))
        self.assertIn("tasks.md: unchanged", out)
        self.assertIn("unchanged (version 5 -> 5)", out)
        self.md.write_text(self.md.read_text(encoding="utf-8").replace("- [ ] T-001", "- [x] T-001"), encoding="utf-8")
        self.drive.edit_in_ui("doc-1", "- [ ] T-002", "- [x] T-002")
        code, out, _ = self.run_cmd("status", str(self.md))
        self.assertEqual(code, EXIT_OK)
        self.assertIn("tasks.md: changed", out)
        self.assertIn("changed (version 5 -> 6)", out)
        code, out, _ = self.run_cmd("status", str(self.md), "--dry-run")
        self.assertNotIn("Doc ", out)

    def test_push_is_skipped_when_nothing_changed(self):
        self.run_cmd("init", str(self.md))
        code, out, _ = self.run_cmd("push", str(self.md))
        self.assertEqual((code, self.drive.calls[2:]), (EXIT_OK, []))
        self.assertIn("nothing to push", out)

    def test_push_is_skipped_again_after_the_converter_changed_the_text(self):
        self.run_cmd("init", str(self.md))
        self.md.write_text(self.md.read_text(encoding="utf-8").replace("- [ ] T-001", "- [x] T-001")
                           + "- [ ] T-004 right after the paragraph\n", encoding="utf-8")  # the tick: a whole replace
        code, _, err = self.run_cmd("push", str(self.md))
        self.assertEqual(code, EXIT_OK)
        self.assertIn("the Doc holds a different text", err)
        state = json.loads(state_path(self.md).read_text(encoding="utf-8"))
        self.assertNotEqual(state["snapshot"], state["local"])
        code, out, _ = self.run_cmd("push", str(self.md))
        self.assertIn("nothing to push", out)
        self.assertEqual(self.drive.versions["doc-1"], 6)
        code, out, _ = self.run_cmd("status", str(self.md))
        self.assertIn("tasks.md: unchanged", out)
        self.assertIn("Doc https://docs.google.com/document/d/doc-1/edit: unchanged", out)

    def test_push_replaces_the_doc_and_stores_the_new_snapshot(self):
        self.run_cmd("init", str(self.md))
        self.md.write_text(self.md.read_text(encoding="utf-8") + "\n- [ ] T-004 added locally\n", encoding="utf-8")
        code, out, _ = self.run_cmd("push", str(self.md), "--dry-run")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("+- [ ] T-004 added locally", out)
        self.assertNotIn("update", self.drive.calls)
        code, out, err = self.run_cmd("push", str(self.md))
        self.assertEqual((code, err), (EXIT_OK, ""))
        self.assertIn("T-004 added locally", self.drive.docs["doc-1"])
        state = json.loads(state_path(self.md).read_text(encoding="utf-8"))
        self.assertEqual((state["version"], state["snapshot"]), (6, normalize(self.md.read_text(encoding="utf-8"))))

    def test_push_is_refused_when_the_doc_moved(self):
        self.run_cmd("init", str(self.md))
        self.md.write_text(self.md.read_text(encoding="utf-8").replace("- [ ] T-001", "- [x] T-001"), encoding="utf-8")
        self.drive.edit_in_ui("doc-1", "- [ ] T-002", "- [x] T-002")
        code, _, err = self.run_cmd("push", str(self.md))
        self.assertEqual(code, EXIT_MOVED)
        self.assertIn("push refused", err)
        self.assertNotIn("update", self.drive.calls)

    def test_pull_is_refused_when_the_file_changed_unless_forced(self):
        self.run_cmd("init", str(self.md))
        self.md.write_text(self.md.read_text(encoding="utf-8") + "- [ ] T-006 added locally\n", encoding="utf-8")
        code, _, err = self.run_cmd("pull", str(self.md))
        self.assertEqual(code, EXIT_MOVED)
        self.assertIn("pull refused", err)
        self.assertIn("T-006", self.md.read_text(encoding="utf-8"))
        code, out, _ = self.run_cmd("pull", str(self.md), "--dry-run")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("-- [ ] T-006 added locally", out)
        code, _, _ = self.run_cmd("pull", str(self.md), "--force")
        self.assertEqual(code, EXIT_OK)
        self.assertNotIn("T-006", self.md.read_text(encoding="utf-8"))

    def test_init_doc_stops_while_the_doc_holds_a_pending_suggestion(self):
        doc_id = self.drive.make_by_hand(self.md.read_text(encoding="utf-8"))
        self.drive.suggest_in_ui(doc_id, "Call the vendor", "Call the vendor SUGGESTED")
        new = Path(self.tmp.name) / "hand.md"
        code, out, err = self.run_cmd("init", str(new), "--doc", doc_id)
        self.assertEqual((code, out, self.drive.calls), (EXIT_MOVED, "", ["export", "get_doc"]))
        self.assertIn("init refused: the Doc holds 1 pending suggestion", err)
        self.assertFalse(new.exists())
        self.assertFalse(state_path(new).exists())

    def test_pull_and_sync_stop_while_the_doc_holds_a_pending_suggestion(self):
        self.run_cmd("init", str(self.md))
        self.drive.suggest_in_ui("doc-1", "Call the vendor", "Call the vendor SUGGESTED")
        before = self.md.read_text(encoding="utf-8")
        for argv in (("pull",), ("pull", "--dry-run"), ("pull", "--force"), ("sync",), ("sync", "--dry-run")):
            self.drive.calls.clear()
            code, out, err = self.run_cmd(*argv, str(self.md))
            self.assertEqual((code, out, self.drive.calls), (EXIT_MOVED, "", ["get_doc"]), argv)
            self.assertEqual(err, f"{argv[0]} refused: the Doc holds 1 pending suggestion, which its export cannot "
                                  "tell from its text; accept or reject it in the Doc, then run again\n", argv)
        self.assertEqual(self.md.read_text(encoding="utf-8"), before)
        self.drive.suggest_in_ui("doc-1", "## Notes", "## Notes\n\nA second one.")
        code, _, err = self.run_cmd("sync", str(self.md))
        self.assertIn("holds 2 pending suggestions, which its export cannot tell from its text; accept or reject "
                      "them", err)
        self.drive.suggestions.clear()  # accepted in the Doc
        code, out, _ = self.run_cmd("pull", str(self.md))
        self.assertEqual(code, EXIT_OK)
        self.assertIn("Call the vendor SUGGESTED", self.md.read_text(encoding="utf-8"))

    def test_without_the_docs_api_a_pull_warns_that_suggestions_went_unchecked(self):
        self.run_cmd("init", str(self.md))
        self.drive.docs_api_enabled = False
        self.drive.suggest_in_ui("doc-1", "Call the vendor", "Call the vendor SUGGESTED")
        code, out, err = self.run_cmd("pull", str(self.md))
        self.assertEqual((code, out), (EXIT_OK, f"pulled {self.md}: changed\n"))
        self.assertEqual(err, "the Doc was not checked for pending suggestions, which its export cannot tell from "
                              "its text: the Docs API is not enabled in the Cloud project (docs/setup.md)\n")
        self.assertIn("SUGGESTED", self.md.read_text(encoding="utf-8"))
        code, out, err = self.run_cmd("sync", str(self.md), "--json")
        result = json.loads(out)
        self.assertEqual((code, err, result["reason"], result["suggestions"]), (EXIT_OK, "", "in_sync", None))
        self.assertEqual(result["warnings"], [result["message"].split("\n")[0]])
        self.assertIn("not checked", result["message"])
        self.drive.docs_api_enabled, self.drive.viewer = True, True
        code, out, err = self.run_cmd("sync", str(self.md))
        self.assertEqual((code, out),
                         (EXIT_OK, f"in sync: neither {self.md} nor the Doc changed since the last sync\n"))
        self.assertEqual(err, "the Doc was not checked for pending suggestions, which its export cannot tell from "
                              "its text: this profile's access to the Doc shows none (Google refused the view that "
                              "would, as for a viewer)\n")

    def test_pull_writes_the_normalized_export(self):
        self.run_cmd("init", str(self.md))
        self.drive.edit_in_ui("doc-1", "- [ ] T-002", "- [x] T-002")
        code, out, _ = self.run_cmd("pull", str(self.md), "--dry-run")
        self.assertIn("+- [x] T-002", out)
        self.assertNotIn("- [x] T-002", self.md.read_text(encoding="utf-8"))
        code, out, _ = self.run_cmd("pull", str(self.md))
        self.assertEqual(code, EXIT_OK)
        self.assertIn("pulled", out)
        self.assertIn("- [x] T-002", self.md.read_text(encoding="utf-8"))
        self.assertNotIn("**", self.md.read_text(encoding="utf-8").split("\n")[0])
        state = json.loads(state_path(self.md).read_text(encoding="utf-8"))
        text = self.md.read_text(encoding="utf-8")
        self.assertEqual((state["version"], state["snapshot"], state["local"]), (6, text, text))
        self.assertEqual(sorted(state), ["doc_id", "footer", "link", "local", "snapshot", "version"])

    def test_help_covers_setup_files_and_exit_codes(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as e:
            main(["--help"])
        self.assertEqual(e.exception.code, 0)
        for word in ("setup", "client_secret.json", "token.json", ".gdoc.json", "exit codes", "3  refused", "sync FILE",
                     "--json",
                     "--account", "--scope", "MD2GDOC_CONFIG_DIR", "MD2GDOC_ACCOUNT", "%APPDATA%", "pip install"):
            self.assertIn(word, out.getvalue())

    def test_a_usage_error_exits_1_not_2(self):
        for argv in (["bogus"], ["push"], []):
            err = io.StringIO()
            with redirect_stderr(err), self.assertRaises(SystemExit) as e:
                main(argv)
            self.assertEqual(e.exception.code, f"md2gdoc: {e.exception.code[9:]}", argv)
            self.assertIn("usage:", err.getvalue())

    def test_a_crlf_file_is_read_and_written_as_crlf_and_the_state_file_as_lf(self):
        self.md.write_bytes(self.md.read_text(encoding="utf-8").replace("\n", "\r\n").encode())
        self.run_cmd("init", str(self.md))
        state = json.loads(state_path(self.md).read_text(encoding="utf-8"))
        self.assertEqual(state["local"], normalize((FIXTURES / "04-task-list.in.md").read_text(encoding="utf-8")))
        self.assertNotIn("\r", self.drive.docs["doc-1"])
        self.assertNotIn(b"\r", state_path(self.md).read_bytes())
        self.drive.edit_in_ui("doc-1", "- [ ] T-002", "- [x] T-002")
        code, _, _ = self.run_cmd("pull", str(self.md))
        self.assertEqual(code, EXIT_OK)
        raw = self.md.read_bytes()
        self.assertIn(b"- [x] T-002", raw)
        self.assertEqual(raw.count(b"\r\n"), raw.count(b"\n"))
        code, out, _ = self.run_cmd("status", str(self.md))
        self.assertIn("tasks.md: unchanged", out)
        lf = Path(self.tmp.name) / "lf.md"
        lf.write_bytes(b"# T\n\n- [ ] a\n")
        self.run_cmd("init", str(lf))
        self.drive.edit_in_ui("doc-2", "- [ ] a", "- [x] a")
        self.run_cmd("pull", str(lf))
        self.assertNotIn(b"\r", lf.read_bytes())

    def test_a_missing_state_file_is_an_error(self):
        with self.assertRaises(SystemExit) as e:
            self.run_cmd("status", str(self.md))
        self.assertIn("no state file", str(e.exception))


class Sync(_WithDoc):
    """`sync` against the fake Drive: both sides merged, conflicts marked, the guard, the re-pull."""

    def setUp(self):
        super().setUp()
        self.run_cmd("init", str(self.md))
        self.drive.calls.clear()

    def edit_local(self, old, new):
        self.md.write_text(self.md.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")

    def test_in_sync_touches_nothing(self):
        code, out, _ = self.run_cmd("sync", str(self.md))
        self.assertEqual((code, self.drive.calls), (EXIT_OK, ["get_doc", "export"]))
        self.assertIn("in sync", out)

    def test_both_sides_edits_are_merged_written_and_pushed(self):
        self.edit_local("- [ ] T-001", "- [x] T-001")
        self.edit_local("- [x] T-003 Done item", "- [x] T-003 Reworded locally, done item")
        self.drive.edit_in_ui("doc-1", "- [ ] T-002", "- [x] T-002")
        self.drive.edit_in_ui("doc-1", "## Notes", "- [ ] T-004 typed in the Doc\n\n## Notes")
        code, out, err = self.run_cmd("sync", str(self.md), "--dry-run")
        self.assertEqual((code, self.drive.calls), (EXIT_OK, ["get_doc", "export"]))
        self.assertIn("+- [x] T-002", out)
        self.assertIn("+- [x] T-001", out)
        code, out, err = self.run_cmd("sync", str(self.md))
        self.assertEqual((code, err), (EXIT_OK, ""))
        text = self.md.read_text(encoding="utf-8")
        for line in ("- [x] T-001", "- [x] T-002", "- [x] T-003 Reworded locally", "- [ ] T-004 typed in the Doc"):
            self.assertIn(line, text)
        self.assertEqual(self.drive.docs["doc-1"], push_form(text))
        # each run reads the Doc for suggestions first; then the guard export, the edit path's read, the tick that
        # sends it to the whole replace, the comments read, the replace and the re-pull
        self.assertEqual(self.drive.calls, ["get_doc", "export", "get_doc", "export", "export", "get_doc", "get_doc",
                                            "update", "export"])
        state = json.loads(state_path(self.md).read_text(encoding="utf-8"))
        self.assertEqual((state["version"], state["local"], state["snapshot"]), (8, text, text))
        code, out, _ = self.run_cmd("sync", str(self.md))
        self.assertIn("in sync", out)

    def test_a_doc_only_change_is_pulled_and_nothing_pushed(self):
        self.drive.edit_in_ui("doc-1", "- [ ] T-002", "- [x] T-002")
        code, out, _ = self.run_cmd("sync", str(self.md))
        self.assertEqual((code, self.drive.calls), (EXIT_OK, ["get_doc", "export"]))
        self.assertIn("pulled, nothing to push", out)
        self.assertIn("- [x] T-002", self.md.read_text(encoding="utf-8"))
        self.assertEqual(json.loads(state_path(self.md).read_text(encoding="utf-8"))["version"], 6)

    def test_a_conflict_is_written_with_markers_exit_2_and_nothing_pushed(self):
        self.edit_local("Call the vendor", "Call the vendor, ours")
        self.drive.edit_in_ui("doc-1", "Call the vendor", "Call the vendor, theirs")
        code, out, err = self.run_cmd("sync", str(self.md), "--dry-run")
        self.assertEqual(code, EXIT_CONFLICT)
        self.assertIn("would write", err)
        self.assertIn("Call the vendor, ours", self.md.read_text(encoding="utf-8"))
        self.assertNotIn("<<<<<<<", self.md.read_text(encoding="utf-8"))
        code, out, err = self.run_cmd("sync", str(self.md))
        self.assertEqual(code, EXIT_CONFLICT)
        self.assertIn("conflict: 1 place", err)
        self.assertNotIn("update", self.drive.calls)
        self.assertIn("<<<<<<< api-edited\n- [ ] T-002 Call the vendor, ours (due 2026-10-24)\n=======\n"
                      "- [ ] T-002 Call the vendor, theirs (due 2026-10-24)\n>>>>>>> hand-edited\n",
                      self.md.read_text(encoding="utf-8"))
        code, _, err = self.run_cmd("sync", str(self.md))
        self.assertEqual(code, EXIT_CONFLICT)
        self.assertIn("holds conflict markers", err)
        self.assertEqual(self.drive.calls, ["get_doc", "export", "get_doc", "export"])

    def test_the_converters_own_blank_line_is_never_a_conflict(self):
        self.md.write_text(self.md.read_text(encoding="utf-8").replace("- [ ] T-001", "- [x] T-001")
                           + "- [ ] T-004 right after the paragraph\n", encoding="utf-8")  # the tick: a whole replace
        self.run_cmd("sync", str(self.md))
        state = json.loads(state_path(self.md).read_text(encoding="utf-8"))
        self.assertNotEqual(state["snapshot"], state["local"])  # the Doc gained a blank line before T-004
        self.drive.edit_in_ui("doc-1", "a_snake_case word.", "a_snake_case word, edited in the Doc.")
        code, out, err = self.run_cmd("sync", str(self.md))
        self.assertEqual((code, err), (EXIT_OK, ""))
        self.assertIn("pulled, nothing to push", out)
        self.assertIn("edited in the Doc.", self.md.read_text(encoding="utf-8"))
        self.edit_local("Last synced: 2026-10-21", "Last synced: 2026-10-22")
        code, out, err = self.run_cmd("sync", str(self.md))
        self.assertEqual((code, err), (EXIT_OK, ""))
        self.assertIn("Last synced: 2026-10-22", self.drive.docs["doc-1"])

    def test_push_refuses_a_file_with_markers(self):
        markers = "<<<<<<< api-edited\nx\n=======\ny\n>>>>>>> hand-edited\n"
        self.md.write_text(self.md.read_text(encoding="utf-8") + markers, encoding="utf-8")
        code, _, err = self.run_cmd("push", str(self.md))
        self.assertEqual((code, self.drive.calls), (EXIT_CONFLICT, []))
        self.assertIn("holds conflict markers", err)

    def test_the_push_is_refused_when_the_doc_moves_during_the_sync(self):
        self.edit_local("- [ ] T-001", "- [x] T-001")
        drive = self.drive

        def version(doc_id):  # a UI edit lands between the export and the push, once; the version lags
            if "- [ ] T-002" in drive.docs[doc_id]:
                drive.docs[doc_id] = drive.docs[doc_id].replace("- [ ] T-002", "- [x] T-002")
            return 5

        drive.version = version
        code, _, err = self.run_cmd("sync", str(self.md))
        self.assertEqual(code, EXIT_MOVED)
        self.assertIn("changed while syncing", err)
        self.assertNotIn("update", drive.calls)
        self.assertIn("- [x] T-001", self.md.read_text(encoding="utf-8"))  # written; the next sync pushes it


class FileSide(_WithDoc):
    """PT-034: a Doc-only change leaves the file's form and its HTML comment; a file-only change pushes its hunks
    alone; a resolved `[-]` line survives the Doc's `[ ]`."""

    text = ("# Plan\n\n<!-- Only people write this file.\n     Entries run to the next dated line. -->\n\n"
            "Also:\n- [ ] T-001 First\n- [-] T-002 Resolved, kept\n- [ ] T-003 Third\n\nNotes\n")

    def setUp(self):
        super().setUp()
        self.md.write_text(self.text, encoding="utf-8")
        self.run_cmd("init", str(self.md))
        self.drive.calls.clear()

    def test_the_doc_never_holds_the_comment_and_the_state_keeps_both_forms(self):
        self.assertNotIn("<!--", self.drive.docs["doc-1"])
        self.assertIn("- [ ] T-002", self.drive.docs["doc-1"])
        state = json.loads(state_path(self.md).read_text(encoding="utf-8"))
        self.assertEqual(state["local"], self.text)
        self.assertEqual(state["snapshot"], "# Plan\n\nAlso:\n\n- [ ] T-001 First\n- [ ] T-002 Resolved, kept\n"
                                            "- [ ] T-003 Third\n\nNotes\n")

    def test_a_doc_only_change_keeps_the_comment_the_shape_and_the_resolved_line(self):
        self.drive.edit_in_ui("doc-1", "- [ ] T-003 Third", "- [x] T-003 Third")
        code, out, err = self.run_cmd("sync", str(self.md))
        self.assertEqual((code, err), (EXIT_OK, ""))
        self.assertIn("pulled, nothing to push", out)
        self.assertEqual(self.md.read_text(encoding="utf-8"), self.text.replace("[ ] T-003", "[x] T-003"))
        self.assertEqual(self.drive.calls, ["get_doc", "export"])
        code, out, _ = self.run_cmd("sync", str(self.md))
        self.assertIn("in sync", out)

    def test_a_doc_only_change_keeps_a_lazy_continuation_line_as_written(self):
        text = self.text.replace("T-003 Third\n", "T-003 Third\nlazily continued\n")
        self.md.write_text(text, encoding="utf-8")
        self.run_cmd("sync", str(self.md))  # pushes the line; the fake, like Google, indents it in the Doc
        self.assertIn("\n  lazily continued\n", self.drive.docs["doc-1"])
        self.drive.edit_in_ui("doc-1", "Notes", "Notes, edited")
        code, out, err = self.run_cmd("sync", str(self.md))
        self.assertEqual((code, err), (EXIT_OK, ""))
        self.assertEqual(self.md.read_text(encoding="utf-8"), text.replace("Notes", "Notes, edited"))

    def test_a_pull_keeps_the_comment_and_the_shape_unless_forced(self):
        self.drive.edit_in_ui("doc-1", "Notes", "Notes, edited")
        code, out, _ = self.run_cmd("pull", str(self.md))
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(self.md.read_text(encoding="utf-8"), self.text.replace("Notes", "Notes, edited"))
        code, _, _ = self.run_cmd("pull", str(self.md), "--force")  # on an unchanged file too
        self.assertEqual(code, EXIT_OK)
        self.assertNotIn("<!--", self.md.read_text(encoding="utf-8"))  # the Doc's text as it is, as asked
        self.assertIn("Also:\n\n- [ ] T-001", self.md.read_text(encoding="utf-8"))

    def test_a_file_only_change_pushes_its_hunks_and_not_the_files_shape(self):
        self.md.write_text(self.text.replace("T-001 First", "T-001 First, reworded"), encoding="utf-8")
        code, out, err = self.run_cmd("sync", str(self.md))
        self.assertEqual((code, err), (EXIT_OK, ""))
        self.assertIn(" edits", out)  # the edit path, not the whole replace
        self.assertEqual(self.drive.docs["doc-1"], "# Plan\n\nAlso:\n\n- [ ] T-001 First, reworded\n"
                                                   "- [ ] T-002 Resolved, kept\n- [ ] T-003 Third\n\nNotes\n")
        self.assertIn("<!--", self.md.read_text(encoding="utf-8"))

    def test_both_sides_changed_merges_in_the_files_form(self):
        self.md.write_text(self.text.replace("T-001 First", "T-001 First, reworded"), encoding="utf-8")
        self.drive.edit_in_ui("doc-1", "- [ ] T-003 Third", "- [x] T-003 Third")
        code, out, err = self.run_cmd("sync", str(self.md))
        self.assertEqual((code, err), (EXIT_OK, ""))
        text = self.md.read_text(encoding="utf-8")
        self.assertEqual(text, self.text.replace("T-001 First", "T-001 First, reworded").replace("[ ] T-003",
                                                                                                "[x] T-003"))
        self.assertIn("- [ ] T-001 First, reworded\n- [ ] T-002 Resolved, kept\n- [x] T-003 Third",
                      self.drive.docs["doc-1"])
        state = json.loads(state_path(self.md).read_text(encoding="utf-8"))
        self.assertEqual(state["local"], text)

    def test_a_comment_only_edit_writes_nothing_to_the_doc(self):
        self.md.write_text(self.text.replace("Only people", "Only humans"), encoding="utf-8")
        code, out, err = self.run_cmd("sync", str(self.md))
        self.assertEqual((code, err), (EXIT_OK, ""))
        self.assertIn("pulled, nothing to push", out)
        self.assertNotIn("batch_update", self.drive.calls)
        self.assertNotIn("update", self.drive.calls)
        self.assertEqual(json.loads(state_path(self.md).read_text(encoding="utf-8"))["local"],
                         self.text.replace("Only people", "Only humans"))


class Footer(_WithDoc):
    """The footer (PT-031, PT-034): on by default at the end of both sides, never a change, off with --no-footer."""

    footer = True

    def lines(self, text):
        footer = split_footer(text)[1]
        return footer and [footer[0], footer[1].strip("`"), footer[2]]  # the fake keeps no markup on an inserted line

    def test_init_writes_the_footer_to_both_sides(self):
        code, out, err = self.run_cmd("init", str(self.md))
        self.assertEqual((code, err), (EXIT_OK, ""))
        text = self.md.read_text(encoding="utf-8")
        footer = self.lines(text)
        self.assertEqual(len(footer), 3)
        self.assertTrue(footer[0].startswith(FOOTER_MARK + "20"))
        self.assertEqual(footer[1], self.md.as_posix())  # no repository root above the temp folder
        self.assertEqual(footer[2], "https://docs.google.com/document/d/doc-1/edit")
        self.assertEqual(text, split_footer(text)[0] + "\n" + "\n\n".join(split_footer(text)[1]) + "\n")
        self.assertEqual(split_footer(text)[1][1], f"`{footer[1]}`")
        self.assertEqual(self.lines(self.drive.docs["doc-1"]), footer)
        state = json.loads(state_path(self.md).read_text(encoding="utf-8"))
        self.assertNotIn("footer", state)
        self.assertNotIn(FOOTER_MARK, state["local"] + state["snapshot"])
        code, out, _ = self.run_cmd("sync", str(self.md))
        self.assertIn("in sync", out)

    def test_a_sync_refreshes_the_written_sides_time_and_a_missing_footer_comes_back(self):
        self.run_cmd("init", str(self.md))
        before = self.lines(self.md.read_text(encoding="utf-8"))
        self.drive.edit_in_ui("doc-1", "- [ ] T-002", "- [x] T-002")
        self.drive.calls.clear()
        code, out, _ = self.run_cmd("sync", str(self.md))
        self.assertEqual((code, self.drive.calls), (EXIT_OK, ["get_doc", "export"]))  # the Doc is not written
        after = self.lines(self.md.read_text(encoding="utf-8"))
        self.assertEqual((after[1], after[2]), (before[1], before[2]))
        self.assertEqual(self.lines(self.drive.docs["doc-1"]), before)
        body, _ = split_footer(self.md.read_text(encoding="utf-8"))
        self.md.write_text(body, encoding="utf-8")  # someone deletes the file's footer
        code, out, _ = self.run_cmd("sync", str(self.md))
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(self.lines(self.md.read_text(encoding="utf-8")), before)  # the Doc's, no new time

    def test_push_and_pull_carry_the_footer_too(self):
        self.run_cmd("init", str(self.md))
        before = self.lines(self.md.read_text(encoding="utf-8"))
        self.md.write_text(self.md.read_text(encoding="utf-8").replace("- [ ] T-001", "- [x] T-001"), encoding="utf-8")
        code, out, _ = self.run_cmd("push", str(self.md))
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(self.lines(self.drive.docs["doc-1"])[1:], before[1:])
        self.assertIn("- [x] T-001", self.drive.docs["doc-1"])
        self.drive.edit_in_ui("doc-1", "- [ ] T-002", "- [x] T-002")
        code, out, _ = self.run_cmd("pull", str(self.md))
        self.assertEqual(code, EXIT_OK)
        text = self.md.read_text(encoding="utf-8")
        self.assertIn("- [x] T-002", text)
        self.assertEqual(self.lines(text)[1:], before[1:])
        self.assertEqual(split_footer(text)[0], split_footer(normalize(text))[0])
        code, out, _ = self.run_cmd("sync", str(self.md))
        self.assertIn("in sync", out)

    def test_the_files_time_moves_with_a_doc_only_change_and_the_docs_does_not(self):
        times = iter(["10:00am", "10:01am", "10:02am", "10:03am"])

        def stamp(md, link):
            return [FOOTER_MARK + "2026-10-30 " + next(times) + " UTC", f"`{md.as_posix()}`", link]

        with patch("md2gdoc.footer_now", stamp):
            self.run_cmd("init", str(self.md))
            self.assertEqual(self.lines(self.drive.docs["doc-1"])[0], FOOTER_MARK + "2026-10-30 10:00am UTC")
            self.drive.edit_in_ui("doc-1", "- [ ] T-002", "- [x] T-002")
            self.run_cmd("sync", str(self.md))
            self.assertEqual(self.lines(self.md.read_text(encoding="utf-8"))[0], FOOTER_MARK + "2026-10-30 10:01am UTC")
            self.assertEqual(self.lines(self.drive.docs["doc-1"])[0], FOOTER_MARK + "2026-10-30 10:00am UTC")
            self.md.write_text(self.md.read_text(encoding="utf-8").replace("- [ ] T-001", "- [x] T-001"),
                               encoding="utf-8")
            self.run_cmd("sync", str(self.md))
            self.assertEqual(self.lines(self.drive.docs["doc-1"])[0], FOOTER_MARK + "2026-10-30 10:02am UTC")
            self.assertEqual(self.lines(self.md.read_text(encoding="utf-8"))[0], FOOTER_MARK + "2026-10-30 10:02am UTC")

    def test_a_line_appended_after_the_footer_is_body_and_the_footer_moves_back_to_the_end(self):
        self.run_cmd("init", str(self.md))
        self.md.write_text(self.md.read_text(encoding="utf-8") + "- [ ] T-009 appended by a tool\n", encoding="utf-8")
        code, out, err = self.run_cmd("sync", str(self.md))
        self.assertEqual((code, err), (EXIT_OK, ""))
        text = self.md.read_text(encoding="utf-8")
        body, footer = split_footer(text)
        self.assertTrue(body.endswith("- [ ] T-009 appended by a tool\n"))
        self.assertEqual(text, with_footer(body, footer))
        self.assertEqual(text.count(FOOTER_MARK), 1)
        self.assertEqual(self.drive.docs["doc-1"].count(FOOTER_MARK), 1)
        self.assertIn("- [ ] T-009 appended by a tool", self.drive.docs["doc-1"])
        code, out, _ = self.run_cmd("sync", str(self.md))
        self.assertIn("in sync", out)

    def test_no_footer_is_remembered_even_when_nothing_else_is_written(self):
        self.run_cmd("init", str(self.md))
        code, out, _ = self.run_cmd("push", str(self.md), "--no-footer")
        self.assertIn("nothing to push", out)
        self.assertFalse(json.loads(state_path(self.md).read_text(encoding="utf-8"))["footer"])
        code, out, _ = self.run_cmd("sync", str(self.md))
        self.assertEqual(code, EXIT_OK)
        self.assertIsNone(self.lines(self.md.read_text(encoding="utf-8")))
        self.assertIsNotNone(self.lines(self.drive.docs["doc-1"]))  # the Doc loses it with its next write for a change
        self.md.write_text(self.md.read_text(encoding="utf-8").replace("- [ ] T-001", "- [x] T-001"), encoding="utf-8")
        self.run_cmd("sync", str(self.md))
        self.assertIsNone(self.lines(self.drive.docs["doc-1"]))

    def test_a_file_name_with_spaces_has_one_footer_on_each_side(self):
        md = Path(self.tmp.name) / "My Notes.md"
        md.write_text(self.md.read_text(encoding="utf-8"), encoding="utf-8")
        self.run_cmd("init", str(md))
        self.drive.edit_in_ui("doc-1", "- [ ] T-002", "- [x] T-002")
        code, out, err = self.run_cmd("sync", str(md))
        self.assertEqual((code, err), (EXIT_OK, ""))
        self.assertEqual(md.read_text(encoding="utf-8").count(FOOTER_MARK), 1)
        self.assertEqual(self.drive.docs["doc-1"].count(FOOTER_MARK), 1)
        self.assertEqual(self.lines(md.read_text(encoding="utf-8"))[1], md.as_posix())
        code, out, _ = self.run_cmd("sync", str(md))
        self.assertIn("in sync", out)

    def test_an_attached_doc_is_not_written_for_the_footer(self):
        doc_id = self.drive.make_by_hand(self.md.read_text(encoding="utf-8"))
        new = Path(self.tmp.name) / "hand.md"
        self.run_cmd("init", str(new), "--doc", doc_id)
        self.assertEqual(len(self.lines(new.read_text(encoding="utf-8"))), 3)
        self.assertIsNone(self.lines(self.drive.docs[doc_id]))
        self.drive.calls.clear()
        code, out, _ = self.run_cmd("sync", str(new))
        self.assertEqual((code, self.drive.calls), (EXIT_OK, ["get_doc", "export"]))
        self.assertIn("in sync", out)
        new.write_text(new.read_text(encoding="utf-8").replace("- [ ] T-001", "- [x] T-001"), encoding="utf-8")
        self.run_cmd("sync", str(new))
        self.assertEqual(len(self.lines(self.drive.docs[doc_id])), 3)  # the first push for a change brings it

    def test_no_footer_turns_it_off_and_the_state_remembers(self):
        self.run_cmd("init", str(self.md), "--no-footer")
        self.assertIsNone(self.lines(self.md.read_text(encoding="utf-8")))
        self.assertIsNone(self.lines(self.drive.docs["doc-1"]))
        self.assertFalse(json.loads(state_path(self.md).read_text(encoding="utf-8"))["footer"])
        self.drive.edit_in_ui("doc-1", "- [ ] T-002", "- [x] T-002")
        self.run_cmd("sync", str(self.md))
        self.assertIsNone(self.lines(self.md.read_text(encoding="utf-8")))

    def test_no_footer_later_removes_it_from_both_sides(self):
        self.run_cmd("init", str(self.md))
        self.md.write_text(self.md.read_text(encoding="utf-8").replace("- [ ] T-001", "- [x] T-001"), encoding="utf-8")
        code, out, _ = self.run_cmd("sync", str(self.md), "--no-footer")
        self.assertEqual(code, EXIT_OK)
        self.assertIsNone(self.lines(self.md.read_text(encoding="utf-8")))
        self.assertIsNone(self.lines(self.drive.docs["doc-1"]))
        self.assertIn("- [x] T-001", self.drive.docs["doc-1"])


class Json(_WithDoc):
    """`--json`: one object on stdout, nothing on stderr, the same exit codes."""

    def run_json(self, *argv):
        code, out, err = self.run_cmd(*argv, "--json")
        self.assertEqual(err, "", argv)
        self.assertEqual(out.count("\n"), 1, out)
        obj = json.loads(out)
        self.assertEqual(obj["exit"], code)
        return code, obj

    def test_every_command_prints_one_object(self):
        code, obj = self.run_json("init", str(self.md))
        self.assertEqual((code, obj["reason"], obj["pushed"]), (EXIT_OK, "created", True))
        self.assertEqual(obj["link"], "https://docs.google.com/document/d/doc-1/edit")
        code, obj = self.run_json("status", str(self.md), "--dry-run")
        self.assertEqual((code, obj["reason"], obj["local_changed"], obj["dry_run"]), (EXIT_OK, "status", False, True))
        self.assertNotIn("doc_changed", obj)
        code, obj = self.run_json("push", str(self.md))
        self.assertEqual((code, obj["reason"], obj["pushed"]), (EXIT_OK, "nothing_to_push", False))
        code, obj = self.run_json("sync", str(self.md))
        self.assertEqual((code, obj["reason"]), (EXIT_OK, "in_sync"))
        self.md.write_text(self.md.read_text(encoding="utf-8").replace("- [ ] T-001", "- [x] T-001")
                           + "- [ ] T-006 local\n", encoding="utf-8")  # the tick sends the push to the whole replace
        self.drive.edit_in_ui("doc-1", "- [ ] T-002", "- [x] T-002")
        code, obj = self.run_json("status", str(self.md))
        self.assertEqual((obj["local_changed"], obj["doc_changed"], obj["version"]), (True, True, 6))
        code, obj = self.run_json("pull", str(self.md))
        self.assertEqual((code, obj["reason"]), (EXIT_MOVED, "refused_file_changed"))
        self.assertIn("pull refused", obj["message"])
        self.drive.suggest_in_ui("doc-1", "## Notes", "## Notes\n\nSuggested paragraph.")
        code, obj = self.run_json("sync", str(self.md))
        self.assertEqual((code, obj["reason"], obj["suggestions"]), (EXIT_MOVED, "refused_suggestions", 1))
        self.assertNotIn("written", obj)
        self.drive.suggestions.clear()
        self.drive.edit_in_ui("doc-1", "\n\nSuggested paragraph.", "")
        code, obj = self.run_json("sync", str(self.md), "--dry-run")
        self.assertEqual((code, obj["reason"], obj["written"], obj["pushed"], obj["suggestions"]),
                         (EXIT_OK, "synced", False, False, 0))
        self.assertIn("+- [x] T-002", obj["diff_file"])
        self.assertIn("+- [ ] T-006 local", obj["diff_doc"])
        code, obj = self.run_json("sync", str(self.md))
        self.assertEqual((code, obj["reason"], obj["written"], obj["pushed"], obj["version"]),
                         (EXIT_OK, "synced", True, True, 9))  # the suggestion and its removal moved the version
        self.assertIn("+", obj["converter_diff"])  # the fake's blank line before T-006, reported, not an error

    def test_a_conflict_and_an_error_are_objects_too(self):
        self.run_json("init", str(self.md))
        self.md.write_text(self.md.read_text(encoding="utf-8").replace("vendor", "vendor, ours"), encoding="utf-8")
        self.drive.edit_in_ui("doc-1", "vendor", "vendor, theirs")
        code, obj = self.run_json("sync", str(self.md))
        self.assertEqual((code, obj["reason"], obj["conflicts"], obj["written"], obj["pushed"]),
                         (EXIT_CONFLICT, "conflict", 1, True, False))
        self.assertIn("<<<<<<< api-edited", self.md.read_text(encoding="utf-8"))
        code, obj = self.run_json("push", str(self.md))
        self.assertEqual((code, obj["reason"]), (EXIT_CONFLICT, "markers"))
        other = Path(self.tmp.name) / "other.md"
        other.write_text("# x\n", encoding="utf-8")
        code, obj = self.run_json("status", str(other))
        self.assertEqual((code, obj["reason"], obj["command"], obj["file"], obj["dry_run"]),
                         (1, "error", "status", str(other), False))
        self.assertIn("no state file", obj["message"])
        obj = error_object("md2gdoc: Google error: x", ["sync", "./a.md", "--json", "--dry-run"])
        self.assertEqual(obj, {"command": "sync", "file": "a.md", "dry_run": True, "exit": 1, "reason": "error",
                               "message": "md2gdoc: Google error: x"})


class Merge(unittest.TestCase):
    base = "# T\n\n- [ ] a\n- [ ] b\n- [ ] c\n"

    def test_one_sided_changes_and_ticks_are_taken(self):
        ours = self.base.replace("[ ] a", "[x] a")
        theirs = self.base.replace("[ ] c", "[x] c").replace("- [ ] b", "- [ ] b, edited")
        self.assertEqual(merge3(self.base, ours, theirs), ("# T\n\n- [x] a\n- [ ] b, edited\n- [x] c\n", 0))
        self.assertEqual(merge3(self.base, self.base, theirs), (theirs, 0))
        self.assertEqual(merge3(self.base, ours, ours), (ours, 0))

    def test_lines_added_at_the_same_place_on_both_sides_are_all_kept(self):
        self.assertEqual(merge3(self.base, self.base + "- [ ] d\n", self.base + "- [ ] e\n"),
                         (self.base + "- [ ] d\n- [ ] e\n", 0))
        self.assertEqual(merge3(self.base, self.base + "d\n", self.base + "d\ne\n"), (self.base + "d\ne\n", 0))
        self.assertEqual(merge3(self.base, self.base + "d\ne\n", self.base + "d\n"), (self.base + "d\ne\n", 0))
        self.assertEqual(merge3(self.base, self.base + "d\ne\n", self.base + "d\nf\n"),
                         (self.base + "d\ne\nf\n", 0))
        self.assertEqual(merge3(self.base, self.base + "d\ne\n", self.base + "f\ne\n"),
                         (self.base + "d\ne\nf\n", 0))
        self.assertEqual(merge3("", "Title\n=======\n", "Title\n=======\n"), ("Title\n=======\n", 0))

    def test_neighbouring_lines_changed_on_each_side_are_no_conflict(self):
        ours = self.base.replace("[ ] a", "[x] a").replace("[ ] c", "[x] c")
        theirs = self.base.replace("- [ ] b", "- [x] b").replace("[ ] c", "[x] c")
        self.assertEqual(merge3(self.base, ours, theirs), ("# T\n\n- [x] a\n- [x] b\n- [x] c\n", 0))
        merged, n = merge3(self.base, ours, self.base.replace("- [ ] a", "- [ ] a, theirs"))
        self.assertEqual(n, 1)
        self.assertIn("<<<<<<< api-edited\n- [x] a\n=======\n- [ ] a, theirs\n>>>>>>> hand-edited\n- [ ] b\n", merged)

    def test_lines_added_beside_a_changed_line_are_kept_around_it(self):
        ours = self.base.replace("- [ ] c", "- [x] c")
        self.assertEqual(merge3(self.base, ours, self.base + "- [ ] d\n"), (ours + "- [ ] d\n", 0))
        self.assertEqual(merge3(self.base, ours, self.base.replace("- [ ] c", "- [ ] b2\n- [ ] c")),
                         (ours.replace("- [x] c", "- [ ] b2\n- [x] c"), 0))
        gone = self.base.replace("- [ ] c\n", "")
        self.assertEqual(merge3(self.base, gone, self.base + "- [ ] d\n"), (gone + "- [ ] d\n", 0))

    def test_a_deletion_against_an_edit_is_a_conflict(self):
        merged, n = merge3(self.base, self.base.replace("- [ ] b\n", ""), self.base.replace("b", "b edited"))
        self.assertEqual(n, 1)
        self.assertIn("<<<<<<< api-edited\n=======\n- [ ] b edited\n>>>>>>> hand-edited\n", merged)

    def test_the_same_deletion_on_both_sides_is_not_a_conflict(self):
        gone = self.base.replace("- [ ] b\n", "")
        self.assertEqual(merge3(self.base, gone, gone), (gone, 0))


class Forms(unittest.TestCase):
    """The two forms (PT-034): `replay` carries one side's hunks onto the other side's form, `doc_view` is the file
    without what the Doc cannot hold, and the footer is split off before either is compared."""

    file = "# T\n\n<!-- a note\n     for people -->\n\nAlso:\n- a\n- b\n\nEnd\n"
    doc = "# T\n\nAlso:\n\n- a\n- b\n\nEnd\n"  # the export: the comment gone, a blank line before the list

    def test_doc_view_drops_comment_blocks_and_the_blank_they_leave(self):
        self.assertEqual(doc_view(self.file), "# T\n\nAlso:\n- a\n- b\n\nEnd\n")
        self.assertEqual(doc_view("x <!-- inline --> y\n"), "x <!-- inline --> y\n")
        self.assertEqual(doc_view("<!-- never closed\nline\n"), "<!-- never closed\nline\n")  # prose, not a comment
        self.assertEqual(doc_view("```\n<!-- c -->\ncode\n```\n"), "```\n<!-- c -->\ncode\n```\n")
        self.assertEqual(doc_view("<!-- c -->\n\n# T\n"), "# T\n")

    def test_replay_carries_a_doc_change_onto_the_file_form(self):
        edited = self.doc.replace("- b", "- b, edited").replace("End", "End\n\nMore")
        self.assertEqual(replay(self.doc, edited, self.file),
                         self.file.replace("- b", "- b, edited").replace("End", "End\n\nMore"))

    def test_replay_carries_a_file_change_onto_the_doc_form(self):
        edited = self.file.replace("- a", "- a, edited").replace("for people", "for everyone")
        self.assertEqual(replay(doc_view(self.file), doc_view(edited), self.doc),
                         self.doc.replace("- a", "- a, edited"))

    def test_replay_on_the_same_form_is_the_new_text(self):
        new = self.doc.replace("Also:", "Also, now:").replace("- b\n", "")
        self.assertEqual(replay(self.doc, new, self.doc), new)

    def test_replay_at_a_converter_only_run_carries_the_run_and_loses_nothing(self):
        edited = self.doc.replace("Also:\n\n- a", "Also:\n\n- a0\n- a")  # the Doc adds a line after its blank
        self.assertEqual(replay(self.doc, edited, self.file), self.file.replace("Also:\n- a", "Also:\n\n- a0\n- a"))
        edited = self.doc.replace("Also:\n\n- a", "Also, a list:\n\n- a")
        self.assertEqual(replay(self.doc, edited, self.file), self.file.replace("Also:", "Also, a list:"))
        # a Doc paragraph inserted between a paragraph and a list keeps its blank lines in the file
        self.assertEqual(replay("Intro\n\nPara\n\n- x\n- y\n", "Intro\n\nPara\n\nNew\n\n- x\n- y\n",
                                "Intro\n\nPara\n- x\n- y\n"), "Intro\n\nPara\n\nNew\n\n- x\n- y\n")

    def test_replay_keeps_a_comment_a_hunk_spans_and_the_lines_of_a_reshaped_run(self):
        # the Doc deletes the paragraph after the comment: the comment stays, between blank lines
        self.assertEqual(replay(self.doc, self.doc.replace("Also:\n\n", ""), self.file),
                         "# T\n\n<!-- a note\n     for people -->\n\n- a\n- b\n\nEnd\n")
        # the Doc ticks a box the file holds as [-]: the comment and the [-] line's neighbours stay
        self.assertEqual(replay("# T\n\n- [ ] x\n- [ ] y\n", "# T\n\n- [x] x\n- [ ] y\n",
                                "# T\n\n<!-- c -->\n\n- [-] x\n- [ ] y\n"), "# T\n\n<!-- c -->\n\n- [x] x\n- [ ] y\n")
        # the Doc edits one of two continuation lines it indented: the other stays, the edited one in the Doc's form
        file, doc = "- item\nlazy one\nlazy two\n\nP\n", "- item\n  lazy one\n  lazy two\n\nP\n"
        self.assertEqual(replay(doc, doc.replace("lazy one", "lazy one, edited"), file),
                         "- item\n  lazy one, edited\nlazy two\n\nP\n")

    def test_split_footer_takes_the_last_three_paragraphs_when_marked(self):
        footer = [FOOTER_MARK + "2026-10-30 09:00am PDT", "`notes/a.md`", "https://docs.google.com/document/d/x/edit"]
        text = "# T\n\nbody\n\n" + "\n\n".join(footer) + "\n"
        self.assertEqual(split_footer(text), ("# T\n\nbody\n", footer))
        self.assertEqual(split_footer("# T\n\nbody\n"), ("# T\n\nbody\n", None))
        self.assertEqual(split_footer(FOOTER_MARK + "x\n\na\n"), (FOOTER_MARK + "x\n\na\n", None))
        self.assertEqual(split_footer("a\nb\nc\n"), ("a\nb\nc\n", None))


class Profiles(unittest.TestCase):
    """The config directory and the profile folder (PD-002), and which scope a run uses."""

    def setUp(self):
        self.env = {k: os.environ.pop(k, None)
                    for k in ("MD2GDOC_CONFIG_DIR", "MD2GDOC_ACCOUNT", "XDG_CONFIG_HOME", "APPDATA")}

    def tearDown(self):
        for k, v in self.env.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v

    def test_config_dir_is_the_override_then_xdg_then_the_home_default(self):
        self.assertEqual(config_dir(), Path.home() / ".config" / "md2gdoc")
        os.environ["XDG_CONFIG_HOME"] = "/xdg"
        self.assertEqual(config_dir(), Path("/xdg/md2gdoc"))
        os.environ["MD2GDOC_CONFIG_DIR"] = "/elsewhere"
        self.assertEqual(config_dir(), Path("/elsewhere"))

    def test_config_dir_on_windows_is_appdata(self):
        os.environ["APPDATA"] = r"C:\Users\me\AppData\Roaming"
        with patch.object(sys, "platform", "win32"):
            self.assertEqual(config_dir(), Path(r"C:\Users\me\AppData\Roaming") / "md2gdoc")
            os.environ["MD2GDOC_CONFIG_DIR"] = "/elsewhere"
            self.assertEqual(config_dir(), Path("/elsewhere"))
            del os.environ["MD2GDOC_CONFIG_DIR"], os.environ["APPDATA"]
            self.assertEqual(config_dir(), Path.home() / ".config" / "md2gdoc")
        self.assertEqual(config_dir(), Path.home() / ".config" / "md2gdoc")

    def test_profile_dir_is_the_flag_then_the_variable_then_default(self):
        os.environ["MD2GDOC_CONFIG_DIR"] = "/cfg"
        self.assertEqual(profile_dir(None), Path("/cfg/default"))
        os.environ["MD2GDOC_ACCOUNT"] = "work"
        self.assertEqual(profile_dir(None), Path("/cfg/work"))
        self.assertEqual(profile_dir("other"), Path("/cfg/other"))

    def test_token_scope_is_the_tokens_else_the_request_else_drive_file(self):
        self.assertEqual(token_scope(None, None), "drive.file")
        self.assertEqual(token_scope(None, "drive"), "drive")
        self.assertEqual(token_scope([SCOPE_URL + "drive"], None), "drive")
        self.assertEqual(token_scope([SCOPE_URL + "drive"], "drive"), "drive")
        with self.assertRaises(SystemExit) as e:
            token_scope([SCOPE_URL + "drive.file"], "drive")
        self.assertIn("logged in with --scope drive.file", str(e.exception))


if __name__ == "__main__":
    unittest.main()


class Inline(unittest.TestCase):
    """`inline`: a line's plain text and spans from the syntax the edit path writes; anything else falls back."""

    def test_plain_and_escapes(self):
        self.assertEqual(inline(r"T-001 [PG-003] a \- dash, a_snake_case word"),
                         ("T-001 [PG-003] a - dash, a_snake_case word", []))

    def test_spans_in_characters(self):
        plain, spans = inline("Done with `inline code` and **bold**, *it* and ~~no~~ [vendor](https://e.com/v)")
        self.assertEqual(plain, "Done with inline code and bold, it and no vendor")
        self.assertEqual([(a, b, list(st)) for a, b, st in spans], [
            (10, 21, ["weightedFontFamily"]), (26, 30, ["bold"]), (32, 34, ["italic"]), (39, 41, ["strikethrough"]),
            (42, 48, ["link", "underline", "foregroundColor"])])
        self.assertEqual(spans[-1][2]["link"], {"url": "https://e.com/v"})

    def test_what_falls_back(self):
        for md in ("_italic_", "an <b>tag</b>", "![img](u)", "&amp;", "**open", "a `tick", '[t](u "title")',
                   "[`code`](u)"):
            with self.assertRaises(Fallback, msg=md):
                inline(md)


class Plan(unittest.TestCase):
    """`plan_edits` against the `documents.get` of fixture 04's Doc, kept in `04-task-list.doc.json`: the requests a
    diff becomes, and the diffs that must fall back to the whole replace."""

    def setUp(self):
        self.doc = json.loads((FIXTURES / "04-task-list.doc.json").read_text(encoding="utf-8"))
        self.old = normalize((FIXTURES / "04-task-list.out.md").read_text(encoding="utf-8"))

    def plan(self, old, new):
        return plan_edits(self.doc, self.old.replace(old, new) if old else self.old, self.old.replace(*new)
                          if isinstance(new, tuple) else new)

    def kinds(self, reqs):
        return [next(iter(r)) for r in reqs]

    def test_a_word_change_edits_the_middle_and_restyles_the_paragraph(self):
        reqs = self.plan(None, ("Call the vendor", "Phone the vendor"))
        # the T-002 paragraph starts at 140; "Call" is at offset 6
        self.assertEqual(reqs[:2], [{"deleteContentRange": {"range": {"startIndex": 146, "endIndex": 150}}},
                                    {"insertText": {"location": {"index": 146}, "text": "Phone"}}])
        self.assertEqual(reqs[2]["updateTextStyle"]["range"], {"startIndex": 140, "endIndex": 140 + 39})
        self.assertEqual(len(reqs), 3)

    def test_a_styled_line_edit_sets_every_span_again(self):
        reqs = self.plan(None, ("T-003 Done item", "T-003 Finished item"))
        self.assertEqual(self.kinds(reqs), ["deleteContentRange", "insertText", "updateTextStyle", "updateTextStyle",
                                            "updateTextStyle"])
        self.assertEqual(reqs[3]["updateTextStyle"]["textStyle"]["weightedFontFamily"]["fontFamily"], "Roboto Mono")
        self.assertEqual(reqs[4]["updateTextStyle"]["textStyle"], {"bold": True})

    def test_a_heading_edit_keeps_the_style_and_a_level_change_sets_it(self):
        reqs = self.plan(None, ("## Notes", "## Remarks"))
        self.assertEqual(self.kinds(reqs), ["deleteContentRange", "insertText", "updateTextStyle"])
        reqs = self.plan(None, ("## Notes", "### Notes"))
        self.assertEqual(reqs[-1]["updateParagraphStyle"]["paragraphStyle"], {"namedStyleType": "HEADING_3"})

    def test_new_lines_go_in_after_the_paragraph_before_them(self):
        reqs = self.plan(None, ("and **bold**\n", "and **bold**\n- [ ] T-004 new box\n"))
        self.assertEqual(reqs[0], {"insertText": {"location": {"index": 249}, "text": "\nT-004 new box"}})
        self.assertEqual(reqs[1]["updateTextStyle"]["range"], {"startIndex": 250, "endIndex": 263})
        self.assertEqual(self.kinds(reqs), ["insertText", "updateTextStyle"])  # the box is inherited

    def test_a_paragraph_after_a_list_drops_the_bullet_and_after_a_heading_the_style(self):
        reqs = self.plan(None, ("and **bold**\n", "and **bold**\n\nA closing line.\n"))
        self.assertEqual(self.kinds(reqs), ["insertText", "updateTextStyle", "deleteParagraphBullets", "insertText",
                                            "deleteParagraphBullets"])  # the line, then its blank, both inherit
        # the blank after a heading is no paragraph; the one before the list is, and both inherit the heading style
        reqs = self.plan(None, ("## Open\n", "## Open\n\nAn intro.\n"))
        self.assertEqual(self.kinds(reqs), ["insertText", "updateParagraphStyle", "insertText", "updateTextStyle",
                                            "updateParagraphStyle"])
        self.assertEqual(reqs[0], {"insertText": {"location": {"index": 42}, "text": "\n"}})
        self.assertEqual(reqs[-1]["updateParagraphStyle"]["paragraphStyle"], {"namedStyleType": "NORMAL_TEXT"})

    def test_lines_after_a_nested_item_drop_its_bullet_and_a_new_item_there_falls_back(self):
        reqs = self.plan(None, ("4-space indent\n", "4-space indent\n\nSome prose here.\n\n"))
        self.assertEqual(self.kinds(reqs), ["insertText", "deleteParagraphBullets", "insertText", "updateTextStyle",
                                            "deleteParagraphBullets", "insertText", "deleteParagraphBullets"])
        with self.assertRaises(Fallback) as e:
            self.plan(None, ("4-space indent\n", "4-space indent\n- [ ] a box after the child\n"))
        self.assertEqual(e.exception.args, ("nesting",))

    def test_the_cells_of_the_features_table_hold(self):
        """One case per cell of features.md "Which push writes what" that no other test pins."""
        in_place = (
            ("## Open\n\n", "## Open\n\n- [ ] a box after the heading\n"),
            ("## Notes\n", "## Notes\n\n### A new heading\n"),
            ("\n## Notes\n\n", "\n"),
            ("    - [ ] sub-task with 4-space indent\n", ""),
            ("- [ ] T-002 Call the vendor (due 2026-10-24)\n", ""),
        )
        for old, new in in_place:
            self.assertTrue(self.plan(None, (old, new)), (old, new))
        for why, old, new in (
            ("layout", "and **bold**\n", "and **bold**\n- a bullet after the checklist\n"),
            ("list", "    - [ ] sub-task", "- [ ] sub-task"),
            ("list", "Last synced: 2026-10-21", "- Last synced: 2026-10-21"),
        ):
            with self.assertRaises(Fallback, msg=(old, new)) as e:
                self.plan(None, (old, new))
            self.assertEqual(e.exception.args, (why,), (old, new))
        doc = json.loads((FIXTURES / "13-list-kinds.doc.json").read_text(encoding="utf-8"))
        old = normalize((FIXTURES / "13-list-kinds.out.md").read_text(encoding="utf-8"))
        self.assertTrue(plan_edits(doc, old, old.replace("- Dash two\n", "- Dash two\n- Dash three\n")))
        for why, a, b in (("list", "- Dash one\n", "- Dash zero\n- Dash one\n"),
                          ("layout", "- Dash two\n", "- Dash two\n- [ ] a box after the bullets\n"),
                          ("layout", "- Dash two", "1. Dash two"),
                          ("list", "+ Plus one\n+ Plus two", "1. Plus one\n2. Plus two")):
            with self.assertRaises(Fallback, msg=(a, b)) as e:
                plan_edits(doc, old, old.replace(a, b))
            self.assertEqual(e.exception.args, (why,), (a, b))

    def test_a_first_line_goes_in_before_the_first_paragraph(self):
        reqs = self.plan(None, "Top line\n\n" + self.old)
        self.assertEqual(reqs[0], {"insertText": {"location": {"index": 1}, "text": "Top line\n"}})
        self.assertEqual(reqs[-1]["updateParagraphStyle"]["range"], {"startIndex": 1, "endIndex": 10})

    def test_a_fresh_checkbox_is_created_and_a_fresh_bullet_falls_back(self):
        reqs = self.plan(None, ("word.\n", "word.\n\n- [ ] a box under the notes\n"))
        # the box goes in first, then the blank line before it, an empty paragraph
        self.assertEqual(self.kinds(reqs), ["insertText", "updateTextStyle", "createParagraphBullets", "insertText"])
        self.assertEqual(reqs[2]["createParagraphBullets"]["bulletPreset"], "BULLET_CHECKBOX")
        self.assertEqual(reqs[3], {"insertText": {"location": {"index": 329}, "text": "\n"}})
        with self.assertRaises(Fallback) as e:
            self.plan(None, ("word.\n", "word.\n\n- a bullet under the notes\n"))
        self.assertEqual(e.exception.args, ("list",))

    def test_deleted_paragraphs_go_in_one_range_and_the_last_through_the_newline_before_it(self):
        gone = "- [ ] T-002 Call the vendor (due 2026-10-24)\n    - [ ] sub-task with 4-space indent\n"
        reqs = self.plan(None, (gone, ""))
        self.assertEqual(reqs, [{"deleteContentRange": {"range": {"startIndex": 140, "endIndex": 208}}}])
        reqs = self.plan(None, ("\nPlain paragraph with a - dash, an & ampersand, 50% and a_snake_case word.\n", "\n"))
        self.assertEqual(reqs, [{"deleteContentRange": {"range": {"startIndex": 255, "endIndex": 329}}}])

    def test_what_falls_back_and_why(self):
        for why, old, new in (
            ("tick", "- [ ] T-002", "- [x] T-002"),
            ("tick", "and **bold**\n", "and **bold**\n- [x] T-004 born ticked\n"),
            ("nesting", "sub-task with", "subtask with"),
            ("nesting", "and **bold**\n", "and **bold**\n    - [ ] a new child\n"),
            ("list", "- [ ] T-002", "* [ ] T-002"),
            ("layout", "- [ ] T-002", "1. T-002"),
            ("list", "Plain paragraph", "- [ ] Plain paragraph"),
            ("blank", "## Notes", "- [ ] Notes"),
            ("structure", "## Notes\n", "## Notes\n\n| a | b |\n| --- | --- |\n"),
            ("structure", "## Notes\n", "## Notes\n\n```\ncode\n```\n"),
            ("structure", "## Notes\n", "## Notes\n\n---\n"),
            ("layout", "word.\n", "word.\nA second line of the same paragraph.\n"),
            ("blank", "T-002 Call the vendor (due 2026-10-24)\n", "T-002 Call the vendor (due 2026-10-24)\n\n"),
            ("inline", "Plain paragraph", "Plain _paragraph_"),
        ):
            with self.assertRaises(Fallback, msg=(old, new)) as e:
                self.plan(None, (old, new))
            self.assertEqual(e.exception.args, (why,), (old, new))

    def test_a_doc_that_does_not_match_its_export_falls_back(self):
        with self.assertRaises(Fallback) as e:
            plan_edits(self.doc, self.old.replace("Call the vendor", "Ring the vendor"), self.old)
        self.assertEqual(e.exception.args, ("mapping",))
        doc = json.loads((FIXTURES / "13-list-kinds.doc.json").read_text(encoding="utf-8"))
        with self.assertRaises(Fallback) as e:
            plan_edits(doc, self.old, self.old)
        self.assertEqual(e.exception.args, ("mapping",))

    def test_the_list_kinds_of_fixture_13_map_and_a_text_edit_in_each_is_planned(self):
        doc = json.loads((FIXTURES / "13-list-kinds.doc.json").read_text(encoding="utf-8"))
        old = normalize((FIXTURES / "13-list-kinds.out.md").read_text(encoding="utf-8"))
        for word in ("Star two", "Plus two", "Dash two", "Four", "Paren two", "open box", "struck"):
            reqs = plan_edits(doc, old, old.replace(word, word.upper()))
            self.assertEqual(self.kinds(reqs)[:2], ["deleteContentRange", "insertText"], word)
        reqs = plan_edits(doc, old, old.replace("- [ ] open box\n", "- [ ] open box\n- [ ] second box\n"))
        self.assertEqual(self.kinds(reqs), ["insertText", "updateTextStyle"])
        # an item put into a numbered list renumbers the rest in the file; the Doc numbers them itself
        reqs = plan_edits(doc, old, old.replace("3. Three\n4. Four\n", "3. Three\n4. Three and a half\n5. Four\n"))
        # the diff pairs "4. Four" with the new line and adds "5. Four" after it: the extra first, then the edit
        self.assertEqual(self.kinds(reqs), ["insertText", "updateTextStyle", "deleteContentRange", "insertText",
                                            "updateTextStyle"])
        with self.assertRaises(Fallback) as e:
            plan_edits(doc, old, old.replace("4. Four", "4) Four"))
        self.assertEqual(e.exception.args, ("list",))


class Suggestions(unittest.TestCase):
    """`pending_suggestions` over the shapes a `documents.get` uses for a suggestion."""

    def test_every_suggested_key_names_the_suggestion_wherever_it_sits(self):
        doc = {"suggestionsViewMode": "SUGGESTIONS_INLINE", "revisionId": "r", "documentStyle": {},
               "body": {"content": [
                   {"paragraph": {"elements": [{"textRun": {"content": "a\n", "textStyle": {},
                                                             "suggestedInsertionIds": ["s1"]}}]}},
                   {"paragraph": {"elements": [{"textRun": {"content": "b\n", "suggestedDeletionIds": ["s2"]}},
                                               {"textRun": {"content": "c\n", "suggestedTextStyleChanges": {
                                                   "s3": {"textStyle": {"bold": True}}}}}],
                                  "paragraphStyle": {"suggestedParagraphStyleChanges": {}},
                                  "suggestedBulletChanges": {"s1": {}}}},
                   {"table": {"tableRows": [{"tableCells": [{"content": [{"paragraph": {"elements": [
                       {"textRun": {"content": "d\n", "suggestedInsertionIds": ["s4"]}}]}}]}]}]}},
                   {"paragraph": {"elements": [{"inlineObjectElement": {"inlineObjectId": "kix.1",
                                                                         "suggestedInsertionIds": ["s5"]}}]}}]},
               "inlineObjects": {"kix.1": {"suggestedInsertionId": "s5"}},  # one id, not a list: never its letters
               "lists": {"kix.2": {"suggestedInsertionId": "s6", "suggestedDeletionIds": ["s7"]}}}
        self.assertEqual(pending_suggestions(doc), {"s1", "s2", "s3", "s4", "s5", "s6", "s7"})
        self.assertEqual(pending_suggestions(json.loads((FIXTURES / "04-task-list.doc.json").read_text("utf-8"))),
                         set())


class Carry(unittest.TestCase):
    """The comments read before a whole replace and written again after it."""

    RESP = {"tabs": [{"documentTab": {
        "body": {"content": [{"startIndex": 0, "endIndex": 1, "sectionBreak": {}},
                             {"startIndex": 1, "endIndex": 12, "paragraph": {"elements": [
                                 {"textRun": {"content": "First line\n"}}]}},
                             {"startIndex": 12, "endIndex": 29, "paragraph": {"elements": [
                                 {"textRun": {"content": "An ALPHA second\n"}}]}}]},
        "commentAnchors": {"a1": {"ranges": [{"startIndex": 15, "endIndex": 20}]}}}}],
        "comments": [
            {"commentId": "c1", "status": "OPEN", "anchorId": "a1", "headPost": {"author": {"displayName": "Ann"},
             "content": "why alpha?"}, "replies": [{"author": {"displayName": "Bob"}, "content": "because"}]},
            {"commentId": "c2", "status": "OPEN", "anchorId": "gone", "headPost": {"author": {}, "content": "orphan"}},
            {"commentId": "c3", "status": "RESOLVED", "anchorId": "a1", "headPost": {"author": {}, "content": "done"}}]}

    def test_anchored_comments_read_the_text_its_paragraph_and_the_replies(self):
        cs = anchored_comments(self.RESP)
        self.assertEqual([(c["id"], c["anchored"], c["para"], c["offset"]) for c in cs],
                         [("c1", "ALPHA", "An ALPHA second", 3), ("c2", None, None, None)])
        self.assertEqual((cs[0]["author"], cs[0]["replies"]), ("Ann", [("Bob", "because")]))

    def test_carry_over_writes_each_comment_again_and_deletes_the_orphan(self):
        drive = FakeDrive()
        drive.create("t", "First line\n\nAn ALPHA second\n", None)
        drive.comment_in_ui("doc-1", "ALPHA", "why alpha?", author="Ann", replies=[("Bob", "because")])
        drive.comment_in_ui("doc-1", "First", "a first comment", author="token user")
        before = anchored_comments(drive.get_doc("doc-1", comments=True))
        drive.update("doc-1", "First line\n\nAn ALPHA second, edited\n")
        self.assertEqual([c["anchored"] for c in drive.comments["doc-1"]], [None, None])
        result = carry_comments(drive, "doc-1", before)
        self.assertEqual(result, {"carried": 2, "unplaced": [], "undeleted": 1})
        kept = [(c["anchored"], c["content"], c["author"]) for c in drive.comments["doc-1"]]
        self.assertEqual(kept, [(None, "why alpha?", "Ann"),
                                ("ALPHA", "why alpha?\n\n(carried over a sync; by Ann)", "token user"),
                                ("First", "a first comment\n\n(carried over a sync; by token user)", "token user")])
        self.assertEqual(drive.comments["doc-1"][1]["replies"],
                         [("token user", "because\n\n(carried over a sync; by Bob)")])

    def test_a_repeated_word_goes_back_to_its_own_occurrence_and_an_image_keeps_the_count(self):
        drive = FakeDrive()
        drive.create("t", "echo echo\n\nAn echo here\n", None)
        drive.comment_in_ui("doc-1", "echo", "the third one")
        before = anchored_comments(drive.get_doc("doc-1", comments=True))
        before[0].update(para="An echo here", offset=3)  # the fake anchors the first echo; a reader chose the third
        drive.update("doc-1", "echo echo\n\nAn echo here\n")
        drive.insert_comment = lambda doc_id, s, e, content: drive.calls.append(f"insert {s}-{e}") or "c9"
        drive.delete_comment = lambda doc_id, cid: None
        carry_comments(drive, "doc-1", before)
        self.assertIn("insert 15-19", drive.calls)  # 1 + len("echo echo\n") + len("\n") + 3
        resp = {"tabs": [{"documentTab": {"body": {"content": [
            {"startIndex": 1, "endIndex": 5, "paragraph": {"elements": [
                {"startIndex": 1, "endIndex": 2, "inlineObjectElement": {}}, {"textRun": {"content": "ab\n"}}]}},
            {"startIndex": 5, "endIndex": 10, "paragraph": {"elements": [{"textRun": {"content": "WORD\n"}}]}}]},
            "commentAnchors": {"a": {"ranges": [{"startIndex": 5, "endIndex": 9}]}}}}],
            "comments": [{"commentId": "c", "anchorId": "a", "headPost": {"author": {}, "content": "x"}}]}
        self.assertEqual(anchored_comments(resp)[0]["anchored"], "WORD")

    def test_a_comment_on_changed_text_has_no_place(self):
        drive = FakeDrive()
        drive.create("t", "First line\n\nAn ALPHA second\n", None)
        drive.comment_in_ui("doc-1", "ALPHA", "why alpha?")
        before = anchored_comments(drive.get_doc("doc-1", comments=True))
        drive.update("doc-1", "First line\n\nAn OMEGA second\n")
        self.assertEqual(carry_comments(drive, "doc-1", before), {"carried": 0, "unplaced": ["ALPHA"], "undeleted": 0})


class Writes(_WithDoc):
    """push and sync through `write_doc`: edits where the diff allows, the whole replace with the comments carried
    where it does not, and the guard on the Doc's revision."""

    def setUp(self):
        super().setUp()
        self.run_cmd("init", str(self.md))
        self.drive.calls.clear()

    def edit_local(self, old, new):
        self.md.write_text(self.md.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")

    def test_a_text_edit_is_pushed_as_edits_and_the_doc_reads_back_the_same(self):
        self.drive.comment_in_ui("doc-1", "vendor", "which one?")
        self.edit_local("Call the vendor", "Phone the vendor")
        self.edit_local("## Notes", "## Notes\n\nA new paragraph.")
        code, out, err = self.run_cmd("push", str(self.md))
        self.assertEqual((code, err), (EXIT_OK, ""))
        self.assertIn("pushed https://docs.google.com/document/d/doc-1/edit by 8 edits", out)
        self.assertEqual(self.drive.calls, ["export", "get_doc", "batch_update", "export"])
        self.assertIn("- [ ] T-002 Phone the vendor (due 2026-10-24)\n", self.drive.docs["doc-1"])
        self.assertIn("## Notes\n\nA new paragraph.\n\nPlain paragraph", self.drive.docs["doc-1"])
        self.assertEqual(self.drive.comments["doc-1"][0]["anchored"], "vendor")  # untouched: still anchored
        state = json.loads(state_path(self.md).read_text(encoding="utf-8"))
        self.assertEqual(state["snapshot"], state["local"])

    def test_a_tick_replaces_the_doc_and_carries_the_comments(self):
        self.drive.comment_in_ui("doc-1", "vendor", "which one?", author="Ann")
        self.drive.comment_in_ui("doc-1", "Done item", "really?", author="token user")
        self.edit_local("- [ ] T-002", "- [x] T-002")
        self.edit_local("T-003 Done item", "T-003 Finished item")
        code, out, err = self.run_cmd("sync", str(self.md), "--json")
        result = json.loads(out)
        self.assertEqual((code, result["write"], result["why"], result["carried"], result["unplaced"],
                          result["undeleted"]), (EXIT_OK, "replace", "tick", 1, ["Done item"], 1))  # Ann's orphan
        self.assertIn("by a whole replace (tick), 1 comments carried, 1 not placed", result["message"])
        self.assertIn("could not be carried", result["message"])
        self.assertEqual(self.drive.calls, ["get_doc", "export", "export", "get_doc", "get_doc", "update", "get_doc",
                                            "insert_comment", "delete_comment", "export"])
        self.assertEqual([(c["anchored"], c["author"]) for c in self.drive.comments["doc-1"]],
                         [(None, "Ann"), (None, "token user"), ("vendor", "token user")])

    def test_the_doc_moving_between_the_read_and_the_write_is_refused(self):
        self.edit_local("Call the vendor", "Phone the vendor")
        real = self.drive.get_doc

        def moved(doc_id, comments=False):
            doc = real(doc_id, comments)
            self.drive.revisions[doc_id] = self.drive.revisions.get(doc_id, 0) + 1
            return doc

        self.drive.get_doc = moved
        code, out, err = self.run_cmd("push", str(self.md))
        self.assertEqual(code, EXIT_MOVED)
        self.assertIn("push refused: the Doc changed while writing", err)

    def test_without_the_docs_api_the_push_replaces_as_before(self):
        self.drive.docs_api_enabled = False
        self.edit_local("Call the vendor", "Phone the vendor")
        code, out, err = self.run_cmd("push", str(self.md), "--json")
        result = json.loads(out)
        self.assertEqual((code, result["write"], result["why"]), (EXIT_OK, "replace", "docs_api"))
        self.assertEqual(self.drive.calls, ["export", "get_doc", "update", "export"])

    def test_write_doc_reports_edits_or_the_replace(self):
        text = (FIXTURES / "04-task-list.in.md").read_text(encoding="utf-8")
        old = normalize(self.drive.export("doc-1"))
        self.assertEqual(write_doc(self.drive, "doc-1", old, text.replace("## Notes", "## Remarks")),
                         {"write": "edits", "requests": 3})
        old = normalize(self.drive.export("doc-1"))
        self.assertEqual(write_doc(self.drive, "doc-1", old, text.replace("## Notes", "## Remarks\n\n---")),
                         {"write": "replace", "why": "structure", "carried": 0, "unplaced": [], "undeleted": 0})
