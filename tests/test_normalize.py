"""The text layer against tests/fixtures/: see that folder's README for what each equality means."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from md2gdoc import doc_view, normalize, push_form  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class CodeBlocks(unittest.TestCase):
    """Fixture 05: the push form and the fold are each other's inverse through Google."""

    def test_push_form_is_what_was_uploaded(self):
        self.assertEqual(push_form(fixture("05-code-blocks.src.md")), fixture("05-code-blocks.in.md"))

    def test_export_normalizes_back_to_the_source(self):
        src = fixture("05-code-blocks.src.md")
        self.assertEqual(normalize(fixture("05-code-blocks.out.md"), src), src)

    def test_info_string_is_empty_without_a_source(self):
        out = normalize(fixture("05-code-blocks.out.md"))
        self.assertIn("\n```\ndef hello():\n", out)
        self.assertNotIn("```python", out)


class HardBreaks(unittest.TestCase):
    """Fixture 06: soft breaks travel as hard breaks, and a one-line block exports as a span plus a space."""

    def test_push_form_is_what_was_uploaded(self):
        self.assertEqual(push_form(fixture("06-hard-breaks.src.md")), fixture("06-hard-breaks.in.md"))

    def test_export_normalizes_back_to_the_source(self):
        src = fixture("06-hard-breaks.src.md")
        self.assertEqual(normalize(fixture("06-hard-breaks.out.md"), src), src)


class Spans(unittest.TestCase):
    """Fixture 07: what is inside a code span comes back verbatim; the export escapes only outside spans."""

    def test_export_normalizes_like_the_upload(self):
        src = fixture("07-spans.in.md")
        self.assertEqual(normalize(fixture("07-spans.out.md")), normalize(src))
        # The one loss: the upload's deliberate escape outside a span is dropped on both sides.
        self.assertEqual(normalize(src), src.replace("\\_x\\_", "_x_"))


class HtmlComment(unittest.TestCase):
    """Fixture 15: Google's import drops a whole-line HTML comment and makes an open box of a resolved `[-]` line;
    the export indents a lazy continuation line and puts a blank line before a list that follows a paragraph."""

    def test_push_form_is_what_was_uploaded(self):
        self.assertEqual(push_form(fixture("15-html-comment.src.md")), fixture("15-html-comment.in.md"))

    def test_the_export_is_the_source_without_the_comments_but_for_three_rewrites(self):
        src = fixture("15-html-comment.src.md")
        self.assertIn("<!--", src)
        self.assertNotIn("<!--", fixture("15-html-comment.out.md"))
        expected = (doc_view(normalize(src))
                    .replace("- [-] 2026-09-01", "- [ ] 2026-09-01")
                    .replace("\nPat will", "\n  Pat will").replace("\nSam will", "\n  Sam will")
                    .replace("Also:\n- offer", "Also:\n\n- offer"))
        self.assertEqual(normalize(fixture("15-html-comment.out.md"), src), expected)


class ExportEscapes(unittest.TestCase):
    """Fixture 16 (PT-035): the export escapes a literal `+` or `~` in prose, each tilde of a literal `~~~` and a `)`
    after digits before a space, and consumes the file's own `\(`, `\)`, `\+`, `\~`; the normalizer drops them all,
    and keeps a line-start escape only where the character would make a block."""

    def test_the_export_normalizes_like_the_upload(self):
        src = fixture("16-export-escapes.in.md")
        out = fixture("16-export-escapes.out.md")
        for escaped in ("north \\+ south", "2013\\) and", "since 2013\\) too", "\\~\\$10", "Reading \\+ writing",
                        "\\+15550100", "\\~85 at the start", "\\~\\~\\~ not a fence", "a \\+ plus, a \\~ tilde"):
            self.assertIn(escaped, out)
        for plain in ("(front desk)", "(parens)", "~~struck~~", "2013)."):
            self.assertIn(plain, out)
        self.assertEqual(normalize(out), normalize(src))
        expected = (src.replace("\\(parens\\)", "(parens)").replace("a \\+ plus", "a + plus")
                    .replace("a \\~ tilde", "a ~ tilde").replace("a \\) after 2013\\).", "a ) after 2013).")
                    .replace("\n\\#tag at", "\n#tag at"))
        self.assertEqual(normalize(src), expected)
        kept = normalize(out)
        for line in ("\n+15550100 is", "\n\\+ not a bullet", "\n\\--- not a rule", "\n\\~~~ not a fence",
                     "\n~85 at the start"):
            self.assertIn(line, kept)

    def test_a_line_start_escape_stays_where_the_character_would_make_a_block(self):
        for kept in ("\\- a", "\\+ a", "\\* a", "\\#", "\\# h", "\\## h", "\\>q", "1\\. a", "1\\) a", "\\---", "\\***",
                     "\\___", "\\~~~py"):
            self.assertEqual(normalize(kept), kept + "\n")
        for dropped, plain in (("\\+1 a", "+1 a"), ("\\#tag", "#tag"), ("\\##tag", "##tag"), ("a \\~ b", "a ~ b"),
                               ("15105550100\\) x", "15105550100) x"), ("a \\+ b", "a + b"), ("(x\\)", "(x)")):
            self.assertEqual(normalize(dropped), plain + "\n")


