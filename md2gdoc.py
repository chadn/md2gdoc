#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "google-api-python-client",
#   "google-auth-oauthlib",
#   "google-auth-httplib2",
# ]
# ///
"""md2gdoc: two-way sync between a markdown file and a native Google Doc.

This file is the whole tool. The text layer, `normalize()` and `push_form()`, follows docs/design.md "Script
design" with tests/fixtures/ as its evidence (PT-005). The commands `init`, `pull`, `push` and `status` and the
state file follow the same section (PT-006); `sync` is PT-007. The Google client libraries are imported only on
the auth path, so the text layer and the tests run without them.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

# A heading whose whole text the export wrapped in bold.
_HEADING_BOLD = re.compile(r"^(#{1,6} )\*\*((?:(?!\*\*).)+)\*\*[ \t]*$")
# Characters the export escapes in prose; `\`` is left alone, since no push sends a raw fence.
_ESCAPE = re.compile(r"\\([-\[\]#_<>:*.])")
# An escape that keeps a line from becoming a block: a bullet, heading, quote, or ordered item.
_BLOCK_ESCAPE = re.compile(r"^[ \t]*\\[-#*+>]|^[ \t]*\d+\\\.")
# A code span inside a line; what is inside it is left alone.
_SPAN = re.compile(r"(`+)(?!`)(.+?)(?<!`)\1(?!`)")
# A link whose text is its own URL.
_AUTOLINK = re.compile(r"\[(https?://[^\]\s]+)\]\(\1\)")
# A table delimiter row, with or without alignment colons.
_DELIM_ROW = re.compile(r"^\|(?:[ \t]*:?-+:?[ \t]*\|)+[ \t]*$")
# A list item: bullet or ordered, with its indent.
_LIST_ITEM = re.compile(r"^([ \t]*)(?:[-*+]|\d+[.)])[ \t]+")
# A whole line that is one code span, with optional leading whitespace outside it.
_SPAN_LINE = re.compile(r"^([ \t]*)(`+)(.*)\2[ \t]*$")
# A fence line, backtick or tilde, at the left margin.
_FENCE = re.compile(r"^(```+|~~~+)(.*)$")
# Lines that start a block other than a paragraph, once their indent is removed.
_BLOCK_START = re.compile(r"^(?:#{1,6} |>|\||[-*+][ \t]|\d+[.)][ \t]|```|~~~|\[\^|---|\*\*\*|=+$)")
# Lines that cannot take a hard break: blank, fence, heading, table, rule, or a code run's own line.
_NO_BREAK = re.compile(r"^(?:$|#{1,6} |\||```|~~~|---|\*\*\*|=+$)")


def normalize(text: str, src: str | None = None) -> str:
    """Undo the export's noise so a Doc's markdown compares to the file's.

    `src` is the local file, used only for what the Doc cannot hold: the fences' info strings.
    """
    lines = text.split("\n")
    lines = _fold_code_runs(lines, _info_strings(src) if src is not None else [])
    out: list[str] = []
    stack: list[int] = []  # indents of the open list levels, as the export wrote them
    for line, is_code in lines:
        if is_code:
            out.append(line)
            continue
        line = line.rstrip(" \t")
        if line == "":
            out.append(line)
            continue
        line = _HEADING_BOLD.sub(r"\1\2", line)
        if _DELIM_ROW.match(line):
            line = "|" + "".join(" --- |" for _ in line.strip("| \t").split("|"))
        line = _outside_spans(line, _unescape)
        item = _LIST_ITEM.match(line)
        if item:
            width = len(item.group(1).expandtabs(4))
            while stack and width < stack[-1]:
                stack.pop()
            if not stack or width > stack[-1]:
                stack.append(width)
            line = " " * (4 * (len(stack) - 1)) + line[len(item.group(1)):]
        elif not line.startswith((" ", "\t")):
            stack.clear()
        out.append(line)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def push_form(text: str) -> str:
    """The markdown sent to Google in place of the file; never written back.

    Fenced blocks become code runs; soft line breaks in a paragraph become hard breaks, so the Doc keeps the
    file's lines; everything else passes through.
    """
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        fence = _FENCE.match(lines[i])
        if fence:
            close = _find_close(lines, i + 1, fence.group(1))
            if close is not None:
                out.extend(_code_run(lines[i + 1:close]))
                i = close + 1
                continue
        line = lines[i]
        if _takes_break(line) and i + 1 < len(lines) and _continues(lines[i + 1]) and not (
            _span_line(line) and (_span_line(lines[i + 1]) or lines[i + 1].strip(" \t") == "")
        ):
            line = line.rstrip(" \t") + "  "
        out.append(line)
        i += 1
    return "\n".join(out)


def _find_close(lines: list[str], start: int, opener: str) -> int | None:
    for j in range(start, len(lines)):
        m = _FENCE.match(lines[j])
        if m and m.group(1)[0] == opener[0] and len(m.group(1)) >= len(opener) and m.group(2).strip() == "":
            return j
    return None


def _code_run(code: list[str]) -> list[str]:
    run: list[str] = []
    for line in code:
        stripped = line.lstrip(" \t")
        if stripped == "":
            run.append("&nbsp;")
            continue
        indent = line[: len(line) - len(stripped)].replace(" ", "&nbsp;").replace("\t", "&#9;")
        ticks = "`" * (max((len(m) for m in re.findall(r"`+", stripped)), default=0) + 1)
        if stripped.startswith("`") or stripped.endswith("`"):
            stripped = f" {stripped} "
        run.append(f"{indent}{ticks}{stripped}{ticks}")
    if len(run) == 1:
        run.append("&nbsp;")
    return [line + "  " for line in run[:-1]] + run[-1:]


def _takes_break(line: str) -> bool:
    """A paragraph line, list item, or continuation line: text the Doc would otherwise join with the next."""
    return not _NO_BREAK.match(line.lstrip(" \t"))


def _continues(line: str) -> bool:
    """A line that markdown would join onto the previous one as the same paragraph or item."""
    text = line.lstrip(" \t")
    return text != "" and not _BLOCK_START.match(text)


def _outside_spans(line: str, rewrite) -> str:
    """Apply `rewrite` to the parts of a line that are not inside a code span."""
    out: list[str] = []
    pos = 0
    for m in _SPAN.finditer(line):
        out.append(rewrite(line[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(rewrite(line[pos:]))
    return "".join(out)


def _unescape(text: str) -> str:
    keep = _BLOCK_ESCAPE.match(text)
    head, tail = (text[: keep.end()], text[keep.end():]) if keep else ("", text)
    return head + _AUTOLINK.sub(r"\1", _ESCAPE.sub(r"\1", tail))


def _info_strings(src: str) -> list[str]:
    infos: list[str] = []
    lines = src.split("\n")
    i = 0
    while i < len(lines):
        m = _FENCE.match(lines[i])
        if m:
            close = _find_close(lines, i + 1, m.group(1))
            if close is not None:
                infos.append(m.group(2).strip())
                i = close + 1
                continue
        i += 1
    return infos


def _span_line(line: str) -> tuple[str, str] | None:
    """(leading whitespace, span content) when the whole line is one code span, else None."""
    m = _SPAN_LINE.match(line)
    if not m:
        return None
    ticks, content = m.group(2), m.group(3)
    if re.search(rf"(?<!`)`{{{len(ticks)}}}(?!`)", content):
        return None
    if content.startswith(" ") and content.endswith(" ") and content.strip(" ") != "":
        content = content[1:-1]
    return m.group(1), content


def _fold_code_runs(lines: list[str], infos: list[str]) -> list[tuple[str, bool]]:
    """Turn each code run back into a fence, and keep a fence the text already has as it is.

    The second value marks code lines the other rules must skip.
    """
    runs: list[tuple[int, int]] = []  # (first, last) line indexes of each run
    fences: list[tuple[int, int]] = []  # (open, close) line indexes of each fence already in the text
    i = 0
    while i < len(lines):
        fence = _FENCE.match(lines[i])
        close = _find_close(lines, i + 1, fence.group(1)) if fence else None
        if close is not None:
            fences.append((i, close))
            i = close + 1
            continue
        if not _run_line(lines[i]) or not lines[i].endswith("  "):
            i += 1
            continue
        j = i
        while j + 1 < len(lines) and lines[j].endswith("  ") and _run_line(lines[j + 1]):
            j += 1
        if j > i and any(_span_line(line) for line in lines[i:j + 1]):
            runs.append((i, j))
        i = j + 1
    use_infos = infos if len(infos) == len(runs) else [""] * len(runs)
    regions = sorted([(first, last, info) for (first, last), info in zip(runs, use_infos)]
                     + [(first, last, None) for first, last in fences])
    out: list[tuple[str, bool]] = []
    pos = 0
    for first, last, info in regions:
        out.extend((line, False) for line in lines[pos:first])
        if info is None:
            out.extend((line, True) for line in lines[first:last + 1])
        else:
            body = []
            for line in lines[first:last + 1]:
                span = _span_line(line)
                body.append("" if span is None else span[0] + span[1])
            while body and body[-1] == "":
                body.pop()
            out.append(("```" + info, True))
            out.extend((line, True) for line in body)
            out.append(("```", True))
        pos = last + 1
    out.extend((line, False) for line in lines[pos:])
    return out


def _run_line(line: str) -> bool:
    """A line a code run may hold: one code span, or a blank code line (whitespace, never empty)."""
    return _span_line(line) is not None or (line != "" and line.strip(" \t") == "")


# The commands. Exit codes: 0 done, 1 usage, setup or Google error, 2 a conflict (sync, PT-007), 3 the Doc
# changed since the last sync so a push was refused.

EXIT_OK, EXIT_ERROR, EXIT_CONFLICT, EXIT_MOVED = 0, 1, 2, 3
STATE_SUFFIX = ".gdoc.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
HERE = Path(__file__).resolve().parent

HELP = f"""\
Two-way sync between one markdown file and one native Google Doc. Either side may add, edit, or tick a line;
`sync` (not yet built) merges both, `push` and `pull` move one way.

