"""The commands against a fake Drive: the state file, the dry runs, the push guard, the exit codes."""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from md2gdoc import (  # noqa: E402
    EXIT_CONFLICT, EXIT_MOVED, EXIT_OK, SCOPE_URL, config_dir, error_object, main, merge3, normalize, profile_dir,
    push_form, state_path, token_scope,
)

FIXTURES = ROOT / "tests" / "fixtures"


class FakeDrive:
    """Holds one Doc as the markdown last uploaded; exports it through fixture 04's known noise."""

    def __init__(self):
        self.docs: dict[str, str] = {}
        self.versions: dict[str, int] = {}
        self.calls: list[str] = []

    def create(self, name, markdown, folder):
        self.calls.append("create")
        doc_id = f"doc-{len(self.docs) + 1}"
        self.docs[doc_id], self.versions[doc_id] = markdown, 5
        return {"doc_id": doc_id, "link": f"https://docs.google.com/document/d/{doc_id}/edit", "version": 5}

    def export(self, doc_id):
        """Two of the converter's habits: a bold heading, and a blank line put before a list after a paragraph."""
        self.calls.append("export")
        out: list[str] = []
        for line in self.docs[doc_id].split("\n"):
            if line.startswith("- ") and out and out[-1] and not out[-1].startswith(("-", " ", "#")):
                out.append("")
            out.append(f"# **{line[2:]}**" if line.startswith("# ") else line)
        return "\n".join(out)

    def update(self, doc_id, markdown):
        self.calls.append("update")
        self.docs[doc_id] = markdown
        self.versions[doc_id] += 1
        return self.versions[doc_id]

    def version(self, doc_id):
        return self.versions[doc_id]

    def lookup(self, doc_id):
        self.calls.append("lookup")
        if doc_id not in self.docs:
            raise KeyError(doc_id)  # Google answers 404; the fake has no HttpError
        return {"doc_id": doc_id, "link": f"https://docs.google.com/document/d/{doc_id}/edit",
                "version": self.versions[doc_id]}

    def make_by_hand(self, markdown):
        """A Doc the script did not create, as the Docs UI would leave it."""
        doc_id = f"hand-{len(self.docs) + 1}"
        self.docs[doc_id], self.versions[doc_id] = markdown, 2
        return doc_id

    def edit_in_ui(self, doc_id, old, new):
        self.docs[doc_id] = self.docs[doc_id].replace(old, new)
        self.versions[doc_id] += 1


class _WithDoc(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.md = Path(self.tmp.name) / "tasks.md"
        self.md.write_text((FIXTURES / "04-task-list.in.md").read_text(encoding="utf-8"), encoding="utf-8")
        self.drive = FakeDrive()

    def tearDown(self):
        self.tmp.cleanup()

    def run_cmd(self, *argv):
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
        self.assertEqual(self.drive.calls, ["export", "lookup"])
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
        self.md.write_text(self.md.read_text(encoding="utf-8") + "- [ ] T-004 right after the paragraph\n",
                           encoding="utf-8")
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
        self.assertEqual(sorted(state), ["doc_id", "link", "local", "snapshot", "version"])

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
        self.assertEqual((code, self.drive.calls), (EXIT_OK, ["export"]))
        self.assertIn("in sync", out)

    def test_both_sides_edits_are_merged_written_and_pushed(self):
        self.edit_local("- [ ] T-001", "- [x] T-001")
        self.edit_local("- [x] T-003 Done item", "- [x] T-003 Reworded locally, done item")
        self.drive.edit_in_ui("doc-1", "- [ ] T-002", "- [x] T-002")
        self.drive.edit_in_ui("doc-1", "## Notes", "- [ ] T-004 typed in the Doc\n\n## Notes")
        code, out, err = self.run_cmd("sync", str(self.md), "--dry-run")
        self.assertEqual((code, self.drive.calls), (EXIT_OK, ["export"]))
        self.assertIn("+- [x] T-002", out)
        self.assertIn("+- [x] T-001", out)
        code, out, err = self.run_cmd("sync", str(self.md))
        self.assertEqual((code, err), (EXIT_OK, ""))
        text = self.md.read_text(encoding="utf-8")
        for line in ("- [x] T-001", "- [x] T-002", "- [x] T-003 Reworded locally", "- [ ] T-004 typed in the Doc"):
            self.assertIn(line, text)
        self.assertEqual(self.drive.docs["doc-1"], push_form(text))
        self.assertEqual(self.drive.calls, ["export", "export", "export", "update", "export"])  # the guard export
        state = json.loads(state_path(self.md).read_text(encoding="utf-8"))
        self.assertEqual((state["version"], state["local"], state["snapshot"]), (8, text, text))
        code, out, _ = self.run_cmd("sync", str(self.md))
        self.assertIn("in sync", out)

    def test_a_doc_only_change_is_pulled_and_nothing_pushed(self):
        self.drive.edit_in_ui("doc-1", "- [ ] T-002", "- [x] T-002")
        code, out, _ = self.run_cmd("sync", str(self.md))
        self.assertEqual((code, self.drive.calls), (EXIT_OK, ["export"]))
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
        self.assertEqual(self.drive.calls, ["export", "export"])

    def test_the_converters_own_blank_line_is_never_a_conflict(self):
        self.md.write_text(self.md.read_text(encoding="utf-8") + "- [ ] T-004 right after the paragraph\n",
                           encoding="utf-8")
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
        self.md.write_text(self.md.read_text(encoding="utf-8") + "- [ ] T-006 local\n", encoding="utf-8")
        self.drive.edit_in_ui("doc-1", "- [ ] T-002", "- [x] T-002")
        code, obj = self.run_json("status", str(self.md))
        self.assertEqual((obj["local_changed"], obj["doc_changed"], obj["version"]), (True, True, 6))
        code, obj = self.run_json("pull", str(self.md))
        self.assertEqual((code, obj["reason"]), (EXIT_MOVED, "refused_file_changed"))
        self.assertIn("pull refused", obj["message"])
        code, obj = self.run_json("sync", str(self.md), "--dry-run")
        self.assertEqual((code, obj["reason"], obj["written"], obj["pushed"]), (EXIT_OK, "synced", False, False))
        self.assertIn("+- [x] T-002", obj["diff_file"])
        self.assertIn("+- [ ] T-006 local", obj["diff_doc"])
        code, obj = self.run_json("sync", str(self.md))
        self.assertEqual((code, obj["reason"], obj["written"], obj["pushed"], obj["version"]),
                         (EXIT_OK, "synced", True, True, 7))
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