class TaskList(unittest.TestCase):
    """Fixture 04: a task list round-trips exactly, and a UI edit shows up as the edit alone."""

    def test_pair(self):
        src = fixture("04-task-list.in.md")
        self.assertEqual(normalize(src), src)
        self.assertEqual(normalize(fixture("04-task-list.out.md")), src)

    def test_after_ui_edit(self):
        expected = fixture("04-task-list.in.md").replace("- [ ] T-002", "- [x] T-002").replace(
            "and **bold**\n", "and **bold**\n- [ ] **T-004 chad was notified this works**\n"
        ) + '\nT-004 - chad should be told "green eggs" to verify this works.\n'
        self.assertEqual(normalize(fixture("04-task-list.after-ui-edit.out.md")), expected)


class NestedCheckboxes(unittest.TestCase):
    """Fixture 08: a child's indent in the export is its parent's content column, whatever the parent is."""

    def test_pair(self):
        self.assertEqual(normalize(fixture("08-nested-checkboxes.out.md")), fixture("08-nested-checkboxes.in.md"))


class RawUploads(unittest.TestCase):
    """Fixtures 01 and 03 were uploaded raw, without the push form; what they lose is pinned here."""

    def test_01_markdown_import(self):
        expected = normalize(fixture("01-markdown-import.in.md"))
        for lost, got in [
            ("- Top level two\n\n1. First", "- Top level two\n1. First"),  # the blank between two lists
            ('```python\ndef hello():\n    return "world"\n```', 'def hello():\n\n    return "world"'),
            ('<div style="color:red">Raw HTML div</div>\n<details><summary>Summary</summary>Hidden text</details>'
             "\n\n## Extras", "Raw HTML div\n\n## SummaryHidden text Extras"),
        ]:
            self.assertIn(lost, expected)
            expected = expected.replace(lost, got)
        self.assertEqual(normalize(fixture("01-markdown-import.out.md")), expected)

    def test_03_resume_style(self):
        expected = normalize(fixture("03-resume-style.in.md"))
        for lost, got in [
            ("Paragraph line one.\nParagraph line two", "Paragraph line one. Paragraph line two"),  # soft break
            ("Version: 2026-10-20\nFor Reader", "Version: 2026-10-20 For Reader"),
            ("_Italic sentence using underscores._", "*Italic sentence using underscores.*"),
        ]:
            self.assertIn(lost, expected)
            expected = expected.replace(lost, got)
        self.assertEqual(normalize(fixture("03-resume-style.out.md")), expected)


class GfmHeadingsRules(unittest.TestCase):
    """Fixture 09: setext headings come back ATX, H4-H6 survive, every rule style comes back `---`."""

    def test_pair(self):
        expected = fixture("09-gfm-headings-rules.in.md")
        for lost, got in [("Setext H1\n=========", "# Setext H1"), ("Setext H2\n---------", "## Setext H2"),
                          ("\n***\n", "\n---\n"), ("\n___\n", "\n---\n"), ("\n- - -\n", "\n---\n")]:
            self.assertIn(lost, expected)
            expected = expected.replace(lost, got)
        self.assertIn("###### Heading six", expected)
        self.assertEqual(normalize(fixture("09-gfm-headings-rules.out.md")), expected)


class GfmListsQuotes(unittest.TestCase):
    """Fixture 10: markers survive but the blank between adjacent lists does not; a loose list stays loose; the
    export pads a quote with empty `>` lines; indented code loses its indent; a tab survives."""

    def test_push_form_is_what_was_uploaded(self):
        self.assertEqual(push_form(fixture("10-gfm-lists-quotes.src.md")), fixture("10-gfm-lists-quotes.in.md"))

    def test_export_normalizes_to_the_source_but_for_the_losses(self):
        src = fixture("10-gfm-lists-quotes.src.md")
        expected = src
        for lost, got in [
            ("- Dash bullet\n\n3. Starts", "- Dash bullet\n3. Starts"),  # the blank between adjacent lists
            ("4. Four\n\n1) Paren", "4. Four\n1) Paren"),
            ("> Quote with **bold**\n>\n> > Nested quote\n", ">\n> Quote with **bold**\n>\n> > Nested quote\n> >\n"),
            ("    indented code line\n    second indented line", "indented code line\n\nsecond indented line"),
        ]:
            self.assertIn(lost, expected)
            expected = expected.replace(lost, got)
        got = normalize(fixture("10-gfm-lists-quotes.out.md"), src)
        self.assertEqual(got, expected)
        self.assertIn("- Loose item one\n\n- Loose item two\n", got)
        self.assertIn("a\ttab", got)