commands:
  init FILE      create the Doc from FILE and write the state file; prints the Doc's link
  pull FILE      export the Doc, undo the converter's noise, write FILE; refused when FILE changed since the
                 last sync, unless --force
  push FILE      replace the Doc's content from FILE; refused when the Doc changed since the last sync
  status FILE    which side changed since the last sync
  --dry-run      on any command: say what would happen, change nothing (status: local side only, no network)

setup (once; the full walkthrough is docs/setup.md at github.com/chadn/md2gdoc):
  1. a Google Cloud project with the Drive API enabled and an OAuth consent screen, scope
     https://www.googleapis.com/auth/drive.file only, published (In production)
  2. an OAuth client of type Desktop app, its JSON saved as client_secret.json next to this script
  3. the first command that needs Google opens a browser once; the token is cached and refreshes itself
  The script sees only the Docs it created (drive.file): let `init` make each Doc.

files:
  FILE{STATE_SUFFIX}       the state file next to FILE: Doc id, link, Drive version, the normalized snapshot of
                       what the Doc held after the last sync (the merge base) and of what FILE held; commit it,
                       so a clone syncs the same Doc
  client_secret.json   the OAuth client, next to this script; never commit it
  token.json           the cached token, next to this script; never commit it (--account NAME uses token-NAME.json)

