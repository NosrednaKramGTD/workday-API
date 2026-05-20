"""Pretty-print and ANSI-colorize XML for interactive debugging in examples."""

from __future__ import annotations

import os
import re
import sys
import xml.dom.minidom as minidom
from xml.parsers.expat import ExpatError

_ANSI_RESET = "\033[0m"
_ANSI_DECL = "\033[90m"
_ANSI_TAG = "\033[96m"
_ANSI_PUNCT = "\033[37m"
_ANSI_ATTR = "\033[93m"
_ANSI_VALUE = "\033[92m"

_ATTR_PATTERN = re.compile(
    r'(\s+)([\w:.-]+)(=)("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'
)

__all__ = ["colorize_xml", "format_xml", "print_xml", "use_color"]


def use_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def format_xml(xml: str) -> str:
    try:
        return minidom.parseString(xml).toprettyxml(indent="  ").strip()
    except ExpatError:
        return xml


def _colorize_tag(tag: str) -> str:
    if tag.startswith("<!--") or tag.startswith("<?"):
        return f"{_ANSI_DECL}{tag}{_ANSI_RESET}"

    match = re.match(
        r"^(<\/?)([\w:.-]+)((?:\s+[\w:.-]+(?:=(?:\"[^\"]*\"|'[^']*'))*\s*)?)(\/?>)$",
        tag,
        re.DOTALL,
    )
    if match is None:
        return tag

    open_bracket, name, attrs, close = match.groups()
    colored = (
        f"{_ANSI_PUNCT}{open_bracket}{_ANSI_RESET}"
        f"{_ANSI_TAG}{name}{_ANSI_RESET}"
    )

    def _colorize_attr(attr_match: re.Match[str]) -> str:
        ws, attr_name, equals, value = attr_match.groups()
        return (
            ws
            + f"{_ANSI_ATTR}{attr_name}{_ANSI_RESET}"
            + f"{_ANSI_PUNCT}{equals}{_ANSI_RESET}"
            + f"{_ANSI_VALUE}{value}{_ANSI_RESET}"
        )

    if attrs:
        colored += _ATTR_PATTERN.sub(_colorize_attr, attrs)
    colored += f"{_ANSI_PUNCT}{close}{_ANSI_RESET}"
    return colored


def colorize_xml(xml: str) -> str:
    if not use_color():
        return xml
    parts = re.split(r"(<[^>]+>)", xml)
    return "".join(_colorize_tag(part) if part.startswith("<") else part for part in parts)


def print_xml(
    xml: str,
    *,
    header: str | None = None,
    footer: str | None = None,
    file=None,
) -> None:
    """Print formatted XML with optional ANSI colors when stdout is a TTY."""
    if header is not None:
        print(header, file=file)
    print(colorize_xml(format_xml(xml)), file=file)
    if footer is not None:
        print(footer, file=file)
