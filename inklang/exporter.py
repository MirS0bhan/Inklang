"""Export an SVG file to PNG or PDF by driving Inkscape's command line.

Inkscape does the actual rasterisation/vector conversion; we just build the
right CLI invocation through :func:`inkex.command.inkscape` and translate any
failure into a clear :class:`~inklang.errors.ExportError`.

The Inkscape call itself goes through the module-level ``inkscape`` /
``is_inkscape_available`` names, which tests can monkey-patch so the suite
passes without Inkscape installed.
"""

from __future__ import annotations

from pathlib import Path

from inkex.command import ProgramRunError, inkscape, is_inkscape_available

from .errors import ExportError

SUPPORTED_FORMATS = ("png", "pdf")


def is_available() -> bool:
    """Return ``True`` if an ``inkscape`` executable is on ``PATH``."""
    return is_inkscape_available()


def _resolve_format(out_path: str, fmt: str | None) -> str:
    if fmt:
        fmt = fmt.lower().lstrip(".")
    else:
        fmt = Path(out_path).suffix.lower().lstrip(".")
    if fmt not in SUPPORTED_FORMATS:
        raise ExportError(
            f"Unsupported export format {fmt!r}. "
            f"Choose one of: {', '.join(SUPPORTED_FORMATS)}."
        )
    return fmt


def export(
    svg_path: str,
    out_path: str,
    fmt: str | None = None,
    dpi: int = 96,
) -> str:
    """Export *svg_path* to *out_path* in PNG or PDF format.

    Args:
        svg_path: Path to the input ``.svg`` file.
        out_path: Where to write the exported file.
        fmt:      ``"png"`` or ``"pdf"``. If omitted, inferred from
            *out_path*'s extension.
        dpi:      Raster DPI (PNG). Ignored by Inkscape for vector (PDF) output.

    Returns:
        The *out_path* on success.

    Raises:
        ExportError: if the SVG is missing, Inkscape is unavailable, the
            format is unsupported, or Inkscape's export command fails.
    """
    fmt = _resolve_format(out_path, fmt)

    if not Path(svg_path).is_file():
        raise ExportError(f"SVG file not found: {svg_path}")

    # Ensure the output directory exists so the Inkscape call can write to it.
    out_dir = Path(out_path).parent
    if str(out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)

    if not is_available():
        raise ExportError(
            "Inkscape was not found on your PATH. Install Inkscape "
            "(https://inkscape.org/release/) and make sure the 'inkscape' "
            "command is runnable, then try again."
        )

    try:
        # Maps to: inkscape --export-filename=<out> --export-type=<fmt>
        #          --export-dpi=<dpi> <svg_path>
        inkscape(
            svg_path,
            export_filename=out_path,
            export_type=fmt,
            export_dpi=dpi,
        )
    except ProgramRunError as exc:
        raise ExportError(
            f"Inkscape failed to export {svg_path} -> {out_path} ({fmt}):\n"
            f"  {exc}"
        ) from exc
    except Exception as exc:  # e.g. CommandNotFound on a broken install
        raise ExportError(f"Inkscape export failed unexpectedly: {exc}") from exc

    return out_path
