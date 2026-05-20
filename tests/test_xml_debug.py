from __future__ import annotations

from workday_api.xml_debug import colorize_xml, format_xml


def test_format_xml_indents_well_formed_input() -> None:
    raw = '<root><child a="1"/></root>'
    formatted = format_xml(raw)
    assert "<root>" in formatted
    assert "  <child" in formatted


def test_format_xml_returns_input_on_parse_error() -> None:
    bad = "<root><unclosed>"
    assert format_xml(bad) == bad


def test_colorize_xml_respects_no_color(monkeypatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    xml = "<tag attr=\"v\">text</tag>"
    assert colorize_xml(xml) == xml


def test_colorize_xml_adds_ansi_when_enabled(monkeypatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("workday_api.xml_debug.sys.stdout.isatty", lambda: True)
    result = colorize_xml('<tag id="1"/>')
    assert "\033[" in result


def test_colorize_xml_declaration(monkeypatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("workday_api.xml_debug.sys.stdout.isatty", lambda: True)
    result = colorize_xml('<?xml version="1.0"?>')
    assert "\033[" in result


def test_print_xml_writes_formatted_output(capsys, monkeypatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    from workday_api.xml_debug import print_xml

    print_xml("<root/>", header="== header ==")
    out = capsys.readouterr().out
    assert "== header ==" in out
    assert "<root" in out


def test_print_xml_footer(capsys, monkeypatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    from workday_api.xml_debug import print_xml

    print_xml("<root/>", footer="== footer ==")
    out = capsys.readouterr().out
    assert "== footer ==" in out
