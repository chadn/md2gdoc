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
design" with tests/fixtures/ as its evidence (PT-005). The commands `init`, `pull`, `push`, `sync` and `status`,
the state file and the merge follow the same section (PT-006, PT-007). The Google client libraries are imported only on
the auth path, so the text layer and the tests run without them.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
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
        out.append(rewrite(line[pos:m.start()], pos == 0))
        out.append(m.group(0))
        pos = m.end()
    out.append(rewrite(line[pos:], pos == 0))
    return "".join(out)


def _unescape(text: str, at_line_start: bool = True) -> str:
    """Drop the export's escapes; one that keeps the line from becoming a block stays, so only at the line's start
    (after a code span the export escapes a dash too, PT-008's real run, and there it is prose)."""
    keep = _BLOCK_ESCAPE.match(text) if at_line_start else None
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


# The merge (sync): three-way on normalized lines, base = the snapshot, ours = the file, theirs = the Doc.

OURS, THEIRS = "api-edited", "hand-edited"  # the conflict-marker labels (language.md)
_MARKER = re.compile(r"^(<{7} " + OURS + r"|>{7} " + THEIRS + r")$")


def merge3(base: str, ours: str, theirs: str) -> tuple[str, int]:
    """Merge two edits of `base`; returns the text and the number of conflicts, each marked in the text.

    Lines that match on all three sides are sync points; between two of them, a chunk changed on one side only
    takes that side, a chunk changed the same way on both takes it once, and a chunk changed differently on both
    is a conflict: both versions kept, `<<<<<<< api-edited` (the file) above, `>>>>>>> hand-edited` (the Doc)
    below. Where git would stop, two more rules keep a task list flowing, since neither loses a line: a chunk that
    kept its line count on both sides is merged line by line, so a box ticked on each of two neighbouring lines is no
    conflict; and lines one side added right before or after a chunk the other side changed are kept around the
    change, as are lines both sides added at the same place, the file's first. A line deleted on one side and edited
    on the other is a conflict, since the deletion is a change too.
    """
    a, b, c = base.split("\n"), ours.split("\n"), theirs.split("\n")
    out: list[str] = []
    conflicts = 0
    ia = ib = ic = 0
    for ja, jb, jc, size in _sync_regions(a, b, c):
        lines, n = _merge_chunk(a[ia:ja], b[ib:jb], c[ic:jc])
        out.extend(lines + a[ja:ja + size])
        conflicts += n
        ia, ib, ic = ja + size, jb + size, jc + size
    return "\n".join(out), conflicts


def _merge_chunk(x: list[str], y: list[str], z: list[str]) -> tuple[list[str], int]:
    """Merge one chunk between two sync points: base `x`, the file's `y`, the Doc's `z`; see `merge3`."""
    if y == x:
        return z, 0
    if z == x or y == z:
        return y, 0
    if not x:  # both sides added lines here: all kept, the file's first, what they share once
        p = next((i for i, (u, v) in enumerate(zip(y, z)) if u != v), min(len(y), len(z)))
        s = next((i for i, (u, v) in enumerate(zip(reversed(y[p:]), reversed(z[p:]))) if u != v),
                 min(len(y), len(z)) - p)
        return y + z[p:len(z) - s], 0
    if len(x) == len(y) == len(z) > 1:
        out: list[str] = []
        conflicts = 0
        for lines in zip(x, y, z):
            merged, n = _merge_chunk(*([line] for line in lines))
            out.extend(merged)
            conflicts += n
        return out, conflicts
    for mine, other in ((y, z), (z, y)):  # one side added lines at an end of the chunk; the other changed it
        if len(mine) > len(x) and mine[:len(x)] == x:
            return other + mine[len(x):], 0
        if len(mine) > len(x) and mine[len(mine) - len(x):] == x:
            return mine[:len(mine) - len(x)] + other, 0
    return [f"<<<<<<< {OURS}", *y, "=======", *z, f">>>>>>> {THEIRS}"], 1


def _sync_regions(a: list[str], b: list[str], c: list[str]) -> list[tuple[int, int, int, int]]:
    """(i, j, k, size): a[i:i+size] == b[j:j+size] == c[k:k+size], in order; the last one is empty, at the ends."""
    ab = difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()
    ac = difflib.SequenceMatcher(None, a, c, autojunk=False).get_matching_blocks()
    regions: list[tuple[int, int, int, int]] = []
    x = y = 0
    while x < len(ab) - 1 and y < len(ac) - 1:
        (i1, j1, n1), (i2, k2, n2) = ab[x], ac[y]
        lo, hi = max(i1, i2), min(i1 + n1, i2 + n2)
        if lo < hi:
            regions.append((lo, j1 + lo - i1, k2 + lo - i2, hi - lo))
        if i1 + n1 < i2 + n2:
            x += 1
        else:
            y += 1
    regions.append((len(a), len(b), len(c), 0))
    return regions


def has_markers(text: str) -> bool:
    return any(_MARKER.match(line) for line in text.split("\n"))


