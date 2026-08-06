"""Stdlib unittest — no test dependencies. Run: uv run python -m unittest discover tests"""
import unittest

from oapple.html2md import to_markdown


class NestedLists(unittest.TestCase):
    def test_sibling_ul_is_a_child_of_the_preceding_li(self):
        # The Apple Notes quirk: the nested list follows the <li>, it isn't inside it.
        html = "<ul><li>DB</li><ul><li>Audit Log</li></ul><li>Next</li></ul>"
        self.assertEqual(to_markdown(html), "- DB\n  - Audit Log\n- Next")

    def test_deep_nesting_keeps_every_level(self):
        html = ("<ul><li>Inventory</li><ul><li>Devices</li>"
                "<ul><li>Interfaces</li><ul><li>Desc</li></ul></ul></ul></ul>")
        self.assertEqual(
            to_markdown(html),
            "- Inventory\n  - Devices\n    - Interfaces\n      - Desc")

    def test_depth_restored_after_a_nested_list_closes(self):
        html = ("<ul><li>a</li><ul><li>a1</li><ul><li>a1x</li></ul></ul>"
                "<li>b</li></ul>")
        self.assertEqual(to_markdown(html), "- a\n  - a1\n    - a1x\n- b")

    def test_properly_nested_html_gives_the_same_result(self):
        html = "<ul><li>DB<ul><li>Audit Log</li></ul></li><li>Next</li></ul>"
        self.assertEqual(to_markdown(html), "- DB\n  - Audit Log\n- Next")

    def test_ordered_lists_are_numbered_per_level(self):
        html = "<ol><li>one</li><li>two</li><ol><li>inner</li></ol><li>three</li></ol>"
        self.assertEqual(to_markdown(html),
                         "1. one\n2. two\n  1. inner\n3. three")


class Inline(unittest.TestCase):
    def test_headings_bold_italic_and_links(self):
        html = ("<div><h1>Title</h1></div><div><b>bold</b> and <i>it</i> "
                '<a href="https://x.dev">link</a></div>')
        self.assertEqual(to_markdown(html),
                         "# Title\n\n**bold** and *it* [link](https://x.dev)")

    def test_heading_levels(self):
        self.assertEqual(to_markdown("<h3>Three</h3>"), "### Three")

    def test_empty_emphasis_does_not_leak_markers(self):
        self.assertEqual(to_markdown("<div><b> </b>text</div>"), "text")

    def test_entities_and_nbsp_are_unescaped(self):
        self.assertEqual(to_markdown("<div>R&amp;D&nbsp;team &lt;x&gt;</div>"),
                         "R&D team <x>")


class Blocks(unittest.TestCase):
    def test_divs_and_br_become_line_breaks(self):
        self.assertEqual(to_markdown("<div>a</div><div>b<br>c</div>"), "a\nb\nc")

    def test_blank_paragraph_separates_blocks(self):
        html = "<ul><li>a</li></ul><div><br></div><ul><li>b</li></ul>"
        self.assertEqual(to_markdown(html), "- a\n\n- b")

    def test_runs_of_blank_lines_collapse_and_trailing_blanks_go(self):
        html = "<div>a</div><div><br></div><div><br></div><div><br></div>"
        self.assertEqual(to_markdown(html), "a")

    def test_empty_body(self):
        self.assertEqual(to_markdown(""), "")


class RealNoteBody(unittest.TestCase):
    """The body Apple Notes actually returned for the note that opened issue #1."""

    BODY = (
        "<div><h1>Back </h1></div>\n<ul>\n<li>Schedule runs </li>\n"
        "<li>Filesystem </li>\n<ul>\n<li>Config backup/restore</li>\n</ul>\n"
        "<li>DB</li>\n<ul>\n<li>Audit Log </li>\n<li>Inventory</li>\n<ul>\n"
        "<li>Devices</li>\n<ul>\n<li>Interfaces </li>\n<ul>\n<li>Desc</li>\n"
        "</ul>\n</ul>\n</ul>\n<li>Topology map</li>\n<ul>\n<li>LLDP/CDP</li>\n"
        "<li>L2</li>\n<ul>\n<li>STP</li>\n</ul>\n<li>L3</li>\n<ul>\n<li>ARP</li>\n"
        "<li>IGP</li>\n<li>BGP</li>\n</ul>\n</ul>\n</ul>\n</ul>\n<div><br></div>\n"
        "<ul>\n<li>AI Agent </li>\n</ul>"
    )

    EXPECTED = "\n".join([
        "# Back",
        "",
        "- Schedule runs",
        "- Filesystem",
        "  - Config backup/restore",
        "- DB",
        "  - Audit Log",
        "  - Inventory",
        "    - Devices",
        "      - Interfaces",
        "        - Desc",
        "  - Topology map",
        "    - LLDP/CDP",
        "    - L2",
        "      - STP",
        "    - L3",
        "      - ARP",
        "      - IGP",
        "      - BGP",
        "",
        "- AI Agent",
    ])

    def test_matches_the_notes_outline(self):
        self.assertEqual(to_markdown(self.BODY), self.EXPECTED)


if __name__ == "__main__":
    unittest.main()
