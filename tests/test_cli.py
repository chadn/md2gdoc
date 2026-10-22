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
    EXIT_MOVED, EXIT_OK, SCOPE_URL, config_dir, main, normalize, profile_dir, push_form, state_path, token_scope,
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

    def edit_in_ui(self, doc_id, old, new):
        self.docs[doc_id] = self.docs[doc_id].replace(old, new)
        self.versions[doc_id] += 1


class Commands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.md = Path(self.tmp.name) / "tasks.md"
        self.md.write_text((FIXTURES / "04-task-list.in.md").read_text())
        self.drive = FakeDrive()

    def tearDown(self):
        self.tmp.cleanup()

    def run_cmd(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv), drive=lambda account, scope: self.drive)
        return code, out.getvalue(), err.getvalue()

    def test_init_creates_the_doc_and_the_state_file(self):
        code, out, err = self.run_cmd("init", str(self.md))
        self.assertEqual(code, EXIT_OK)
        self.assertIn("created https://docs.google.com/document/d/doc-1/edit", out)
        self.assertEqual(err, "")
        state = json.loads(state_path(self.md).read_text())
        self.assertEqual(state["doc_id"], "doc-1")
        self.assertEqual(state["snapshot"], normalize(self.md.read_text()))
        self.assertEqual(self.drive.docs["doc-1"], push_form(self.md.read_text()))
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

    def test_status_names_the_side_that_changed(self):
        self.run_cmd("init", str(self.md))
        code, out, _ = self.run_cmd("status", str(self.md))
        self.assertIn("tasks.md: unchanged", out)
        self.assertIn("unchanged (version 5 -> 5)", out)
        self.md.write_text(self.md.read_text().replace("- [ ] T-001", "- [x] T-001"))
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
        self.md.write_text(self.md.read_text() + "- [ ] T-004 right after the paragraph\n")
        code, _, err = self.run_cmd("push", str(self.md))
        self.assertEqual(code, EXIT_OK)
        self.assertIn("the Doc holds a different text", err)
        state = json.loads(state_path(self.md).read_text())
        self.assertNotEqual(state["snapshot"], state["local"])
        code, out, _ = self.run_cmd("push", str(self.md))
        self.assertIn("nothing to push", out)
        self.assertEqual(self.drive.versions["doc-1"], 6)
        code, out, _ = self.run_cmd("status", str(self.md))
        self.assertIn("tasks.md: unchanged", out)
        self.assertIn("Doc https://docs.google.com/document/d/doc-1/edit: unchanged", out)

    def test_push_replaces_the_doc_and_stores_the_new_snapshot(self):
        self.run_cmd("init", str(self.md))
        self.md.write_text(self.md.read_text() + "\n- [ ] T-004 added locally\n")
        code, out, _ = self.run_cmd("push", str(self.md), "--dry-run")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("+- [ ] T-004 added locally", out)
        self.assertNotIn("update", self.drive.calls)
        code, out, err = self.run_cmd("push", str(self.md))
        self.assertEqual((code, err), (EXIT_OK, ""))
        self.assertIn("T-004 added locally", self.drive.docs["doc-1"])
        state = json.loads(state_path(self.md).read_text())
        self.assertEqual((state["version"], state["snapshot"]), (6, normalize(self.md.read_text())))

    def test_push_is_refused_when_the_doc_moved(self):
        self.run_cmd("init", str(self.md))
        self.md.write_text(self.md.read_text().replace("- [ ] T-001", "- [x] T-001"))
        self.drive.edit_in_ui("doc-1", "- [ ] T-002", "- [x] T-002")
        code, _, err = self.run_cmd("push", str(self.md))
        self.assertEqual(code, EXIT_MOVED)
        self.assertIn("push refused", err)
        self.assertNotIn("update", self.drive.calls)

    def test_pull_is_refused_when_the_file_changed_unless_forced(self):
        self.run_cmd("init", str(self.md))
        self.md.write_text(self.md.read_text() + "- [ ] T-006 added locally\n")
        code, _, err = self.run_cmd("pull", str(self.md))
        self.assertEqual(code, EXIT_MOVED)
        self.assertIn("pull refused", err)
        self.assertIn("T-006", self.md.read_text())
        code, out, _ = self.run_cmd("pull", str(self.md), "--dry-run")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("-- [ ] T-006 added locally", out)
        code, _, _ = self.run_cmd("pull", str(self.md), "--force")
        self.assertEqual(code, EXIT_OK)
        self.assertNotIn("T-006", self.md.read_text())

    def test_pull_writes_the_normalized_export(self):
        self.run_cmd("init", str(self.md))
        self.drive.edit_in_ui("doc-1", "- [ ] T-002", "- [x] T-002")
        code, out, _ = self.run_cmd("pull", str(self.md), "--dry-run")
        self.assertIn("+- [x] T-002", out)
        self.assertNotIn("- [x] T-002", self.md.read_text())
        code, out, _ = self.run_cmd("pull", str(self.md))
        self.assertEqual(code, EXIT_OK)
        self.assertIn("pulled", out)
        self.assertIn("- [x] T-002", self.md.read_text())
        self.assertNotIn("**", self.md.read_text().split("\n")[0])
        state = json.loads(state_path(self.md).read_text())
        text = self.md.read_text()
        self.assertEqual((state["version"], state["snapshot"], state["local"]), (6, text, text))
        self.assertEqual(sorted(state), ["doc_id", "link", "local", "snapshot", "version"])

    def test_help_covers_setup_files_and_exit_codes(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as e:
            main(["--help"])
        self.assertEqual(e.exception.code, 0)
        for word in ("setup", "client_secret.json", "token.json", ".gdoc.json", "exit codes", "3  refused",
                     "--account", "--scope", "MD2GDOC_CONFIG_DIR", "MD2GDOC_ACCOUNT", "%APPDATA%", "pip install"):
            self.assertIn(word, out.getvalue())

    def test_a_usage_error_exits_1_not_2(self):
        for argv in (["bogus"], ["push"], []):
            err = io.StringIO()
            with redirect_stderr(err), self.assertRaises(SystemExit) as e:
                main(argv)
            self.assertEqual(e.exception.code, f"md2gdoc: {e.exception.code[9:]}", argv)
            self.assertIn("usage:", err.getvalue())

    def test_a_missing_state_file_is_an_error(self):
        with self.assertRaises(SystemExit) as e:
            self.run_cmd("status", str(self.md))
        self.assertIn("no state file", str(e.exception))


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