# The commands. Exit codes: 0 done, 1 usage, setup or Google error, 2 a conflict (sync), 3 the Doc changed since
# the last sync so a push was refused.

EXIT_OK, EXIT_ERROR, EXIT_CONFLICT, EXIT_MOVED = 0, 1, 2, 3
STATE_SUFFIX = ".gdoc.json"
SCOPES = ("drive.file", "drive")  # the short names; a scope URL is SCOPE_URL + name
SCOPE_URL = "https://www.googleapis.com/auth/"
CLIENT_FILE, TOKEN_FILE = "client_secret.json", "token.json"

HELP = f"""\
Two-way sync between one markdown file and one native Google Doc. Either side may add, edit, or tick a line;
`sync` merges both, `push` and `pull` move one way.

commands:
  init FILE      create the Doc from FILE and write the state file; prints the Doc's link
  pull FILE      export the Doc, undo the converter's noise, write FILE; refused when FILE changed since the
                 last sync, unless --force
  push FILE      replace the Doc's content from FILE; refused when the Doc changed since the last sync
  sync FILE      merge both sides' changes since the last sync, write FILE, push the Doc; a line changed
                 differently on both sides is written to FILE between <<<<<<< api-edited (FILE's version) and
                 >>>>>>> hand-edited (the Doc's), nothing is pushed, and the exit code is 2
  status FILE    which side changed since the last sync
  --dry-run      on any command: say what would happen, change nothing (status: local side only, no network)
  --account NAME on any command: the profile to use (default: $MD2GDOC_ACCOUNT, else `default`)
  --scope NAME   on any command: `drive.file` (default) or `drive`; chosen at a profile's first login, then
                 remembered in its token

setup (once per profile; the full walkthrough is docs/setup.md at github.com/chadn/md2gdoc):
  1. a Google Cloud project with the Drive API enabled and an OAuth consent screen, scope
     https://www.googleapis.com/auth/drive.file only (.../auth/drive for a `--scope drive` profile),
     published (In production)
  2. an OAuth client of type Desktop app, its JSON saved as {CLIENT_FILE} in the profile's folder (below)
  3. the first command that needs Google opens a browser once; the token is cached and refreshes itself
  The script sees only the Docs it created (drive.file): let `init` make each Doc. To sync a Doc made by
  hand, a second profile with `--scope drive`, best under a Google account that holds little else.
  Run: `uv run --script md2gdoc.py ...`, or `pip install google-api-python-client google-auth-oauthlib
  google-auth-httplib2` once and `python md2gdoc.py ...`.

files:
  FILE{STATE_SUFFIX}       the state file next to FILE: Doc id, link, Drive version, the normalized snapshot of
                       what the Doc held after the last sync (the merge base) and of what FILE held; commit it,
                       so a clone syncs the same Doc
  <config>/NAME/       one folder per profile, NAME the account name, holding that profile's {CLIENT_FILE}
                       (the OAuth client, from a Cloud project under that Google account) and {TOKEN_FILE} (the
                       cached token, which remembers the scope); neither is ever in a repository
  <config>             $MD2GDOC_CONFIG_DIR; else on Windows %APPDATA%\\md2gdoc; else $XDG_CONFIG_HOME/md2gdoc,
                       else ~/.config/md2gdoc

exit codes:
  0  done            1  usage, setup, or Google error
  2  conflict: both sides changed one line (sync), or FILE still holds conflict markers (sync, push)
  3  refused: push when the Doc changed since the last sync, pull when FILE did (sync, or pull --force);
     sync when the Doc changed between its export and its push (run it again)
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


def config_dir() -> Path:
    """The per-user directory holding the profiles (PD-002): an override, the platform's convention, else XDG."""
    if override := os.environ.get("MD2GDOC_CONFIG_DIR"):
        return Path(override)
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "md2gdoc"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "md2gdoc"


def profile_dir(account: str | None) -> Path:
    """The folder of one profile: `--account`, else $MD2GDOC_ACCOUNT, else `default`."""
    return config_dir() / (account or os.environ.get("MD2GDOC_ACCOUNT") or "default")


def token_scope(token_scopes: list[str] | None, requested: str | None) -> str:
    """The scope a run uses: the token's when it has one, else the request, else `drive.file`.

    A request that differs from the token's scope is an error, since a token is granted for one scope: the
    profile keeps its scope for life, and another scope is another profile.
    """
    held = [u[len(SCOPE_URL):] for u in token_scopes or [] if u.startswith(SCOPE_URL)]
    if held and requested and requested not in held:
        raise SystemExit(f"md2gdoc: this profile logged in with --scope {held[0]}; another scope is another "
                         f"profile (--account), or delete its {TOKEN_FILE} to log in again")
    return held[0] if held else requested or SCOPES[0]


