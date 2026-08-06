"""HTML → Markdown, tuned for Apple Notes bodies. Stdlib only, no I/O.

Notes stores bodies as HTML, and outline structure lives entirely in nested
`<ul>`/`<ol>`; the plaintext form Notes hands out drops the indentation, so a
child item reads as a sibling. This converts the real body instead.

Apple quirk: Notes emits a nested list as a *sibling* of the `<li>` it belongs
to, not inside it — `<li>DB</li><ul><li>Audit Log</li></ul>`. Depth is therefore
counted from open list elements, not from `<li>` containment, which happens to
handle both that shape and well-formed HTML.
"""
import re
from html.parser import HTMLParser

_HEADINGS = {f"h{n}": n for n in range(1, 7)}
_LIST_TAGS = {"ul", "ol"}
# tags that end the current line but carry no inline meaning of their own
_BREAKING = {"div", "p", "tr", "blockquote", "table", "thead", "tbody"}
_INLINE_MARKS = {"b": "**", "strong": "**", "i": "*", "em": "*", "u": "", "span": ""}


class _Converter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.buf: list[str] = []
        self.mode: str | None = None      # None | "li" | "h"
        self.level = 0                    # heading level, when mode == "h"
        self.lists: list[str] = []        # open "ul"/"ol", innermost last
        self.counters: list[int] = []     # <ol> item numbers, parallel to lists
        self.marked = False               # bullet already written for this item
        self.inline: list[tuple[str, int, str | None]] = []  # (mark, buf idx, href)

    # ---------- line assembly ----------

    def _prefix(self) -> str:
        if self.mode == "h":
            return "#" * self.level + " "
        if self.mode == "li":
            indent = "  " * max(len(self.lists) - 1, 0)
            if self.marked:                      # continuation line of the same item
                return indent + "  "
            if self.lists and self.lists[-1] == "ol":
                return f"{indent}{self.counters[-1]}. "
            return indent + "- "
        return ""

    def _emit(self, forced: bool = False) -> None:
        """Close the current line. `forced` allows an empty line (an explicit <br>)."""
        text = "".join(self.buf).replace("\xa0", " ")
        text = re.sub(r"\s+", " ", text).strip()
        self.buf = []
        self.inline = []
        if text:
            self.lines.append(self._prefix() + text)
            if self.mode == "h":
                self.lines.append("")       # headings always get breathing room
            self.marked = True
        elif forced and self.mode != "li":
            self.lines.append("")

    def _close_block(self) -> None:
        self._emit()
        self.mode = None
        self.marked = False

    def _break(self) -> None:
        """A block boundary: a soft line break inside a list item, else a full close."""
        if self.mode == "li":
            self._emit()
        else:
            self._close_block()

    # ---------- parser hooks ----------

    def handle_starttag(self, tag, attrs):
        if tag in _LIST_TAGS:
            self._close_block()
            self.lists.append(tag)
            self.counters.append(0)
        elif tag == "li":
            self._close_block()
            self.mode = "li"
            if self.lists and self.lists[-1] == "ol":
                self.counters[-1] += 1
        elif tag in _HEADINGS:
            self._close_block()
            self.mode = "h"
            self.level = _HEADINGS[tag]
        elif tag == "br":
            self._emit(forced=True)
        elif tag == "a":
            href = dict(attrs).get("href")
            self.inline.append(("a", len(self.buf), href))
            self.buf.append("[")
        elif tag in _INLINE_MARKS:
            mark = _INLINE_MARKS[tag]
            self.inline.append((mark, len(self.buf), None))
            if mark:
                self.buf.append(mark)
        elif tag in _BREAKING:
            self._break()
        elif tag == "td" or tag == "th":
            if self.buf:
                self.buf.append(" | ")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in _LIST_TAGS:
            self._close_block()
            if self.lists:
                self.lists.pop()
                self.counters.pop()
        elif tag in ("li",) or tag in _HEADINGS:
            self._close_block()
        elif tag == "a" or tag in _INLINE_MARKS:
            self._close_inline(tag)
        elif tag in _BREAKING:
            self._break()

    def handle_data(self, data):
        self.buf.append(data)

    # ---------- inline spans ----------

    def _close_inline(self, tag: str) -> None:
        want = "a" if tag == "a" else _INLINE_MARKS[tag]
        for i in range(len(self.inline) - 1, -1, -1):
            mark, idx, href = self.inline[i]
            if mark != want:
                continue
            del self.inline[i]
            content = "".join(self.buf[idx + 1:]) if (mark or tag == "a") else ""
            if tag == "a":
                if content.strip() and href:
                    self.buf.append(f"]({href})")
                else:                       # empty or href-less link: drop the bracket
                    self.buf.pop(idx)
            elif mark:
                if content.strip():
                    self.buf.append(mark)
                else:                       # nothing to emphasise: drop the opener
                    self.buf.pop(idx)
            return

    # ---------- result ----------

    def result(self) -> str:
        self._close_block()
        out: list[str] = []
        for line in self.lines:
            if not line and (not out or not out[-1]):
                continue                    # collapse runs of blank lines
            out.append(line)
        while out and not out[-1]:
            out.pop()
        return "\n".join(out)


def to_markdown(html: str) -> str:
    """Convert an Apple Notes HTML body to Markdown, preserving list nesting."""
    c = _Converter()
    c.feed(html or "")
    c.close()
    return c.result()
