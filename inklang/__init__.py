"""InkLang — a declarative YAML language for generating SVG designs.

Public entry points:

* :func:`inklang.parser.load_design` — load + validate a design file.
* :func:`inklang.renderer.render` — build an inkex SVG document from a design.
* :func:`inklang.renderer.write_svg` — render a design straight to a ``.svg``.
* :func:`inklang.exporter.export` — export an SVG to PNG/PDF via Inkscape.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .errors import InklangError
from .parser import load_data, load_design
from .schema import Design

__all__ = [
    "__version__",
    "InklangError",
    "Design",
    "load_data",
    "load_design",
]