def connect(account: str | None, scope: str | None = None) -> Drive:
    """The auth path: the profile's cached token, else one browser login with its client file."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    profile = profile_dir(account)
    token, client = profile / TOKEN_FILE, profile / CLIENT_FILE
    creds = Credentials.from_authorized_user_file(token) if token.exists() else None
    scopes = [SCOPE_URL + token_scope(creds.scopes if creds else None, scope)]
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token.write_text(creds.to_json())
        except Exception as e:  # a revoked or expired token (Testing status): log in again
            print(f"md2gdoc: the token did not refresh ({e}); opening the browser", file=sys.stderr)
    if not creds or not creds.valid:
        if not client.exists():
            raise SystemExit(f"md2gdoc: no {client}; save the OAuth client's JSON there (see `--help` under "
                             f"setup)")
        creds = InstalledAppFlow.from_client_secrets_file(client, scopes).run_local_server(port=0)
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
    d = drive(args.account, args.scope)
    return _record(md, text, d.create(name, push_form(text), args.folder), d, "created")


def cmd_pull(args, drive) -> int:
    md = Path(args.file)
    state = load_state(md)
    local = read_md(md) if md.is_file() else ""
    if normalize(local) != state["local"] and not args.force and not args.dry_run:
        print(f"pull refused: {md} changed since the last sync; sync, or pull --force to overwrite it",
              file=sys.stderr)
        return EXIT_MOVED
    d = drive(args.account, args.scope)
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
    if has_markers(text):
        print(f"push refused: {md} holds conflict markers from the last sync; resolve them first", file=sys.stderr)
        return EXIT_CONFLICT
    local = normalize(text)
    if local == state["local"]:
        print(f"nothing to push: {md} matches the last sync")
        return EXIT_OK
    d = drive(args.account, args.scope)
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
    d = drive(args.account, args.scope)
    doc_text = normalize(d.export(state["doc_id"]))
    version = d.version(state["doc_id"])
    print(f"Doc {state['link']}: {'changed' if doc_text != state['snapshot'] else 'unchanged'}"
          f" (version {state['version']} -> {version})")
    return EXIT_OK


def cmd_sync(args, drive) -> int:
    md = Path(args.file)
    state = load_state(md)
    text = read_md(md)
    if has_markers(text):
        print(f"sync refused: {md} holds conflict markers from the last sync; resolve them first", file=sys.stderr)
        return EXIT_CONFLICT
    local = normalize(text)
    d = drive(args.account, args.scope)
    theirs = normalize(d.export(state["doc_id"]), text)
    version = d.version(state["doc_id"])
    if local == state["local"] and theirs == state["snapshot"]:
        print(f"in sync: neither {md} nor the Doc changed since the last sync")
        return EXIT_OK
    # One side unchanged: the other side is the result, so the converter's own differences between the two
    # texts of the last sync (features.md, the blank line before a list) never read as a conflict.
    if local == state["local"]:
        merged, conflicts = theirs, 0
    elif theirs == state["snapshot"]:
        merged, conflicts = local, 0
    else:
        merged, conflicts = merge3(state["snapshot"], local, theirs)
    if conflicts:
        if args.dry_run:
            print(diff(local, merged, f"{md} (local)", f"{md} (merged, with markers)"))
        else:
            md.write_text(merged, encoding="utf-8")
        print(f"conflict: {conflicts} place{'s' if conflicts > 1 else ''} changed differently on both sides; "
              f"{'would write' if args.dry_run else 'wrote'} both versions to {md} between "
              f"<<<<<<< {OURS} and >>>>>>> {THEIRS}; nothing pushed", file=sys.stderr)
        return EXIT_CONFLICT
    if args.dry_run:
        print(diff(local, merged, f"{md} (local)", f"{md} (merged)") or f"{md} would not change")
        print(diff(theirs, merged, f"{md} (Doc)", f"{md} (merged)") or "the Doc would not change")
        return EXIT_OK
    if merged != local:
        md.write_text(merged, encoding="utf-8")
    if merged == theirs:
        state.update(version=version, snapshot=theirs, local=merged)
        save_state(md, state)
        print(f"synced {state['link']}: pulled, nothing to push")
        return EXIT_OK
    # The push guard is a fresh export, as in push: the version is no proof of anything (design.md, item 2).
    if normalize(d.export(state["doc_id"]), text) != theirs:
        print("push refused: the Doc changed while syncing; run sync again", file=sys.stderr)
        return EXIT_MOVED
    d.update(state["doc_id"], push_form(merged))
    return _record(md, merged, {"doc_id": state["doc_id"], "link": state["link"]}, d, "synced")


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
                           ("sync", cmd_sync, "merge both sides' changes, write the file, push the Doc"),
                           ("status", cmd_status, "which side changed")):
        p = sub.add_parser(name, help=what)
        p.add_argument("file", help="the markdown file")
        p.add_argument("--dry-run", action="store_true", help="say what would happen; change nothing")
        p.add_argument("--account", metavar="NAME",
                       help="the profile to use (default: $MD2GDOC_ACCOUNT, else default)")
        p.add_argument("--scope", choices=SCOPES, help="the Google scope for a profile's first login (default: "
                       "drive.file); remembered in its token")
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