exit codes:
  0  done            1  usage, setup, or Google error      2  conflict, both sides changed one line (sync)
  3  refused: push when the Doc changed since the last sync, pull when FILE did; sync, or pull --force
"""


def state_path(md: Path) -> Path:
    return md.with_name(md.name + STATE_SUFFIX)


def load_state(md: Path) -> dict:
    path = state_path(md)
    if not path.exists():
        raise SystemExit(f"md2gdoc: no state file {path}; run `init {md}` first")
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(md: Path, state: dict) -> None:
    state_path(md).write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_md(md: Path) -> str:
    if not md.is_file():
        raise SystemExit(f"md2gdoc: {md} is not a file")
    return md.read_text(encoding="utf-8")


def diff(a: str, b: str, a_name: str, b_name: str) -> str:
    return "".join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), a_name, b_name))


class Drive:
    """The four Drive calls the commands make; tests pass a fake with the same methods."""

    def __init__(self, creds):
        from googleapiclient.discovery import build  # lazy: the text layer runs without the libraries

        self.api = build("drive", "v3", credentials=creds, cache_discovery=False)

    @staticmethod
    def _media(markdown: str):
        import io
        from googleapiclient.http import MediaIoBaseUpload

        return MediaIoBaseUpload(io.BytesIO(markdown.encode("utf-8")), mimetype="text/markdown")

    def create(self, name: str, markdown: str, folder: str | None) -> dict:
        body = {"name": name, "mimeType": "application/vnd.google-apps.document"}
        if folder:
            body["parents"] = [folder]
        f = self.api.files().create(body=body, media_body=self._media(markdown), fields="id,webViewLink,version",
                                    supportsAllDrives=True).execute()
        return {"doc_id": f["id"], "link": f["webViewLink"], "version": int(f["version"])}

    def export(self, doc_id: str) -> str:
        return self.api.files().export(fileId=doc_id, mimeType="text/markdown").execute().decode("utf-8")

    def update(self, doc_id: str, markdown: str) -> int:
        f = self.api.files().update(fileId=doc_id, media_body=self._media(markdown), fields="version",
                                    supportsAllDrives=True).execute()
        return int(f["version"])

    def version(self, doc_id: str) -> int:
        f = self.api.files().get(fileId=doc_id, fields="version", supportsAllDrives=True).execute()
        return int(f["version"])


def connect(account: str | None) -> Drive:
    """The auth path: a cached token next to this script, else one browser login with the client file."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token = HERE / (f"token-{account}.json" if account else "token.json")
    client = HERE / "client_secret.json"
    creds = Credentials.from_authorized_user_file(token, SCOPES) if token.exists() else None
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token.write_text(creds.to_json())
        except Exception as e:  # a revoked or expired token (Testing status): log in again
            print(f"md2gdoc: the token did not refresh ({e}); opening the browser", file=sys.stderr)
    if not creds or not creds.valid:
        if not client.exists():
            raise SystemExit(f"md2gdoc: no {client}; see `--help` under setup")
        creds = InstalledAppFlow.from_client_secrets_file(client, SCOPES).run_local_server(port=0)
        token.write_text(creds.to_json())
    return Drive(creds)