class GfmInlines(unittest.TestCase):
    """Fixture 11: what each inline construct becomes; the image comes back as a data URI that pushes back."""

    def test_export_normalizes_to_the_upload_but_for_the_losses(self):
        expected = fixture("11-gfm-inlines.in.md")
        for lost, got in [
            ("__strong__", "**strong**"), ("_underscore italic_", "*underscore italic*"),
            ("&amp; &lt; &copy; &#169; &#x1F600; and a non-breaking&nbsp;space", "& < \u00a9 \u00a9 \U0001f600 and a "
             "non-breaking\u00a0space"),  # the no-break space stays one, U+00A0
            ('![GitHub favicon](https://github.githubassets.com/favicons/favicon.png "Pic title")',
             "![GitHub favicon][image1]"),
            ("<https://example.com/a>", "https://example.com/a"),
            ("<mailto:someone@example.com>", "[mailto:someone@example.com](mailto:someone@example.com)"),
            ("Bare www.example.com and https://example.com/b and someone@example.com",
             "Bare [www.example.com](http://www.example.com) and https://example.com/b and "
             "[someone@example.com](mailto:someone@example.com)"),
            ('[titled](https://example.com/c "The title")', "[titled](https://example.com/c)"),
            ("[ref link][r1]", "[ref link](https://example.com/r1)"),
            ("[collapsed][]", "[collapsed](https://example.com/collapsed)"),
            ("[r1]: https://example.com/r1\n\n[collapsed]: https://example.com/collapsed\n\n"
             "[shortcut]: https://example.com/shortcut\n", ""),
            ("[shortcut]", "[shortcut](https://example.com/shortcut)"),
            ("<b>bold</b>, <em>em</em>, break<br>after, <span style=\"color:red\">span</span>, "
             "<script>alert(1)</script>.", "**bold**, *em*, break\n\nafter, span, ."),
        ]:
            self.assertIn(lost, expected)
            expected = expected.replace(lost, got)
        got = normalize(fixture("11-gfm-inlines.out.md"))
        self.assertTrue(got.startswith(expected), got[:len(expected)])
        self.assertRegex(got[len(expected):], r'^\[image1\]: <data:image/png;base64,[A-Za-z0-9+/=]+> "Pic title"\n$')
        self.assertIn("~~gone~~ and **strong** and ***both*** and *star italic*", got)

    def test_the_export_fed_back_in_exports_the_same(self):
        self.assertEqual(fixture("11-gfm-inlines.round2.out.md"), fixture("11-gfm-inlines.out.md"))


class GfmListMarkers(unittest.TestCase):
    """Fixture 12: each marker style in its own list, a start at 3, nested mixed markers: all come back as written."""

    def test_pair(self):
        self.assertEqual(normalize(fixture("12-gfm-list-markers.out.md")), fixture("12-gfm-list-markers.in.md"))


class GithubPlatform(unittest.TestCase):
    """Fixture 14, GitHub's layer beyond GFM: a mermaid or math fence is a code run like any fence; an alert's
    marker keeps its own line through the push form's hard break; math comes back escaped and the normalizer drops
    the escapes; emoji shortcodes come back as characters; adjacent alerts merge into one quote; `<details>`
    flattens into one paragraph; color chips, a mention, an issue reference and a SHA are plain text."""

    def test_push_form_is_what_was_uploaded(self):
        self.assertEqual(push_form(fixture("14-github-platform.src.md")), fixture("14-github-platform.in.md"))

    def test_export_normalizes_to_the_source_but_for_the_losses(self):
        src = fixture("14-github-platform.src.md")
        expected = src
        for lost, got in [
            ("attention.\n\n> [!TIP]", "attention.\n>\n> [!TIP]"),  # two alerts back to back are one quote
            (":+1: :tada: :heavy_check_mark:", "\U0001f44d \U0001f389 \u2714\ufe0f"),
            ("<details>\n<summary>Collapsed section</summary>\n\nHidden paragraph with **bold** inside.\n\n</details>",
             "Collapsed section Hidden paragraph with **bold** inside."),
        ]:
            self.assertIn(lost, expected)
            expected = expected.replace(lost, got)
        got = normalize(fixture("14-github-platform.out.md"), src)
        self.assertEqual(got, expected)
        for kept in ("```mermaid\ngraph TD;\n    A-->B;", "> [!NOTE]\n> Useful", "math $\\sqrt{3x-1}+(1+x)^2$ in",
                     "and $5 for", "$$\n\\left( \\sum_{k=1}^n", "```math\n\\frac{a}{b} = c\n```", "`#0969DA`",
                     "@octocat, issue #1 and commit 16c999e8"):
            self.assertIn(kept, got)

    def test_what_the_export_holds_raw(self):
        out = fixture("14-github-platform.out.md")
        for raw in ("> \\[\\!NOTE\\]  \n> Useful", "\\$\\\\sqrt{3x-1}+(1+x)^2\\$", "\\$\\$  \n\\\\left(",
                    "`\\frac{a}{b} = c`", "issue \\#1"):
            self.assertIn(raw, out)


