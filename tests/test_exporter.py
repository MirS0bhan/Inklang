"""Tests for inklang.exporter.

The Inkscape call is mocked so these tests pass without Inkscape installed.
We assert that the *command we would run* is built correctly, plus the
error paths (missing file, unavailable Inkscape, unsupported format, Inkscape
failure).
"""

from __future__ import annotations

import pytest
from inkex.command import ProgramRunError

from inklang.errors import ExportError
from inklang.exporter import SUPPORTED_FORMATS, export


@pytest.fixture
def fake_svg(tmp_path):
    p = tmp_path / "drawing.svg"
    p.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    return str(p)


@pytest.fixture
def mock_inkscape(monkeypatch):
    """Patch the exporter to think Inkscape is present and record the call."""
    calls = []

    def fake_inkscape(svg_file, *args, **kwargs):
        calls.append({"svg_file": svg_file, "args": args, "kwargs": kwargs})
        return ""

    monkeypatch.setattr("inklang.exporter.inkscape", fake_inkscape)
    monkeypatch.setattr("inklang.exporter.is_inkscape_available", lambda: True)
    return calls


def test_export_png_builds_correct_command(fake_svg, mock_inkscape, tmp_path):
    out = str(tmp_path / "out.png")
    export(fake_svg, out, fmt="png", dpi=150)

    assert len(mock_inkscape) == 1
    call = mock_inkscape[0]
    assert call["svg_file"] == fake_svg
    assert call["kwargs"]["export_filename"] == out
    assert call["kwargs"]["export_type"] == "png"
    assert call["kwargs"]["export_dpi"] == 150


def test_export_format_inferred_from_extension(fake_svg, mock_inkscape, tmp_path):
    out_pdf = str(tmp_path / "out.pdf")
    export(fake_svg, out_pdf)
    assert mock_inkscape[0]["kwargs"]["export_type"] == "pdf"

    out_png = str(tmp_path / "out.png")
    export(fake_svg, out_png)
    assert mock_inkscape[1]["kwargs"]["export_type"] == "png"


def test_export_creates_output_directory(fake_svg, mock_inkscape, tmp_path):
    nested = tmp_path / "deep" / "nested" / "out.png"
    export(fake_svg, str(nested), fmt="png")
    assert nested.parent.is_dir()


def test_export_returns_out_path(fake_svg, mock_inkscape, tmp_path):
    out = str(tmp_path / "out.png")
    assert export(fake_svg, out, fmt="png") == out


@pytest.mark.parametrize("fmt", ["jpg", "gif", ""])
def test_unsupported_format_raises(fake_svg, mock_inkscape, tmp_path, fmt):
    with pytest.raises(ExportError) as exc_info:
        export(fake_svg, str(tmp_path / "out"), fmt=fmt or None)
    assert "Unsupported" in str(exc_info.value)


def test_missing_svg_raises(tmp_path, mock_inkscape):
    with pytest.raises(ExportError) as exc_info:
        export(str(tmp_path / "nope.svg"), str(tmp_path / "out.png"), fmt="png")
    assert "not found" in str(exc_info.value)


def test_inkscape_unavailable_raises(fake_svg, monkeypatch, tmp_path):
    monkeypatch.setattr("inklang.exporter.inkscape", lambda *a, **k: "")
    monkeypatch.setattr("inklang.exporter.is_inkscape_available", lambda: False)
    with pytest.raises(ExportError) as exc_info:
        export(fake_svg, str(tmp_path / "out.png"), fmt="png")
    assert "Inkscape was not found" in str(exc_info.value)


def test_inkscape_failure_wrapped_as_export_error(fake_svg, monkeypatch, tmp_path):
    def failing(svg_file, *args, **kwargs):
        raise ProgramRunError("inkscape", 1, b"something broke", b"")

    monkeypatch.setattr("inklang.exporter.inkscape", failing)
    monkeypatch.setattr("inklang.exporter.is_inkscape_available", lambda: True)

    with pytest.raises(ExportError) as exc_info:
        export(fake_svg, str(tmp_path / "out.png"), fmt="png")
    assert "Inkscape failed" in str(exc_info.value)


def test_supported_formats_are_png_and_pdf():
    assert set(SUPPORTED_FORMATS) == {"png", "pdf"}