def cmd_init(args, drive) -> int:
    md = Path(args.file)
    text = read_md(md)
    if state_path(md).exists():
        raise SystemExit(f"md2gdoc: {state_path(md)} exists; this file already has a Doc")
    name = args.name or md.stem
    if args.dry_run:
        print(f"would create Doc {name!r} from {md} ({len(text.splitlines())} lines) and write {state_path(md)}")
        return EXIT_OK
    d = drive(args.account)
    return _record(md, text, d.create(name, push_form(text), args.folder), d, "created")


def cmd_pull(args, drive) -> int:
    md = Path(args.file)
    state = load_state(md)
    local = read_md(md) if md.is_file() else ""
    if normalize(local) != state["local"] and not args.force and not args.dry_run:
        print(f"pull refused: {md} changed since the last sync; sync, or pull --force to overwrite it",
              file=sys.stderr)
        return EXIT_MOVED
    d = drive(args.account)
    new = normalize(d.export(state["doc_id"]), local)
    if args.dry_run:
        print(diff(local, new, f"{md} (local)", f"{md} (Doc)") or f"{md} already matches the Doc")
        return EXIT_OK
    md.write_text(new, encoding="utf-8")
    state.update(version=d.version(state["doc_id"]), snapshot=new, local=new)
    save_state(md, state)
    print(f"pulled {md}: {'changed' if new != local else 'unchanged'}")
    return EXIT_OK