class Rules(unittest.TestCase):
    def test_normalize_is_idempotent_on_every_export(self):
        for path in sorted(FIXTURES.glob("*.out.md")):
            once = normalize(path.read_text(encoding="utf-8"))
            self.assertEqual(normalize(once), once, path.name)

    def test_escapes_that_keep_a_line_from_becoming_a_block_stay(self):
        self.assertEqual(normalize("\\- not a bullet\n1\\. not a list\n\\# not a heading\na \\- dash\n"),
                         "\\- not a bullet\n1\\. not a list\n\\# not a heading\na - dash\n")

    def test_an_escape_after_a_code_span_is_prose_and_dropped(self):
        self.assertEqual(normalize("Prove the `drive`\\-scope path\n"), "Prove the `drive`-scope path\n")
        self.assertEqual(normalize("\\- not a bullet, `code`\\-less\n"), "\\- not a bullet, `code`-less\n")

    def test_hard_breaks_go_where_the_doc_would_join_lines(self):
        self.assertEqual(push_form("one\ntwo\n\n- item\n  more\n# H\nthree\n> q\n> r\n| a |\n| b |\n"),
                         "one  \ntwo\n\n- item  \n  more\n# H\nthree\n> q  \n> r\n| a |\n| b |\n")
        self.assertEqual(push_form("> a\n>\n> b\n> > c\n> d\n\n> [!NOTE]\n> e\nf\n"),
                         "> a\n>\n> b\n> > c\n> d\n\n> [!NOTE]  \n> e  \nf\n")  # quoted alike; f is lazy
        self.assertEqual(push_form(">a\n> b\n"), ">a  \n> b\n")  # the same depth, spaced differently

    def test_the_exports_escapes_of_math_and_alert_markers_are_dropped(self):
        self.assertEqual(normalize("\\$\\\\sqrt{x}\\$ costs \\$5 \\[\\!NOTE\\]\n"), "$\\sqrt{x}$ costs $5 [!NOTE]\n")
        # the loss the Math row names: a `\$` a person wrote inside a formula is dropped the same way
        self.assertEqual(normalize("$\\sqrt{\\$4}$\n"), "$\\sqrt{$4}$\n")

    def test_one_line_block_gets_a_blank_line_and_backticks_are_padded(self):
        self.assertEqual(push_form("```\n`a`\n```\n"), "`` `a` ``  \n&nbsp;\n")
        self.assertEqual(normalize("`` `a` ``  \n   \n"), "```\n`a`\n```\n")

    def test_a_fence_in_a_file_is_left_alone(self):
        text = "```\n\\- x\na \\- b\n    - y\n| :-- |\n```\na \\- b\n"
        self.assertEqual(normalize(text), "```\n\\- x\na \\- b\n    - y\n| :-- |\n```\na - b\n")

    def test_inside_a_span_is_left_alone(self):
        self.assertEqual(normalize("regex `\\d+\\.` and `rm \\-rf` a \\- b [u](u)\n"),
                         "regex `\\d+\\.` and `rm \\-rf` a - b [u](u)\n")

    def test_a_block_may_open_with_a_blank_line(self):
        self.assertEqual(push_form("```\n\ncode\n```\n"), "&nbsp;  \n`code`\n")
        self.assertEqual(normalize("   \n`code`\n"), "```\n\ncode\n```\n")

    def test_a_partly_bold_heading_is_kept(self):
        self.assertEqual(normalize("# **a** and **b**\n"), "# **a** and **b**\n")

    def test_span_only_lines_take_no_break_before_another(self):
        self.assertEqual(push_form("`a`\n`b`\n\n`c`\nprose\n"), "`a`\n`b`\n\n`c`  \nprose\n")

    def test_a_lone_span_is_prose(self):
        self.assertEqual(normalize("`alpha` `beta`\n\n`gamma`\n"), "`alpha` `beta`\n\n`gamma`\n")


if __name__ == "__main__":
    unittest.main()
