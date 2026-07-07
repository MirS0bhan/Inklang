"""Command-line interface for InkLang.

Commands::

    inklang render <design.yaml> --data <data.json> --out <output.svg>
    inklang batch  <design.yaml> --data <data.csv>  --out-dir <folder>
    inklang export <input.svg>   --format png|pdf   --out <output-file>

``render`` produces one SVG from a single data record; ``batch`` produces one
SVG per row of a CSV/JSON data file; ``export`` turns an SVG into a PNG or PDF
via Inkscape.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

import click

from .errors import InklangError
from .exporter import export as export_file
from .parser import load_data, load_design
from .renderer import write_svg

_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(name: str, index: int) -> str:
    """Turn a data value into a filesystem-safe base filename."""
    cleaned = _UNSAFE_FILENAME.sub("_", str(name).strip()).strip("_.")
    return cleaned or f"design_{index:03d}"


@click.group()
@click.version_option(package_name="inklang")
def cli() -> None:
    """InkLang — generate SVG designs from declarative YAML."""


@cli.command()
@click.argument("design", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--data",
    "data_path",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="A JSON file with one data record (object, or list with one entry).",
)
@click.option("--out", "out_path", required=True, help="Output .svg path.")
def render(design: str, data_path: str | None, out_path: str) -> None:
    """Render a single design with one data record to one SVG file."""
    records = load_data(data_path)
    if not records:
        raise InklangError(f"The data file {data_path} contains no records.")
    record: Dict[str, Any] = records[0]

    parsed = load_design(design, record)
    write_svg(parsed, out_path)
    click.echo(f"Wrote {out_path}")


@cli.command()
@click.argument("design", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--data",
    "data_path",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="A CSV or JSON file with one record per row.",
)
@click.option(
    "--out-dir",
    "out_dir",
    required=True,
    type=click.Path(file_okay=False),
    help="Directory to write the SVGs into (created if missing).",
)
@click.option(
    "--name-field",
    default="name",
    show_default=True,
    help="Column whose value names each output file.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["svg", "png", "pdf"], case_sensitive=False),
    default="svg",
    show_default=True,
    help="Output format. svg writes a .svg; png/pdf also exports via Inkscape.",
)
@click.option("--dpi", default=96, show_default=True, type=int)
def batch(
    design: str,
    data_path: str,
    out_dir: str,
    name_field: str,
    fmt: str,
    dpi: int,
) -> None:
    """Render one SVG per row of a CSV/JSON data file."""
    records = load_data(data_path)
    if not records:
        raise InklangError(f"The data file {data_path} contains no records.")

    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    fmt = fmt.lower()
    written = 0
    for index, record in enumerate(records):
        parsed = load_design(design, record)
        base = _safe_filename(record.get(name_field, ""), index)
        svg_path = out_root / f"{base}.svg"
        write_svg(parsed, str(svg_path))

        if fmt == "svg":
            click.echo(f"Wrote {svg_path}")
        else:
            target = out_root / f"{base}.{fmt}"
            export_file(str(svg_path), str(target), fmt=fmt, dpi=dpi)
            click.echo(f"Wrote {target} (from {svg_path})")
        written += 1

    click.echo(f"Done: {written} design(s) -> {out_root}")


@cli.command()
@click.argument("input_svg", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["png", "pdf"], case_sensitive=False),
    default=None,
    help="Output format. Inferred from --out if omitted.",
)
@click.option("--out", "out_path", required=True, help="Output file path.")
@click.option("--dpi", default=96, show_default=True, type=int, help="PNG raster DPI.")
def export(input_svg: str, fmt: str | None, out_path: str, dpi: int) -> None:
    """Export an SVG to PNG or PDF using Inkscape."""
    export_file(input_svg, out_path, fmt=fmt, dpi=dpi)
    click.echo(f"Wrote {out_path}")


def main() -> None:
    """Entry point used by the ``inklang`` console script."""
    try:
        cli(standalone_mode=False)
    except click.exceptions.Abort:
        raise SystemExit(130)
    except click.ClickException as exc:
        exc.show()
        raise SystemExit(exc.exit_code)
    except click.exceptions.Exit as exc:
        raise SystemExit(exc.exit_code)
    except InklangError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)
