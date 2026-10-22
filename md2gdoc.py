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

This file is the whole tool. PT-005 ships its text layer, `normalize()` and `push_form()`, whose rules are in
docs/design.md under "Script design" and whose evidence is tests/fixtures/. The commands arrive with PT-006, and
with them the Google client libraries, imported only on the auth path so the text layer keeps running without them.
"""

from __future__ import annotations

import re

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


if __name__ == "__main__":
    raise SystemExit("md2gdoc: the commands arrive with PT-006; the text layer is importable now")
