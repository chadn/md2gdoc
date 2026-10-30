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
the state file and the merge follow the same section (PT-006, PT-007). The write path, `plan_edits` and `write_doc`,
edits the Doc in place where it can and replaces it where it cannot, carrying the comments over (PT-009, "Whole-document
replace" there). The Google client libraries are imported only on the auth path, so the text layer and the tests run
without them.
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import json
import os
import re
import sys
from pathlib import Path

# A heading whose whole text the export wrapped in bold.
_HEADING_BOLD = re.compile(r"^(#{1,6} )\*\*((?:(?!\*\*).)+)\*\*[ \t]*$")
# Characters the export escapes in prose (`!`, `$` and `\` since fixture 14's math and alerts); `\`` is left alone,
# since no push sends a raw fence.
_ESCAPE = re.compile(r"\\([-\[\]#_<>:*.!$\\])")
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
# Blockquote markers at the start of a line, as many as it has.
_QUOTE = re.compile(r"^(?:[ \t]*>[ \t]?)*")
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
        inner, following = _quoted(line, lines[i + 1] if i + 1 < len(lines) else "")
        if _takes_break(inner) and _continues(following) and not (
            _span_line(inner) and (_span_line(following) or following.strip(" \t") == "")
        ):
            line = line.rstrip(" \t") + "  "
        out.append(line)
        i += 1
    return "\n".join(out)


def _quoted(line: str, following: str) -> tuple[str, str]:
    """Two lines inside the same blockquote markers, so a quote's lines take hard breaks as a paragraph's do (an
    alert's `[!NOTE]` line must stay its own line, fixture 14); lines quoted differently are themselves."""
    marks = [_QUOTE.match(x) for x in (line, following)]
    if marks[0].group(0).count(">") != marks[1].group(0).count(">"):
        return line, following
    return line[marks[0].end():], following[marks[1].end():]


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


# The two forms (PT-034). The file's form, `local` in the state file, is the normalized file: it keeps what Google's
# import drops (an HTML comment) and the file's own shape of a line the converter rewrites (a blank line before a
# list, a code span's trailing space). The Doc's form, `snapshot`, is the normalized export. A change made on one
# side is carried onto the other side's form by `replay`, so a Doc-only change leaves the file's form and a file-only
# change pushes nothing but the file's hunks; the two forms are never compared to each other.

_COMMENT_OPEN = re.compile(r"^ {0,3}<!--")
_RESOLVED_BOX = re.compile(r"^((?:    )*- )\[-\] ")


def _comment_lines(lines: list[str]) -> set[int]:
    """The indexes of the lines inside whole-line HTML comment blocks: a line starting with `<!--` (up to three spaces
    in), through the line holding `-->`; a comment that starts mid-line, one never closed, or one inside a fenced
    block is prose or code and stays."""
    skip: set[int] = set()
    fence: str | None = None
    i = 0
    while i < len(lines):
        m = _FENCE.match(lines[i])
        if fence is None and m and m.group(1)[0] in "`~":
            fence = m.group(1)
        elif fence is not None and m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
            fence = None
        elif fence is None and _COMMENT_OPEN.match(lines[i]):
            j = next((k for k in range(i, len(lines)) if "-->" in lines[k]), None)
            if j is not None:
                skip.update(range(i, j + 1))
                i = j + 1
                continue
        i += 1
    return skip


def doc_view(text: str) -> str:
    """The file's form as the Doc can hold it: the HTML comment blocks gone, as Google's import drops them, and the
    blank line that would double up with them; a file that opened with a comment opens with its first line."""
    lines = text.split("\n")
    skip = _comment_lines(lines)
    if not skip:
        return text
    out: list[str] = []
    for i, line in enumerate(lines):
        if i in skip:
            continue
        if line == "" and i - 1 in skip and (not out or out[-1] == ""):
            continue
        out.append(line)
    while len(out) > 1 and out[-1] == "" and out[-2] == "":
        out.pop()
    return "\n".join(out)


def _key(line: str) -> str:
    """What a line is for aligning the two forms: its text without the converter's rewrites of shape, a continuation
    line's indent and a resolved box shown open."""
    return _RESOLVED_BOX.sub(r"\1[ ] ", line.strip())


def replay(base: str, new: str, target: str) -> str:
    """The hunks of `base` to `new` carried onto `target`, the same text as `base` in the other form.

    The two forms are aligned line by line on `_key`, so a line the converter only reshaped (a continuation line it
    indented, a `[-]` it shows as `[ ]`) pairs with its other form, and the runs left unpaired are the lines one form
    alone has: the blank the converter puts before a list, an HTML comment. A hunk's edge inside such a run, or an
    insertion at its edge, takes the whole run, carrying the run's unchanged lines along in `new`'s form, so nothing
    is lost; a hunk that spans a comment of `target` keeps the comment, after the hunk's lines, between blank lines.
    """
    a, c, b = base.split("\n"), new.split("\n"), target.split("\n")
    comments = _comment_lines(b)
    keys_b = [object() if i in comments else _key(line) for i, line in enumerate(b)]
    blocks = difflib.SequenceMatcher(None, [_key(x) for x in a], keys_b, autojunk=False).get_matching_blocks()
    in_block = [False] * (len(a) + 1)
    for ai, _, n in blocks:
        for i in range(ai, ai + n):
            in_block[i] = True
    in_block[len(a)] = True

    def gap(i: int) -> tuple[int, int]:  # the unpaired run of `a` holding position i
        lo = hi = i
        while lo > 0 and not in_block[lo - 1]:
            lo -= 1
        while hi < len(a) and not in_block[hi]:
            hi += 1
        return lo, hi

    hunks: list[list[int]] = []
    for tag, i1, i2, k1, k2 in difflib.SequenceMatcher(None, a, c, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        if i1 == i2 and (not in_block[i1] or (i1 and not in_block[i1 - 1])):  # an insertion touching a run
            lo, hi = gap(i1 if not in_block[i1] else i1 - 1)
        else:
            lo = gap(i1)[0] if not in_block[i1] else i1
            hi = gap(i2 - 1)[1] if i2 > i1 and not in_block[i2 - 1] else i2
        k1, k2 = k1 - (i1 - lo), k2 + (hi - i2)
        if hunks and lo <= hunks[-1][1]:  # the widened hunk reaches the one before: one hunk
            hunks[-1][1], hunks[-1][3] = hi, k2
        else:
            hunks.append([lo, hi, k1, k2])

    def to_b(i: int, end: bool) -> int:
        """A position of `a` in `b`: inside a block, or at the edge of one; a start edge takes the block it opens, an
        end edge the block it closes, so a run only `b` has stays outside the hunk."""
        for ai, bj, n in blocks:
            if (ai < i <= ai + n) if end else (ai <= i < ai + n):
                return bj + i - ai
        for ai, bj, n in blocks:
            if ai <= i <= ai + n:
                return bj + i - ai
        return len(b)

    out: list[str] = []
    pos = 0
    for lo, hi, k1, k2 in hunks:
        j1, j2 = to_b(lo, False), to_b(hi, True)
        if hi == lo:
            j2 = j1
        j1 = max(j1, pos)
        j2 = max(j2, j1)
        out.extend(b[pos:j1])
        kept = [b[j] for j in range(j1, j2) if j in comments]
        out.extend(c[k1:k2])
        if kept:
            if out and out[-1] != "":
                out.append("")
            out.extend(kept)
            if j2 < len(b) and b[j2] != "":
                out.append("")
        pos = j2
    out.extend(b[pos:])
    return "\n".join(out)


# The footer (PT-031, built by PT-034): three paragraphs at the end of both the file and the Doc, the time of the
# last sync that wrote that side, the file's path from the repository root as a code span, the Doc's link. Stripped
# from both sides before they are compared or merged, written after; `--no-footer` on a writing command turns it
# off, and the state file remembers.

FOOTER_MARK = "md2gdoc sync last change: "


def split_footer(text: str) -> tuple[str, list[str] | None]:
    """The text without its footer, and the footer's three lines, or None when the text holds no footer. The footer
    is the last line starting with the mark whose next two non-blank lines are a path (a code span, or bare since a
    Doc may lose the span, then a file name with its dot or a folder's slash) and a link, wherever it sits; lines
    appended after it (a task line `chadkit task add` wrote) stay body, so the next write moves the footer back to the
    end."""
    lines = text.rstrip("\n").split("\n")
    kept = [i for i, line in enumerate(lines) if line.strip()]
    for n in range(len(kept) - 3, -1, -1):
        first, path, link = (lines[i] for i in kept[n:n + 3])
        span = path.startswith("`") and path.endswith("`")
        if first.startswith(FOOTER_MARK) and (span or "." in path or "/" in path) and link.startswith("http"):
            body = lines[:kept[n]] + lines[kept[n + 2] + 1:]
            while body and body[-1] == "":
                body.pop()
            while len(body) > 1 and body[-1] == "" and body[-2] == "":
                body.pop()
            return "\n".join(body) + "\n", [first, path, link]
    return text, None


def with_footer(body: str, footer: list[str] | None) -> str:
    if footer is None:
        return body
    return (body + "\n" if body.strip() else "") + "\n\n".join(footer) + "\n"


def footer_now(md: Path, link: str) -> list[str]:
    now = datetime.datetime.now().astimezone()
    when = f"{now:%Y-%m-%d %I:%M}{now.strftime('%p').lower()} {now.tzname() or ''}".rstrip()
    return [FOOTER_MARK + when, f"`{repo_path(md)}`", link]  # a span, so a `_` in the path is never italics


def repo_path(md: Path) -> str:
    """The file's path from the repository root, so the footer reads the same in every clone; the path as given
    outside a repository."""
    full = md.resolve()
    for parent in [full.parent, *full.parent.parents]:
        if (parent / ".git").exists():
            return full.relative_to(parent).as_posix()
    return md.as_posix()


def footer_wanted(args, state: dict, md: Path | None = None) -> bool:
    """Whether this file carries the footer: off once `--no-footer` was given, which the state file remembers, from
    that command on even when it writes nothing else."""
    if getattr(args, "no_footer", False) and state.get("footer", True):
        state["footer"] = False
        if md is not None and state_path(md).exists():
            save_state(md, state)
    return state.get("footer", True)


def footer_for(want: bool, *present: list[str] | None, md: Path, link: str, fresh: bool) -> list[str] | None:
    """The footer a side gets: none when off; new when a body was written (`fresh`); else the footer a side already
    has, so an in-sync run adds a missing footer without changing the other side's time."""
    if not want:
        return None
    if not fresh:
        for footer in present:
            if footer is not None:
                return footer
    return footer_now(md, link)


# ---- Targeted edits (PT-009, PD-001 option C'): a push edits the Doc's paragraphs when it can, replaces it when
# it cannot, and carries the comments over a replace. The rules are measured in chadkit/work/PT-009.md.

_HEADING_LINE = re.compile(r"^(#{1,6}) (.+)$")
_ITEM_LINE = re.compile(r"^((?:    )*)([-*+]|\d+[.)]) (?:\[([ xX])\] )?(.*)$")
_INTRAWORD = re.compile(r"\w")
_HOLD = re.compile(r"&#?\w+;|<[\w/!]|!\[")  # an entity, a tag or autolink, an image: not written by the edit path
_RESET = "bold,italic,strikethrough,underline,weightedFontFamily,foregroundColor,backgroundColor,link"
_LINK_COLOR = {"color": {"rgbColor": {"red": 0.06666667, "green": 0.33333334, "blue": 0.8}}}
_MONO = {"fontFamily": "Roboto Mono", "weight": 400}
_PRESETS = {"box": "BULLET_CHECKBOX"}


class Fallback(Exception):
    """The edit path cannot write this diff; the one argument names why, a word the output carries."""


def _u16(s: str) -> int:
    """Length in UTF-16 code units, the unit of every Docs API index."""
    return len(s.encode("utf-16-le")) // 2


def inline(md: str) -> tuple[str, list[tuple[int, int, dict]]]:
    """A line's plain text and its styled spans, (start, end, textStyle) in characters, from the inline syntax the
    edit path writes: code spans, `**bold**`, `*italic*`, `~~struck~~`, `[text](url)` and escapes. Anything else
    raises Fallback("inline")."""
    plain: list[str] = []
    spans: list[tuple[int, int, dict]] = []
    open_: dict[str, int] = {}
    pos, n = 0, len(md)

    def at() -> int:
        return sum(len(p) for p in plain)

    while pos < n:
        c = md[pos]
        if c == "\\" and pos + 1 < n:
            plain.append(md[pos + 1])
            pos += 2
        elif c == "`":
            m = _SPAN.match(md, pos)
            if not m:
                raise Fallback("inline")
            start = at()
            plain.append(m.group(2).strip(" ") if m.group(2).strip(" ") else m.group(2))
            spans.append((start, at(), {"weightedFontFamily": _MONO}))
            pos = m.end()
        elif md.startswith(("**", "~~"), pos) or c == "*":
            tok = md[pos:pos + 2] if md.startswith(("**", "~~"), pos) else "*"
            style = {"**": "bold", "*": "italic", "~~": "strikethrough"}[tok]
            if style in open_:
                spans.append((open_.pop(style), at(), {style: True}))
            else:
                open_[style] = at()
            pos += len(tok)
        elif c == "_":
            if not (pos > 0 and _INTRAWORD.match(md[pos - 1]) and pos + 1 < n and _INTRAWORD.match(md[pos + 1])):
                raise Fallback("inline")
            plain.append(c)
            pos += 1
        elif c == "[":
            close = md.find("]", pos)
            if close > pos and close + 1 < n and md[close + 1] == "(":
                end = md.find(")", close)
                url = md[close + 2:end] if end > close else ""
                text = md[pos + 1:close]
                if not url or " " in url or any(ch in text for ch in "`*[]~\\"):
                    raise Fallback("inline")
                start = at()
                plain.append(text)
                spans.append((start, at(), {"link": {"url": url}, "underline": True, "foregroundColor": _LINK_COLOR}))
                pos = end + 1
            else:
                plain.append(c)
                pos += 1
        elif c in "&<!" and _HOLD.match(md, pos):
            raise Fallback("inline")
        else:
            plain.append(c)
            pos += 1
    if open_:
        raise Fallback("inline")
    return "".join(plain), spans


class Line:
    """One normalized line read for the edit path: its kind and the parts the Doc holds separately."""

    def __init__(self, text: str):
        self.text = text
        self.kind, self.level, self.marker, self.state, self.heading = "para", 0, "", "", 0
        body = text
        if text == "":
            self.kind = "blank"
        elif m := _HEADING_LINE.match(text):
            self.kind, self.heading, body = "heading", len(m.group(1)), m.group(2)
        elif m := _ITEM_LINE.match(text):
            self.kind, self.level, body = "item", len(m.group(1)) // 4, m.group(4)
            self.marker, self.state = m.group(2), (m.group(3) or "").lower()
            self.list = "box" if m.group(3) is not None else "ordered" if m.group(2)[0].isdigit() else "bullet"
            if self.list == "ordered":
                self.marker = m.group(2)[-1]  # the Doc numbers the items itself; only `.` against `)` matters
        elif text.startswith((" ", "\t", ">", "|", "```", "~~~", "---", "***", "<", "![", "[^", "=")):
            self.kind = "other"
        self.body = body

    def rendered(self) -> tuple[str, list[tuple[int, int, dict]]]:
        return inline(self.body)


class Para:
    """One body paragraph of `documents.get`, with what the mapping compares."""

    def __init__(self, el: dict, lists: dict):
        p = el["paragraph"]
        self.start, self.end = el["startIndex"], el["endIndex"]
        runs = []
        for e in p["elements"]:
            if "textRun" not in e:
                raise Fallback("structure")
            r = e["textRun"]
            if r.get("suggestedInsertionIds") or r.get("suggestedDeletionIds"):
                raise Fallback("suggestion")
            runs.append(r["content"])
        self.plain = "".join(runs)[:-1]
        if "\u000b" in self.plain:
            raise Fallback("structure")
        style = p.get("paragraphStyle", {})
        named = style.get("namedStyleType", "NORMAL_TEXT")
        self.heading = int(named[-1]) if named.startswith("HEADING_") else 0
        if not self.heading and named != "NORMAL_TEXT":
            raise Fallback("structure")
        bullet = p.get("bullet")
        self.list, self.level = "", 0
        if bullet:
            self.level = bullet.get("nestingLevel", 0)
            glyph = lists[bullet["listId"]]["listProperties"]["nestingLevels"][self.level]
            kind = glyph.get("glyphType", "GLYPH_TYPE_UNSPECIFIED")
            self.list = "bullet" if glyph.get("glyphSymbol") else "box" if kind == "GLYPH_TYPE_UNSPECIFIED" \
                else "ordered"
        elif style.get("indentStart", {}).get("magnitude"):
            raise Fallback("structure")
        self.line: Line | None = None  # the normalized line this paragraph maps to

    @property
    def kind(self) -> str:
        return "item" if self.list else "heading" if self.heading else "para" if self.plain else "blank"


def _paragraphs(doc: dict) -> list[Para]:
    """The body's paragraphs in order, an empty one a blank line; a table or a second section is a Fallback."""
    out: list[Para] = []
    for i, el in enumerate(doc["body"]["content"]):
        if "paragraph" in el:
            out.append(Para(el, doc.get("lists", {})))
        elif "sectionBreak" not in el or i:
            raise Fallback("structure")
    return out


def _lines(text: str) -> list[Line]:
    """The lines as the Doc holds them: a blank line is an empty paragraph, except the one the export writes on each
    side of a heading, which no paragraph holds. Checked for a layout the edit path can place: two prose lines in a
    row would be one paragraph, a blank between list items makes the list loose, two kinds of list side by side are
    unmeasured."""
    lines = [Line(raw) for raw in text.rstrip("\n").split("\n")]
    out: list[Line] = []
    for i, line in enumerate(lines):
        if line.kind == "other":
            raise Fallback("structure")
        if line.kind == "blank" and ((i and lines[i - 1].kind == "heading")
                                     or (i + 1 < len(lines) and lines[i + 1].kind == "heading")):
            continue
        out.append(line)
    for prev, line in zip(out, out[1:]):
        if line.kind == "para" and prev.kind in ("para", "item"):
            raise Fallback("layout")
        if line.kind == "item" and prev.kind == "item" and prev.list != line.list and line.level == prev.level:
            raise Fallback("layout")
    for a, b, c in zip(out, out[1:], out[2:]):
        if b.kind == "blank" and a.kind == c.kind == "item":
            raise Fallback("blank")
    return out


def _check(para: Para, line: Line) -> None:
    """The paragraph holds this line: same kind, level, heading and plain text, else the mapping is off."""
    if (para.kind, para.level, para.heading) != (line.kind, line.level, line.heading):
        raise Fallback("mapping")
    if line.kind == "item" and para.list != line.list:
        raise Fallback("mapping")
    if para.plain != line.rendered()[0]:
        raise Fallback("mapping")


def _styles(start: int, plain: str, spans: list[tuple[int, int, dict]]) -> list[dict]:
    """Reset every text style over the paragraph's text, then set each span's; indexes from `start`."""
    if not plain:
        return []
    out = [{"updateTextStyle": {"range": {"startIndex": start, "endIndex": start + _u16(plain)}, "textStyle": {},
                                "fields": _RESET}}]
    for a, b, style in spans:
        if b > a:
            out.append({"updateTextStyle": {"range": {"startIndex": start + _u16(plain[:a]),
                                                      "endIndex": start + _u16(plain[:b])},
                                            "textStyle": style, "fields": ",".join(style)}})
    return out


def _named(start: int, end: int, heading: int) -> dict:
    return {"updateParagraphStyle": {"range": {"startIndex": start, "endIndex": end},
                                     "paragraphStyle": {"namedStyleType": f"HEADING_{heading}" if heading
                                                        else "NORMAL_TEXT"}, "fields": "namedStyleType"}}


def _edit(para: Para, line: Line) -> list[dict]:
    """Rewrite one paragraph to hold `line`: the smallest text change, every style set again, the kind fixed up."""
    old = para.line
    assert old is not None
    if line.kind == "item":
        if old.kind != "item" or (old.list, old.level, old.marker) != (line.list, line.level, line.marker):
            raise Fallback("list")
        if old.state != line.state:
            raise Fallback("tick")
    elif old.kind == "item" and line.kind == "heading":
        raise Fallback("list")
    if line.level:
        raise Fallback("nesting")
    plain, spans = line.rendered()
    before = para.plain
    i = 0
    while i < min(len(before), len(plain)) and before[i] == plain[i]:
        i += 1
    j = 0
    while j < min(len(before), len(plain)) - i and before[-1 - j] == plain[-1 - j]:
        j += 1
    reqs: list[dict] = []
    at = para.start + _u16(before[:i])
    if before[i:len(before) - j]:
        reqs.append({"deleteContentRange": {"range": {"startIndex": at,
                                                      "endIndex": at + _u16(before[i:len(before) - j])}}})
    if plain[i:len(plain) - j]:
        reqs.append({"insertText": {"location": {"index": at}, "text": plain[i:len(plain) - j]}})
    reqs.extend(_styles(para.start, plain, spans))
    end = para.start + _u16(plain) + 1
    if line.kind != "item":
        if old.kind == "item":
            reqs.append({"deleteParagraphBullets": {"range": {"startIndex": para.start, "endIndex": end}}})
        if old.heading != line.heading or old.kind == "item":
            reqs.append(_named(para.start, end, line.heading))
    return reqs


def _insert(lines: list[Line], at: int, after: bool, anchor: Para) -> list[dict]:
    """New paragraphs beside `anchor`: after it (at its text's end) or before it (at its start). Each inherits the
    anchor's style and bullet, so each is reset and fixed up; a list item is written only where it inherits a
    bullet of its own kind, a checkbox also fresh."""
    reqs: list[dict] = []
    for line in reversed(lines):  # each insert at the same point, so the last line goes in first
        if line.level:
            raise Fallback("nesting")
        plain, spans = line.rendered()
        inherits = anchor.kind == "item"
        if line.kind == "item":
            if anchor.level:
                raise Fallback("nesting")
            if line.state == "x":
                raise Fallback("tick")
            if inherits and anchor.line is not None and (anchor.line.list, anchor.line.marker) != (line.list,
                                                                                                    line.marker):
                raise Fallback("list")
            if not inherits and line.list not in _PRESETS:
                raise Fallback("list")
        start = at + 1 if after else at
        reqs.append({"insertText": {"location": {"index": at}, "text": "\n" + plain if after else plain + "\n"}})
        reqs.extend(_styles(start, plain, spans))
        end = start + _u16(plain) + 1
        if line.kind != "item":
            if inherits:
                reqs.append({"deleteParagraphBullets": {"range": {"startIndex": start, "endIndex": end}}})
            if anchor.heading != line.heading:
                reqs.append(_named(start, end, line.heading))
        elif not inherits:
            if anchor.heading:
                reqs.append(_named(start, end, 0))
            reqs.append({"createParagraphBullets": {"range": {"startIndex": start, "endIndex": end},
                                                    "bulletPreset": _PRESETS[line.list]}})
    return reqs


def plan_edits(doc: dict, old_text: str, new_text: str) -> list[dict]:
    """The batchUpdate requests that turn the Doc, whose normalized export is `old_text`, into `new_text`; raises
    Fallback when the whole replace must do it. Hunks are written from the end of the Doc backwards, so no index
    moves under a later request."""
    import difflib

    paras = _paragraphs(doc)
    old, new = _lines(old_text), _lines(new_text)
    if len(paras) != len(old):
        raise Fallback("mapping")
    for para, line in zip(paras, old):
        _check(para, line)
        para.line = line
    reqs: list[dict] = []
    ops = difflib.SequenceMatcher(None, [l.text for l in old], [l.text for l in new], autojunk=False).get_opcodes()
    for tag, i1, i2, j1, j2 in reversed(ops):
        if tag == "equal":
            continue
        pairs = min(i2 - i1, j2 - j1)
        if j2 - j1 > pairs:  # more new lines than paragraphs: the extras go in first, after the last paragraph kept
            extra = new[j1 + pairs:j2]
            if pairs or i1:
                anchor = paras[i1 + pairs - 1]
                reqs.extend(_insert(extra, anchor.end - 1, True, anchor))
            else:
                reqs.extend(_insert(extra, paras[0].start, False, paras[0]))
        elif i2 - i1 > pairs:  # paragraphs with no line left: one range, through the previous newline at the end
            first, last = paras[i1 + pairs], paras[i2 - 1]
            if last is paras[-1]:
                if first is paras[0]:
                    raise Fallback("structure")
                reqs.append({"deleteContentRange": {"range": {"startIndex": paras[i1 + pairs - 1].end - 1,
                                                              "endIndex": last.end - 1}}})
            else:
                reqs.append({"deleteContentRange": {"range": {"startIndex": first.start, "endIndex": last.end}}})
        for k in reversed(range(pairs)):
            reqs.extend(_edit(paras[i1 + k], new[j1 + k]))
    return reqs


def _body(body: dict) -> list[tuple[int, int, str]]:
    """(start, end, text) per body paragraph, the text as wide as the indexes: an element that is not a text run
    (an image, a rule, a footnote mark) stands in as one placeholder per index it takes."""
    out = []
    for el in body["content"]:
        if "paragraph" in el:
            text = "".join(e["textRun"]["content"] if "textRun" in e else "\ufffc" * (e["endIndex"] - e["startIndex"])
                           for e in el["paragraph"]["elements"])
            out.append((el["startIndex"], el["endIndex"], text))
    return out


def anchored_comments(resp: dict) -> list[dict]:
    """The open comments of a `documents.get` with comments: author, content, replies, the anchored text, the plain
    text of the paragraph it starts in and its offset there, so a carry-over can find the place again."""
    tab = resp["tabs"][0]["documentTab"]
    anchors = tab.get("commentAnchors", {})
    paras = _body(tab["body"])
    out = []
    for c in resp.get("comments", []):
        if c.get("status", "OPEN") != "OPEN":
            continue
        a = anchors.get(c.get("anchorId", ""))
        r = a["ranges"][0] if a and a.get("ranges") else None
        para = next(((s, t) for s, e, t in paras if r and s <= r["startIndex"] < e), None)
        text = offset = None
        if r and para:
            offset = r["startIndex"] - para[0]
            text = "".join(t for _, _, t in paras)[r["startIndex"] - paras[0][0]:r["endIndex"] - paras[0][0]]
        out.append({"id": c["commentId"], "author": c["headPost"]["author"].get("displayName", "?"),
                    "content": c["headPost"]["content"], "anchored": text,
                    "para": para[1][:-1] if para else None, "offset": offset,
                    "replies": [(p["author"].get("displayName", "?"), p["content"]) for p in c.get("replies", [])]})
    return out


def _place(doc: dict, c: dict) -> tuple[int, int] | None:
    """Where a carried comment goes in the replaced Doc: its text at the same offset of the paragraph that held it,
    else elsewhere in that paragraph, else the one place its text occurs; None when the push changed that text."""
    paras = _body(doc["body"])
    text = c["anchored"]
    if not text:
        return None
    for start, _, plain in paras:
        if plain[:-1] == c["para"]:
            i = c["offset"] if plain.startswith(text, c["offset"]) else plain.find(text)
            if i >= 0:
                return start + i, start + i + len(text)
    body = "".join(t for _, _, t in paras)
    if body.count(text) == 1:
        i = body.index(text)
        return paras[0][0] + i, paras[0][0] + i + len(text)
    return None


def carry_comments(d, doc_id: str, comments: list[dict]) -> dict:
    """After a whole replace: each comment read before it is written again at its text, its replies after it, and
    the orphan deleted; written by the token's user, who names the author. Counts for the output."""
    out = {"carried": 0, "unplaced": [], "undeleted": 0}
    if not comments:
        return out
    doc = d.get_doc(doc_id)
    for c in comments:
        place = _place(doc, c)
        if place is None:
            out["unplaced"].append(c["anchored"] or c["content"][:40])
            continue
        new_id = d.insert_comment(doc_id, place[0], place[1],
                                  f"{c['content']}\n\n(carried over a sync; by {c['author']})")
        for author, content in c["replies"]:
            d.reply(doc_id, new_id, f"{content}\n\n(carried over a sync; by {author})")
        try:
            d.delete_comment(doc_id, c["id"])
        except Exception:  # another user's comment: Google refuses, the orphan stays listed
            out["undeleted"] += 1
        out["carried"] += 1
    return out


def docs_api_off(e: Exception) -> bool:
    """Google's 403 for a Cloud project where the Docs API is not enabled."""
    return getattr(getattr(e, "resp", None), "status", None) == 403 and any(
        word in str(e) for word in ("accessNotConfigured", "SERVICE_DISABLED", "has not been used"))


def pending_suggestions(doc: dict) -> set[str]:
    """The ids of the suggestions pending in a `documents.get`: every `suggested...` key names them, as one id (a
    list's or an inline object's `suggestedInsertionId`), a list of ids or a map keyed by id, wherever it sits (a
    run, a paragraph's style or bullet, a table cell, the document style). The markdown export cannot tell a
    suggestion from the text, so a pull must look here first."""
    ids: set[str] = set()

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key.startswith("suggested") and value:
                    if isinstance(value, str):
                        ids.add(value)
                    else:
                        ids.update(value)  # the keys of a map, the items of a list
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(doc)
    return ids


def write_doc(d, doc_id: str, old_text: str, text: str) -> dict:
    """Push `text` over a Doc whose normalized export is `old_text`: by edits when `plan_edits` can, else by the
    whole replace with the comments carried over. Returns what `--json` and the prose report."""
    try:
        doc = d.get_doc(doc_id)
        reqs = plan_edits(doc, old_text, normalize(text))
    except Fallback as e:
        why = e.args[0]
    except Exception as e:  # the Docs API not enabled in the Cloud project: the push as before PT-009
        if not docs_api_off(e):
            raise
        why = "docs_api"
    else:
        d.batch_update(doc_id, reqs, doc.get("revisionId"))
        return {"write": "edits", "requests": len(reqs)}
    comments = anchored_comments(d.get_doc(doc_id, comments=True)) if why != "docs_api" else []
    d.update(doc_id, push_form(text))
    return {"write": "replace", "why": why, **carry_comments(d, doc_id, comments)}


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
  init FILE --doc ID  attach FILE, new or empty, to the Doc with id ID (the /d/ID/ part of its link): write
                 its text to FILE and the state file; a Doc the script did not make needs a `--scope drive`
                 profile; refused with --name or --folder, or when FILE holds text
  pull FILE      export the Doc, undo the converter's noise, carry the Doc's changes onto FILE, which keeps
                 its own shape and its HTML comments away from the changed lines; refused when FILE changed
                 since the last sync; --force writes the Doc's text as it is, changed or not; refused while
                 the Doc holds a pending suggestion, which
                 the export cannot tell from the text (sync and init --doc refuse it too; a dry run of init
                 makes no call)
  push FILE      write FILE's changes to the Doc; refused when the Doc changed since the last sync. Changed
                 lines are edited in place through the Docs API, so comments and formatting elsewhere stay;
                 a diff that ticks a box, nests a list, or touches a table, code, an image or a rule replaces
                 the whole Doc, and the comments are written again at their text, by you, naming each author
  sync FILE      merge both sides' changes since the last sync, write FILE, push the Doc; a line changed
                 differently on both sides is written to FILE between <<<<<<< api-edited (FILE's version) and
                 >>>>>>> hand-edited (the Doc's), nothing is pushed, and the exit code is 2; refused while
                 the Doc holds a pending suggestion, like pull
  status FILE    which side changed since the last sync
  --no-footer    on init, pull, push, sync: no footer; by default every synced file and its Doc end with three
                 paragraphs, `md2gdoc sync last change: 2026-10-30 09:43am PDT` (this machine's clock and
                 zone), FILE's path from the repository root in backticks, and the Doc's link, refreshed by
                 whichever command writes that side and never read as a change; remembered in the state
                 file, so one --no-footer is enough
  --dry-run      on any command: say what would happen, change nothing (status: local side only, no network)
  --json         on any command: one JSON object on stdout and nothing else: command, file, exit, reason (a
                 fixed word: created, attached, pulled, pushed, synced, status, in_sync, nothing_to_push,
                 conflict, markers, refused_doc_changed, refused_file_changed, refused_suggestions, error),
                 message (the prose), and per command written, pushed, conflicts, version, link, the diffs,
                 suggestions and warnings, write (edits or replace, with requests, or why and the comments
                 carried); for agents (docs/agents.md)
  --account NAME on any command: the profile to use (default: $MD2GDOC_ACCOUNT, else `default`)
  --scope NAME   on any command: `drive.file` (default) or `drive`; chosen at a profile's first login, then
                 remembered in its token

setup (once per profile; the full walkthrough is docs/setup.md at github.com/chadn/md2gdoc):
  1. a Google Cloud project with the Drive API and the Google Docs API enabled and an OAuth consent screen, scope
     https://www.googleapis.com/auth/drive.file only (.../auth/drive for a `--scope drive` profile),
     published (In production)
  2. an OAuth client of type Desktop app, its JSON saved as {CLIENT_FILE} in the profile's folder (below)
  3. the first command that needs Google opens a browser once; the token is cached and refreshes itself
  The script sees only the Docs it created (drive.file): let `init` make each Doc. To sync a Doc made by
  hand, a second profile with `--scope drive`, best under a Google account that holds little else.
  Run: `uv run --script md2gdoc.py ...`; or `uv tool install git+https://github.com/chadn/md2gdoc` once and
  `md2gdoc ...`; or `pip install google-api-python-client google-auth-oauthlib google-auth-httplib2` once and
  `python md2gdoc.py ...`.

files:
  FILE{STATE_SUFFIX}       the state file next to FILE: Doc id, link, Drive version, the normalized snapshot of
                       what the Doc held after the last sync and of what FILE held (the merge base), and
                       `footer: false` after --no-footer; commit it, so a clone syncs the same Doc
  <config>/NAME/       one folder per profile, NAME the account name, holding that profile's {CLIENT_FILE}
                       (the OAuth client, from a Cloud project under that Google account) and {TOKEN_FILE} (the
                       cached token, which remembers the scope); neither is ever in a repository
  <config>             $MD2GDOC_CONFIG_DIR; else on Windows %APPDATA%\\md2gdoc; else $XDG_CONFIG_HOME/md2gdoc,
                       else ~/.config/md2gdoc

exit codes:
  0  done            1  usage, setup, or Google error
  2  conflict: both sides changed one line (sync), or FILE still holds conflict markers (sync, push)
  3  refused: push when the Doc changed since the last sync, pull when FILE did (sync, or pull --force);
     sync when the Doc changed between its export and its push (run it again); pull, sync and init --doc
     while the Doc holds a pending suggestion (accept or reject it in the Doc)
"""


def state_path(md: Path) -> Path:
    return md.with_name(md.name + STATE_SUFFIX)


def load_state(md: Path) -> dict:
    path = state_path(md)
    if not path.exists():
        raise SystemExit(f"md2gdoc: no state file {path}; run `init {md}` first")
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(md: Path, state: dict) -> None:
    # newline="\n" on every platform, so a Windows checkout does not rewrite a committed file with CRLF
    state_path(md).write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def read_md(md: Path) -> str:
    r"""The file's text with `\n` line endings, whatever the file uses; `write_md` restores CRLF when it had it."""
    if not md.is_file():
        raise SystemExit(f"md2gdoc: {md} is not a file")
    return md.read_text(encoding="utf-8")  # universal newlines: CRLF read as \n


def write_md(md: Path, text: str) -> None:
    """Write the file with the line endings it had: CRLF when a CRLF is in it today, else LF, on every platform."""
    crlf = md.is_file() and b"\r\n" in md.read_bytes()
    md.write_text(text, encoding="utf-8", newline="\r\n" if crlf else "\n")


def diff(a: str, b: str, a_name: str, b_name: str) -> str:
    return "".join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), a_name, b_name))


class Drive:
    """The Drive calls the commands make, and the Docs API calls of the edit path; tests pass a fake with the same
    methods."""

    def __init__(self, creds):
        from googleapiclient.discovery import build  # lazy: the text layer runs without the libraries

        self.api = build("drive", "v3", credentials=creds, cache_discovery=False)
        self.docs = build("docs", "v1", credentials=creds, cache_discovery=False)

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

    def get_doc(self, doc_id: str, comments: bool = False) -> dict:
        """The document JSON; with `comments`, the tabs form that carries the comment threads and their anchors (the
        API wants the three parameters together)."""
        if not comments:  # the view named, since the default for a profile that cannot edit the Doc hides suggestions
            return self.docs.documents().get(documentId=doc_id, suggestionsViewMode="SUGGESTIONS_INLINE").execute()
        return self.docs.documents().get(documentId=doc_id, includeTabsContent=True,
                                         suggestionsViewMode="SUGGESTIONS_INLINE",
                                         commentsViewMode="COMMENTS_VIEW_MODE_INCLUDED").execute()

    def batch_update(self, doc_id: str, requests: list[dict], revision_id: str | None = None) -> dict:
        """One `batchUpdate`; with `revision_id`, refused by Google (400) when the Doc moved since that read."""
        body: dict = {"requests": requests}
        if revision_id:
            body["writeControl"] = {"requiredRevisionId": revision_id}
        return self.docs.documents().batchUpdate(documentId=doc_id, body=body).execute()

    def insert_comment(self, doc_id: str, start: int, end: int, content: str) -> str:
        r = self.batch_update(doc_id, [{"insertComment": {"content": content,
                                                          "range": {"startIndex": start, "endIndex": end}}}])
        return r["replies"][0]["insertComment"]["commentThread"]["commentId"]

    def reply(self, doc_id: str, comment_id: str, content: str) -> None:
        self.batch_update(doc_id, [{"addCommentReply": {"commentId": comment_id, "post": {"content": content}}}])

    def delete_comment(self, doc_id: str, comment_id: str) -> None:
        self.batch_update(doc_id, [{"deleteComment": {"commentId": comment_id}}])

    def lookup(self, doc_id: str) -> dict:
        """The same fields `create` returns, for a Doc that exists (a `drive.file` token gets 404 notFound on one it did
        not make; the export `_attach` runs first gets 403 appNotAuthorizedToFile)."""
        f = self.api.files().get(fileId=doc_id, fields="id,webViewLink,version", supportsAllDrives=True).execute()
        return {"doc_id": f["id"], "link": f["webViewLink"], "version": int(f["version"])}


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


def _out(args, md: Path) -> dict:
    """The one object `--json` prints; the prose commands fill the same fields and print lines instead."""
    return {"command": args.command, "file": str(md), "dry_run": bool(args.dry_run)}


def _finish(args, out: dict, code: int, reason: str, *, lines=(), errors=(), **fields) -> int:
    """Print the result and return the exit code: prose lines (stdout, then stderr), or with `--json` one object
    holding `exit`, `reason`, `message` (the prose joined) and every field a command recorded."""
    warnings = out.get("warnings", [])
    out.update(fields, exit=code, reason=reason, message="\n".join([*warnings, *errors, *lines]))
    if args.json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        for line in [*warnings, *errors]:  # first, as before: a warning sits above the line it qualifies
            print(line, file=sys.stderr)
        for line in lines:
            print(line)
    return code


def error_object(message: str, argv: list[str]) -> dict:
    """The `--json` object for an error raised as a message, from the arguments as given: the command is the first
    word that is not a flag, the file the second, since the parser may not have accepted them."""
    words = [a for a in argv if not a.startswith("-")]
    return {"command": words[0] if words else None, "file": str(Path(words[1])) if len(words) > 1 else None,
            "dry_run": "--dry-run" in argv, "exit": EXIT_ERROR, "reason": "error", "message": message}


def cmd_init(args, drive) -> int:
    md = Path(args.file)
    out = _out(args, md)
    if state_path(md).exists():
        raise SystemExit(f"md2gdoc: {state_path(md)} exists; this file already has a Doc")
    if args.doc:
        return _attach(args, out, md, drive)
    text = read_md(md)
    name = args.name or md.stem
    if args.dry_run:
        return _finish(args, out, EXIT_OK, "created", name=name, lines=[
            f"would create Doc {name!r} from {md} ({len(text.splitlines())} lines) and write {state_path(md)}"])
    d = drive(args.account, args.scope)
    state = {}
    want = footer_wanted(args, state)
    body, _ = split_footer(normalize(text))
    state.update(d.create(name, push_form(doc_view(body)), args.folder))
    footer = footer_for(want, md=md, link=state["link"], fresh=True)
    if footer is not None:  # the file gets its footer, and the Doc, which the create could not name, gets it by edits
        raw, _ = split_footer(text)
        write_md(md, with_footer(raw if raw.endswith("\n") else raw + "\n", footer))
        doc_full = normalize(d.export(state["doc_id"]), body)
        write_doc(d, state["doc_id"], doc_full, with_footer(doc_full, footer))
    return _record(args, out, md, body, doc_view(body), state, d, "created")


def _attach(args, out: dict, md: Path, drive) -> int:
    """`init --doc`: the state file for a Doc that already exists, and its text into FILE, as a first pull."""
    if args.name or args.folder:
        raise SystemExit("md2gdoc: --doc attaches a Doc that exists; --name and --folder are for creating one")
    if md.is_file() and read_md(md).strip():
        raise SystemExit(f"md2gdoc: {md} exists and is not empty; init --doc writes the Doc's text into a new or "
                         f"empty FILE")
    out.update(doc_id=args.doc)
    if args.dry_run:
        return _finish(args, out, EXIT_OK, "attached", written=False, lines=[
            f"would write {md} from Doc {args.doc} and write {state_path(md)}"])
    d = drive(args.account, args.scope)
    new = normalize(d.export(args.doc))  # first, for its error on a Doc the app may not open (setup.md, PT-022)
    if (code := suggestions_held(args, out, d, args.doc, "init")) is not None:
        return code
    state = d.lookup(args.doc)
    want = footer_wanted(args, state)
    body, doc_footer = split_footer(new)
    footer = footer_for(want, doc_footer, md=md, link=state["link"], fresh=doc_footer is None)
    write_md(md, with_footer(body, footer))  # the Doc, a first pull's source, is not written; its first push adds one
    state.update(snapshot=body, local=body)
    save_state(md, state)
    return _finish(args, out, EXIT_OK, "attached", written=True, link=state["link"], version=state["version"],
                   lines=[f"attached {md} to {state['link']}"])


UNCHECKED = "the Doc was not checked for pending suggestions, which its export cannot tell from its text: {}"
NO_DOCS_API = "the Docs API is not enabled in the Cloud project (docs/setup.md)"
NO_RIGHT = "this profile's access to the Doc shows none (Google refused the view that would, as for a viewer)"


def suggestions_held(args, out: dict, d, doc_id: str, verb: str) -> int | None:
    """Before `pull`, `sync` or `init --doc` writes the Doc's export: how many suggestions are pending in it, through
    the Docs API, since the export cannot tell one from the text. With any, the exit code the command returns, after
    the refusal is printed; else None, with `out["suggestions"]` the count, or null and a warning when the Doc
    cannot be read that way: the Docs API not enabled, or a profile that may only view the Doc, to which Google
    refuses the view that shows suggestions (403, per the SuggestionsViewMode reference; not measured)."""
    try:
        held = len(pending_suggestions(d.get_doc(doc_id)))
    except Exception as e:
        if docs_api_off(e):
            reason = NO_DOCS_API
        elif getattr(getattr(e, "resp", None), "status", None) == 403:
            reason = NO_RIGHT
        else:
            raise
        out["suggestions"], out["warnings"] = None, [UNCHECKED.format(reason)]
        return None
    out["suggestions"] = held
    if not held:
        return None
    return _finish(args, out, EXIT_MOVED, "refused_suggestions", errors=[
        f"{verb} refused: the Doc holds {held} pending suggestion{'s' if held > 1 else ''}, which its export "
        f"cannot tell from its text; accept or reject {'them' if held > 1 else 'it'} in the Doc, then run again"])


def cmd_pull(args, drive) -> int:
    md = Path(args.file)
    out = _out(args, md)
    state = load_state(md)
    text = read_md(md) if md.is_file() else ""
    local, file_footer = split_footer(normalize(text))
    want = footer_wanted(args, state, md)
    out.update(doc_id=state["doc_id"], link=state["link"])
    if local != state["local"] and not args.force and not args.dry_run:
        return _finish(args, out, EXIT_MOVED, "refused_file_changed", errors=[
            f"pull refused: {md} changed since the last sync; sync, or pull --force to overwrite it"])
    d = drive(args.account, args.scope)
    if (code := suggestions_held(args, out, d, state["doc_id"], "pull")) is not None:
        return code
    theirs, doc_footer = split_footer(normalize(d.export(state["doc_id"]), text))
    # The Doc's changes carried onto the file's form; with --force, the Doc's text as it is
    new = theirs if args.force else replay(state["snapshot"], theirs, state["local"])
    footer = footer_for(want, file_footer, doc_footer, md=md, link=state["link"], fresh=new != local)
    new_text = with_footer(new, footer)
    changes = diff(text, new_text, f"{md} (local)", f"{md} (Doc)")
    if args.dry_run:
        return _finish(args, out, EXIT_OK, "pulled", diff=changes, written=False,
                       lines=[changes or f"{md} already matches the Doc"])
    if new_text != text:
        write_md(md, new_text)
    state.update(version=d.version(state["doc_id"]), snapshot=theirs, local=new)
    save_state(md, state)
    return _finish(args, out, EXIT_OK, "pulled", written=new_text != text, version=state["version"],
                   lines=[f"pulled {md}: {'changed' if new_text != text else 'unchanged'}"])


def cmd_push(args, drive) -> int:
    md = Path(args.file)
    out = _out(args, md)
    state = load_state(md)
    text = read_md(md)
    out.update(doc_id=state["doc_id"], link=state["link"])
    if has_markers(text):
        return _finish(args, out, EXIT_CONFLICT, "markers", errors=[
            f"push refused: {md} holds conflict markers from the last sync; resolve them first"])
    local, _ = split_footer(normalize(text))
    want = footer_wanted(args, state, md)
    if local == state["local"]:
        return _finish(args, out, EXIT_OK, "nothing_to_push", pushed=False,
                       lines=[f"nothing to push: {md} matches the last sync"])
    d = drive(args.account, args.scope)
    # The guard exports and compares every time: a matching Drive version is not proof (design.md, item 2).
    doc_full = normalize(d.export(state["doc_id"]), text)
    theirs, doc_footer = split_footer(doc_full)
    if theirs != state["snapshot"]:
        return _finish(args, out, EXIT_MOVED, "refused_doc_changed", pushed=False, errors=[
            "push refused: the Doc changed since the last sync; pull or sync first"])
    if args.dry_run:
        changes = diff(state["local"], local, f"{md} (last sync)", f"{md} (local)")
        return _finish(args, out, EXIT_OK, "pushed", pushed=False, diff=changes, lines=[changes])
    new_doc = replay(doc_view(state["local"]), doc_view(local), theirs)
    footer = footer_for(want, md=md, link=state["link"], fresh=True)
    return _write(args, out, md, with_footer(new_doc, footer), local, state, d, doc_full, "pushed")


def cmd_status(args, drive) -> int:
    md = Path(args.file)
    out = _out(args, md)
    state = load_state(md)
    local = split_footer(normalize(read_md(md)))[0] if md.is_file() else ""
    out.update(doc_id=state["doc_id"], link=state["link"], local_changed=local != state["local"])
    lines = [f"{md}: {'changed' if out['local_changed'] else 'unchanged'} since the last sync"]
    if args.dry_run:
        return _finish(args, out, EXIT_OK, "status", lines=lines)
    d = drive(args.account, args.scope)
    doc_text = split_footer(normalize(d.export(state["doc_id"])))[0]
    version = d.version(state["doc_id"])
    out.update(doc_changed=doc_text != state["snapshot"], version=version, version_at_sync=state["version"])
    lines.append(f"Doc {state['link']}: {'changed' if out['doc_changed'] else 'unchanged'}"
                 f" (version {state['version']} -> {version})")
    return _finish(args, out, EXIT_OK, "status", lines=lines)


def cmd_sync(args, drive) -> int:
    md = Path(args.file)
    out = _out(args, md)
    state = load_state(md)
    text = read_md(md)
    out.update(doc_id=state["doc_id"], link=state["link"])
    if has_markers(text):
        return _finish(args, out, EXIT_CONFLICT, "markers", errors=[
            f"sync refused: {md} holds conflict markers from the last sync; resolve them first"])
    local, file_footer = split_footer(normalize(text))
    want = footer_wanted(args, state, md)
    d = drive(args.account, args.scope)
    if (code := suggestions_held(args, out, d, state["doc_id"], "sync")) is not None:
        return code
    doc_full = normalize(d.export(state["doc_id"]), text)
    theirs, doc_footer = split_footer(doc_full)
    version = d.version(state["doc_id"])
    file_changed, doc_changed = local != state["local"], theirs != state["snapshot"]
    footer_ok = (file_footer is None) == (not want)  # the Doc's footer moves with its next write for a change
    if not file_changed and not doc_changed and footer_ok:
        return _finish(args, out, EXIT_OK, "in_sync", written=False, pushed=False,
                       lines=[f"in sync: neither {md} nor the Doc changed since the last sync"])
    # The Doc's changes in the file's form, then the merge in that form; the two forms are never compared, so the
    # converter's own differences between the two texts of the last sync never read as a conflict.
    carried = replay(state["snapshot"], theirs, state["local"]) if doc_changed else state["local"]
    if not file_changed:
        merged, conflicts = carried, 0
    elif not doc_changed:
        merged, conflicts = local, 0
    else:
        merged, conflicts = merge3(state["local"], local, carried)
    footer = footer_for(want, file_footer, doc_footer, md=md, link=state["link"],
                        fresh=file_changed or doc_changed)
    if conflicts:
        changes = diff(local, merged, f"{md} (local)", f"{md} (merged, with markers)")
        if not args.dry_run:
            write_md(md, with_footer(merged, footer))
        return _finish(args, out, EXIT_CONFLICT, "conflict", conflicts=conflicts, written=not args.dry_run,
                       pushed=False, diff_file=changes, lines=[changes] if args.dry_run else [], errors=[
                           f"conflict: {conflicts} place{'s' if conflicts > 1 else ''} changed differently on both "
                           f"sides; {'would write' if args.dry_run else 'wrote'} both versions to {md} between "
                           f"<<<<<<< {OURS} and >>>>>>> {THEIRS}; nothing pushed"])
    new_doc = replay(doc_view(carried), doc_view(merged), theirs) if file_changed else theirs
    # The Doc is written for a change it would show, and takes or loses its footer then; never for the footer alone,
    # since a Doc-only change, a comment-only edit or an attached Doc would then write the Doc, by the whole replace
    # where a line forces it, with the comments that costs.
    doc_text = with_footer(new_doc, footer) if new_doc != theirs else doc_full
    if args.dry_run:
        diff_file = diff(with_footer(local, file_footer), with_footer(merged, footer), f"{md} (local)",
                         f"{md} (merged)")
        diff_doc = diff(doc_full, doc_text, f"{md} (Doc)", f"{md} (merged)")
        return _finish(args, out, EXIT_OK, "synced", written=False, pushed=False, diff_file=diff_file,
                       diff_doc=diff_doc, lines=[diff_file or f"{md} would not change",
                                                 diff_doc or "the Doc would not change"])
    file_text = with_footer(merged, footer)
    out["written"] = file_text != text
    if out["written"]:
        write_md(md, file_text)
    if doc_text == doc_full:
        state.update(version=version, snapshot=theirs, local=merged)
        save_state(md, state)
        return _finish(args, out, EXIT_OK, "synced", pushed=False, version=version,
                       lines=[f"synced {state['link']}: pulled, nothing to push"])
    # The push guard is a fresh export, as in push: the version is no proof of anything (design.md, item 2).
    if normalize(d.export(state["doc_id"]), text) != doc_full:
        return _finish(args, out, EXIT_MOVED, "refused_doc_changed", pushed=False, errors=[
            "push refused: the Doc changed while syncing; run sync again"])
    return _write(args, out, md, doc_text, merged, state, d, doc_full, "synced")


def _write(args, out: dict, md: Path, doc_text: str, body: str, state: dict, d: Drive, old_doc: str,
           verb: str) -> int:
    """The write of push and sync: edits when the diff allows, else the whole replace with the comments carried,
    then the record; `old_doc` is the Doc's normalized export the guard just compared, footer and all, `doc_text`
    what the Doc is to hold, and `body` the file's form the state keeps as `local`."""
    try:
        wrote = write_doc(d, state["doc_id"], old_doc, doc_text)
    except Exception as e:
        if "revision" not in str(e).lower():
            raise
        return _finish(args, out, EXIT_MOVED, "refused_doc_changed", pushed=False, errors=[
            f"{verb[:-2]} refused: the Doc changed while writing; run it again"])
    how = f"{wrote['requests']} edits" if wrote["write"] == "edits" else f"a whole replace ({wrote['why']})"
    if wrote.get("carried") or wrote.get("unplaced"):
        how += f", {wrote['carried']} comments carried"
        if wrote["unplaced"]:
            how += f", {len(wrote['unplaced'])} not placed (their text changed)"
    errors = [f"{len(wrote['unplaced'])} comments could not be carried; they stay in the Doc's comment list "
              f"without an anchor: {'; '.join(repr(t) for t in wrote['unplaced'])}"] if wrote.get("unplaced") else []
    return _record(args, out, md, body, split_footer(doc_text)[0], state, d, verb, how, errors, **wrote)


def _record(args, out: dict, md: Path, body: str, sent: str, state: dict, d: Drive, verb: str, how: str = "",
            errors: list[str] = (), **fields) -> int:
    """After a create or a write: export once more and store what the Doc now holds as the snapshot, beside the
    file's form `body` as `local`; the footer is in neither. `sent` is the text the Doc was given, so what the
    converter changed shows against it."""
    snapshot, _ = split_footer(normalize(d.export(state["doc_id"]), body))
    state.update(version=d.version(state["doc_id"]), snapshot=snapshot, local=body)
    save_state(md, state)
    lost = diff(sent, snapshot, f"{md} (sent)", f"{md} (Doc)")
    errors = [*errors] + ([f"the Doc holds a different text; `pull --force` would write it back (docs/features.md "
                           f"lists what the converter loses):\n{lost}"] if lost else [])
    return _finish(args, out, EXIT_OK, verb, pushed=True, doc_id=state["doc_id"], link=state["link"],
                   version=state["version"], converter_diff=lost, **fields,
                   lines=[f"{verb} {state['link']}" + (f" by {how}" if how else "")], errors=errors)


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # usage errors exit 1, as `--help` says; 2 is a conflict
        self.print_usage(sys.stderr)
        raise SystemExit(f"md2gdoc: {message}")


def main(argv: list[str] | None = None, drive=connect) -> int:
    prog = Path(sys.argv[0]).name or "md2gdoc"  # md2gdoc.py when run as the file, md2gdoc as the installed command
    parser = _Parser(prog=prog, description=HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")
    for name, fn, what in (("init", cmd_init, "create the Doc and the state file"),
                           ("pull", cmd_pull, "carry the Doc's changes onto the file"),
                           ("push", cmd_push, "write the file's changes to the Doc"),
                           ("sync", cmd_sync, "merge both sides' changes, write the file, push the Doc"),
                           ("status", cmd_status, "which side changed")):
        p = sub.add_parser(name, help=what)
        p.add_argument("file", help="the markdown file")
        p.add_argument("--dry-run", action="store_true", help="say what would happen; change nothing")
        p.add_argument("--json", action="store_true", help="one JSON object on stdout instead of prose")
        p.add_argument("--account", metavar="NAME",
                       help="the profile to use (default: $MD2GDOC_ACCOUNT, else default)")
        p.add_argument("--scope", choices=SCOPES, help="the Google scope for a profile's first login (default: "
                       "drive.file); remembered in its token")
        if name == "init":
            p.add_argument("--name", help="the Doc's title (default: the file's name without .md)")
            p.add_argument("--folder", help="Drive folder id to create the Doc in")
            p.add_argument("--doc", metavar="ID", help="attach FILE to the Doc with this id instead of creating one")
        if name == "pull":
            p.add_argument("--force", action="store_true", help="overwrite the file even if it changed")
        if name != "status":
            p.add_argument("--no-footer", action="store_true",
                           help="no footer naming the other side at the end of the file and the Doc; remembered")
        p.set_defaults(fn=fn)
    args = parser.parse_args(argv)
    try:
        return args.fn(args, drive)
    except SystemExit as e:  # a setup or state error raised as a message: the same object, exit 1
        if not args.json or not isinstance(e.code, str):
            raise
        print(json.dumps(error_object(e.code, argv if argv is not None else sys.argv[1:]), ensure_ascii=False))
        return EXIT_ERROR


def cli() -> None:
    """The entry point, for `python md2gdoc.py` and for the `md2gdoc` command `uv tool install` makes."""
    for stream in (sys.stdout, sys.stderr):  # UTF-8 whatever the console's code page (Windows), so diffs print
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors=stream.errors)
    try:
        sys.exit(main())
    except Exception as e:  # a Google error is one line, not a traceback; anything else is a bug
        if type(e).__name__ != "HttpError":
            raise
        if "--json" in sys.argv[1:]:
            print(json.dumps(error_object(f"md2gdoc: Google error: {e}", sys.argv[1:]), ensure_ascii=False))
            sys.exit(EXIT_ERROR)
        sys.exit(f"md2gdoc: Google error: {e}")


if __name__ == "__main__":
    cli()