def cmd_push(args, drive) -> int:
    md = Path(args.file)
    state = load_state(md)
    text = read_md(md)
    local = normalize(text)
    if local == state["local"]:
        print(f"nothing to push: {md} matches the last sync")
        return EXIT_OK
    d = drive(args.account)
    # The guard exports and compares every time: a matching Drive version is not proof (design.md, item 2).
    doc_text = normalize(d.export(state["doc_id"]), text)
    if doc_text != state["snapshot"]:
        print("push refused: the Doc changed since the last sync; pull or sync first", file=sys.stderr)
        return EXIT_MOVED
    if args.dry_run:
        print(diff(state["local"], local, f"{md} (last sync)", f"{md} (local)"))
        return EXIT_OK
    d.update(state["doc_id"], push_form(text))
    return _record(md, text, {"doc_id": state["doc_id"], "link": state["link"]}, d, "pushed")


def cmd_status(args, drive) -> int:
    md = Path(args.file)
    state = load_state(md)
    local = normalize(read_md(md)) if md.is_file() else ""
    print(f"{md}: {'changed' if local != state['local'] else 'unchanged'} since the last sync")
    if args.dry_run:
        return EXIT_OK
    d = drive(args.account)
    doc_text = normalize(d.export(state["doc_id"]))
    version = d.version(state["doc_id"])
    print(f"Doc {state['link']}: {'changed' if doc_text != state['snapshot'] else 'unchanged'}"
          f" (version {state['version']} -> {version})")
    return EXIT_OK


def _record(md: Path, text: str, state: dict, d: Drive, verb: str) -> int:
    """After a create or an update: export once more and store what the Doc now holds as the snapshot."""
    snapshot = normalize(d.export(state["doc_id"]), text)
    state.update(version=d.version(state["doc_id"]), snapshot=snapshot, local=normalize(text))
    save_state(md, state)
    lost = diff(normalize(text), snapshot, f"{md} (local)", f"{md} (Doc)")
    if lost:
        print(f"the Doc holds a different text; `pull --force` would write it back (docs/features.md lists what "
              f"the converter loses):\n{lost}", file=sys.stderr)
    print(f"{verb} {state['link']}")
    return EXIT_OK


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # usage errors exit 1, as `--help` says; 2 is a conflict
        self.print_usage(sys.stderr)
        raise SystemExit(f"md2gdoc: {message}")


def main(argv: list[str] | None = None, drive=connect) -> int:
    parser = _Parser(prog="md2gdoc.py", description=HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")
    for name, fn, what in (("init", cmd_init, "create the Doc and the state file"),
                           ("pull", cmd_pull, "write the Doc's content to the file"),
                           ("push", cmd_push, "replace the Doc's content from the file"),
                           ("status", cmd_status, "which side changed")):
        p = sub.add_parser(name, help=what)
        p.add_argument("file", help="the markdown file")
        p.add_argument("--dry-run", action="store_true", help="say what would happen; change nothing")
        p.add_argument("--account", help="use token-NAME.json next to the script instead of token.json")
        if name == "init":
            p.add_argument("--name", help="the Doc's title (default: the file's name without .md)")
            p.add_argument("--folder", help="Drive folder id to create the Doc in")
        if name == "pull":
            p.add_argument("--force", action="store_true", help="overwrite the file even if it changed")
        p.set_defaults(fn=fn)
    args = parser.parse_args(argv)
    return args.fn(args, drive)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # a Google error is one line, not a traceback; anything else is a bug
        if type(e).__name__ != "HttpError":
            raise
        sys.exit(f"md2gdoc: Google error: {e}")
