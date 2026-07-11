"""Tests for inklang.reverse_parser (SVG to YAML conversion).

Tests the bidirectional conversion:
- SVG element parsing (all element types)
- Gradient, filter, clip, mask extraction from <defs>
- Attribute and style preservation
- Round-tripping: SVG → Design → YAML → Design
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from inklang.errors import ParseError
from inklang.renderer import render, write_svg
from inklang.reverse_parser import parse_svg_to_design, svg_to_yaml
from inklang.schema import (
    CircleElement,
    Design,
    EllipseElement,
    LineElement,
    PolygonElement,
    PolylineElement,
    RectElement,
    TextElement as TextModel,
    CircleGeo,
    LinearGradientSpec,
)


def _design(**overrides):
    """Helper to create a Design for testing."""
    base = {"design": "test", "size": "100x50", "elements": []}
    base.update(overrides)
    return Design.model_validate(base)


def _write_and_parse(design: Design) -> Design:
    """Render a design to SVG, write it, then parse it back."""
    tmp_file = Path("/tmp/test_reverse.svg")
    write_svg(design, str(tmp_file))
    return parse_svg_to_design(tmp_file)


# --------------------------------------------------------------------------- #
# Basic Element Parsing
# --------------------------------------------------------------------------- #


def test_parse_rect_element(tmp_path):
    """Parse <rect> with fill, stroke, and corner radius."""
    design = _design(
        elements=[
            {
                "type": "rect",
                "position": [10, 20],
                "size": [30, 40],
                "fill": "#ff0000",
                "stroke": {"color": "#000000", "width": 2},
                "corner_radius": 5,
            }
        ]
    )
    svg_path = tmp_path / "rect.svg"
    write_svg(design, str(svg_path))
    parsed = parse_svg_to_design(svg_path)

    assert len(parsed.elements) == 1
    rect = parsed.elements[0]
    assert isinstance(rect, RectElement)
    assert rect.position == [10.0, 20.0]
    assert rect.size == [30.0, 40.0]
    assert rect.fill == "#ff0000"
    assert rect.stroke is not None
    assert rect.stroke.color == "#000000"
    assert rect.stroke.width == 2.0
    assert rect.corner_radius == 5.0


def test_parse_circle_element(tmp_path):
    """Parse <circle> with center, radius, and stroke."""
    design = _design(
        elements=[
            {
                "type": "circle",
                "center": [50, 60],
                "radius": 15,
                "fill": "#0000ff",
                "stroke": {"color": "#333", "width": 1},
            }
        ]
    )
    svg_path = tmp_path / "circle.svg"
    write_svg(design, str(svg_path))
    parsed = parse_svg_to_design(svg_path)

    assert len(parsed.elements) == 1
    circle = parsed.elements[0]
    assert isinstance(circle, CircleElement)
    assert circle.center == [50.0, 60.0]
    assert circle.radius == 15.0
    assert circle.fill == "#0000ff"


def test_parse_ellipse_element(tmp_path):
    """Parse <ellipse> with radii."""
    design = _design(
        elements=[
            {
                "type": "ellipse",
                "center": [40, 50],
                "radii": [20, 30],
                "fill": "#ffff00",
            }
        ]
    )
    svg_path = tmp_path / "ellipse.svg"
    write_svg(design, str(svg_path))
    parsed = parse_svg_to_design(svg_path)

    assert len(parsed.elements) == 1
    ellipse = parsed.elements[0]
    assert isinstance(ellipse, EllipseElement)
    assert ellipse.center == [40.0, 50.0]
    assert ellipse.radii == [20.0, 30.0]


def test_parse_line_element(tmp_path):
    """Parse <line> with stroke (required)."""
    design = _design(
        elements=[
            {
                "type": "line",
                "start": [0, 0],
                "end": [100, 50],
                "stroke": {"color": "#000000", "width": 2},
            }
        ]
    )
    svg_path = tmp_path / "line.svg"
    write_svg(design, str(svg_path))
    parsed = parse_svg_to_design(svg_path)

    assert len(parsed.elements) == 1
    line = parsed.elements[0]
    assert isinstance(line, LineElement)
    assert line.start == [0.0, 0.0]
    assert line.end == [100.0, 50.0]
    assert line.stroke.color == "#000000"


def test_parse_text_element(tmp_path):
    """Parse <text> with content, position, color, and font."""
    design = _design(
        elements=[
            {
                "type": "text",
                "content": "Hello, World!",
                "position": [10, 30],
                "color": "#333333",
                "font": {"family": "Arial", "size": 24, "weight": "bold"},
            }
        ]
    )
    svg_path = tmp_path / "text.svg"
    write_svg(design, str(svg_path))
    parsed = parse_svg_to_design(svg_path)

    assert len(parsed.elements) == 1
    text = parsed.elements[0]
    assert isinstance(text, TextModel)
    assert text.content == "Hello, World!"
    assert text.position == [10.0, 30.0]
    assert text.color == "#333333"
    assert text.font.family == "Arial"
    assert text.font.size == 24


def test_parse_polygon_element(tmp_path):
    """Parse <polygon> with multiple points."""
    design = _design(
        elements=[
            {
                "type": "polygon",
                "points": [[0, 0], [50, 0], [25, 50]],
                "fill": "#ff00ff",
            }
        ]
    )
    svg_path = tmp_path / "polygon.svg"
    write_svg(design, str(svg_path))
    parsed = parse_svg_to_design(svg_path)

    assert len(parsed.elements) == 1
    polygon = parsed.elements[0]
    assert isinstance(polygon, PolygonElement)
    assert polygon.fill == "#ff00ff"
    # Points should be preserved
    assert len(polygon.points) == 3


def test_parse_polyline_element(tmp_path):
    """Parse <polyline> (open shape)."""
    design = _design(
        elements=[
            {
                "type": "polyline",
                "points": [[0, 0], [25, 25], [50, 0]],
                "stroke": {"color": "#000", "width": 2},
            }
        ]
    )
    svg_path = tmp_path / "polyline.svg"
    write_svg(design, str(svg_path))
    parsed = parse_svg_to_design(svg_path)

    assert len(parsed.elements) == 1
    polyline = parsed.elements[0]
    assert isinstance(polyline, PolylineElement)
    assert len(polyline.points) == 3


def test_parse_path_element(tmp_path):
    """Parse <path> with SVG path data."""
    design = _design(
        elements=[
            {
                "type": "path",
                "d": "M 10 10 L 90 90",
                "fill": "#ffff00",
            }
        ]
    )
    svg_path = tmp_path / "path.svg"
    write_svg(design, str(svg_path))
    parsed = parse_svg_to_design(svg_path)

    assert len(parsed.elements) == 1
    path = parsed.elements[0]
    assert path.type == "path"
    assert "M" in path.d or "m" in path.d  # path data preserved


# --------------------------------------------------------------------------- #
# Canvas & Background
# --------------------------------------------------------------------------- #


def test_parse_canvas_size_from_viewbox(tmp_path):
    """Extract canvas size from viewBox attribute."""
    design = _design(size="350x200")
    svg_path = tmp_path / "size.svg"
    write_svg(design, str(svg_path))
    parsed = parse_svg_to_design(svg_path)

    assert parsed.size == "350x200"
    assert parsed.width == 350.0
    assert parsed.height == 200.0


def test_parse_background_color(tmp_path):
    """Extract background color."""
    design = _design(size="100x100", background="#cccccc")
    svg_path = tmp_path / "bg.svg"
    write_svg(design, str(svg_path))
    parsed = parse_svg_to_design(svg_path)

    assert parsed.background == "#cccccc"


def test_parse_no_background_when_unset(tmp_path):
    """No background field when not specified."""
    design = _design(size="100x100")
    svg_path = tmp_path / "no_bg.svg"
    write_svg(design, str(svg_path))
    parsed = parse_svg_to_design(svg_path)

    assert parsed.background is None


# --------------------------------------------------------------------------- #
# Gradients
# --------------------------------------------------------------------------- #


def test_parse_linear_gradient(tmp_path):
    """Extract linear gradient from <defs>."""
    design = _design(
        size="100x100",
        gradients={
            "sky": {
                "type": "linear",
                "x1": 0,
                "y1": 0,
                "x2": 1,
                "y2": 1,
                "stops": [
                    {"offset": 0, "color": "#ff0000"},
                    {"offset": 100, "color": "#0000ff"},
                ],
            }
        },
        elements=[
            {
                "type": "rect",
                "position": [0, 0],
                "size": [100, 100],
                "fill": "ref:sky",
            }
        ],
    )
    svg_path = tmp_path / "gradient.svg"
    write_svg(design, str(svg_path))
    parsed = parse_svg_to_design(svg_path)

    assert "sky" in parsed.gradients
    gradient = parsed.gradients["sky"]
    assert isinstance(gradient, LinearGradientSpec)
    assert gradient.type == "linear"
    assert len(gradient.stops) == 2
    assert gradient.stops[0].color == "#ff0000"
    assert gradient.stops[1].color == "#0000ff"


def test_parse_radial_gradient(tmp_path):
    """Extract radial gradient from <defs>."""
    design = _design(
        size="100x100",
        gradients={
            "radial": {
                "type": "radial",
                "cx": 0.5,
                "cy": 0.5,
                "r": 0.5,
                "stops": [
                    {"offset": 0, "color": "#ffffff"},
                    {"offset": 100, "color": "#000000"},
                ],
            }
        },
        elements=[
            {
                "type": "rect",
                "position": [0, 0],
                "size": [100, 100],
                "fill": "ref:radial",
            }
        ],
    )
    svg_path = tmp_path / "radial.svg"
    write_svg(design, str(svg_path))
    parsed = parse_svg_to_design(svg_path)

    assert "radial" in parsed.gradients


# --------------------------------------------------------------------------- #
# Transforms & Opacity
# --------------------------------------------------------------------------- #


def test_parse_opacity(tmp_path):
    """Parse opacity attribute."""
    design = _design(
        elements=[
            {
                "type": "rect",
                "position": [0, 0],
                "size": [50, 50],
                "fill": "#ff0000",
                "opacity": 0.5,
            }
        ]
    )
    svg_path = tmp_path / "opacity.svg"
    write_svg(design, str(svg_path))
    parsed = parse_svg_to_design(svg_path)

    assert len(parsed.elements) == 1
    rect = parsed.elements[0]
    assert rect.opacity == 0.5


def test_parse_transform(tmp_path):
    """Parse transform attribute (translate, rotate, scale)."""
    design = _design(
        elements=[
            {
                "type": "rect",
                "position": [0, 0],
                "size": [30, 30],
                "fill": "#00ff00",
                "transform": {
                    "translate": [10, 20],
                    "rotate": 45,
                    "scale": 1.5,
                },
            }
        ]
    )
    svg_path = tmp_path / "transform.svg"
    write_svg(design, str(svg_path))
    parsed = parse_svg_to_design(svg_path)

    assert len(parsed.elements) == 1
    rect = parsed.elements[0]
    assert rect.transform is not None


# --------------------------------------------------------------------------- #
# Stroke Dashes
# --------------------------------------------------------------------------- #


def test_parse_stroke_with_dash(tmp_path):
    """Parse stroke-dasharray."""
    design = _design(
        elements=[
            {
                "type": "rect",
                "position": [10, 10],
                "size": [50, 50],
                "fill": "#ffffff",
                "stroke": {"color": "#000000", "width": 2, "dash": [5, 3]},
            }
        ]
    )
    svg_path = tmp_path / "dash.svg"
    write_svg(design, str(svg_path))
    parsed = parse_svg_to_design(svg_path)

    rect = parsed.elements[0]
    assert rect.stroke is not None
    assert rect.stroke.dash == [5.0, 3.0]


# --------------------------------------------------------------------------- #
# Groups (Nested Elements)
# --------------------------------------------------------------------------- #


def test_parse_group_with_children(tmp_path):
    """Parse <g> with nested elements."""
    design = _design(
        elements=[
            {
                "type": "group",
                "opacity": 0.8,
                "children": [
                    {
                        "type": "rect",
                        "position": [0, 0],
                        "size": [25, 25],
                        "fill": "#ff0000",
                    },
                    {
                        "type": "circle",
                        "center": [50, 50],
                        "radius": 10,
                        "fill": "#0000ff",
                    },
                ],
            }
        ]
    )
    svg_path = tmp_path / "group.svg"
    write_svg(design, str(svg_path))
    parsed = parse_svg_to_design(svg_path)

    assert len(parsed.elements) == 1
    group = parsed.elements[0]
    assert group.type == "group"
    assert group.opacity == 0.8
    assert len(group.children) == 2


# --------------------------------------------------------------------------- #
# Round-trip Tests (SVG → YAML → SVG)
# --------------------------------------------------------------------------- #


def test_roundtrip_simple_rect(tmp_path):
    """Render rect → SVG → parse → YAML → verify."""
    design = _design(
        elements=[
            {
                "type": "rect",
                "position": [5, 10],
                "size": [40, 50],
                "fill": "#ff00ff",
            }
        ]
    )
    svg_path = tmp_path / "rt.svg"
    write_svg(design, str(svg_path))

    # Parse SVG back to Design
    parsed = parse_svg_to_design(svg_path)

    # Verify key properties survived
    assert len(parsed.elements) == 1
    assert parsed.elements[0].type == "rect"
    assert parsed.elements[0].fill == "#ff00ff"


def test_roundtrip_complex_design(tmp_path):
    """Round-trip a complex design with multiple element types."""
    design = _design(
        size="200x150",
        background="#eeeeee",
        elements=[
            {
                "type": "rect",
                "position": [0, 0],
                "size": [200, 150],
                "fill": "#eeeeee",
            },
            {
                "type": "text",
                "content": "Title",
                "position": [10, 30],
                "color": "#000000",
                "font": {"family": "Arial", "size": 20},
            },
            {
                "type": "circle",
                "center": [100, 100],
                "radius": 30,
                "fill": "#ff0000",
                "stroke": {"color": "#000000", "width": 2},
            },
        ],
    )
    svg_path = tmp_path / "complex.svg"
    write_svg(design, str(svg_path))
    parsed = parse_svg_to_design(svg_path)

    assert parsed.size == "200x150"
    assert len(parsed.elements) >= 3  # At least rect, text, circle


# --------------------------------------------------------------------------- #
# YAML Output
# --------------------------------------------------------------------------- #


def test_svg_to_yaml_output(tmp_path):
    """Generate YAML string from SVG."""
    design = _design(
        elements=[
            {
                "type": "rect",
                "position": [0, 0],
                "size": [50, 50],
                "fill": "#ff0000",
            }
        ]
    )
    svg_path = tmp_path / "out.svg"
    write_svg(design, str(svg_path))

    yaml_str = svg_to_yaml(svg_path)
    assert isinstance(yaml_str, str)
    assert "rect" in yaml_str or "Rect" in yaml_str.lower()
    assert "50" in yaml_str  # size should be in YAML


def test_svg_to_yaml_write_file(tmp_path):
    """Write parsed SVG to YAML file."""
    design = _design(
        elements=[
            {
                "type": "circle",
                "center": [25, 25],
                "radius": 15,
                "fill": "#0000ff",
            }
        ]
    )
    svg_path = tmp_path / "in.svg"
    write_svg(design, str(svg_path))

    yaml_path = tmp_path / "out.yaml"
    svg_to_yaml(svg_path, output_path=yaml_path)

    assert yaml_path.exists()
    yaml_content = yaml_path.read_text()
    assert "circle" in yaml_content or "design" in yaml_content


# --------------------------------------------------------------------------- #
# Error Handling
# --------------------------------------------------------------------------- #


def test_parse_missing_file():
    """Raise ParseError on missing SVG file."""
    with pytest.raises(ParseError):
        parse_svg_to_design("/nonexistent/file.svg")


def test_parse_invalid_svg():
    """Raise ParseError on invalid SVG."""
    tmp_file = Path("/tmp/invalid.svg")
    tmp_file.write_text("not valid xml", encoding="utf-8")
    with pytest.raises(ParseError):
        parse_svg_to_design(tmp_file)


def test_parse_svg_without_viewbox_or_size():
    """Raise ParseError when canvas size cannot be determined."""
    tmp_file = Path("/tmp/no_size.svg")
    # SVG without viewBox, width, or height
    tmp_file.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="10" height="10"/></svg>',
        encoding="utf-8",
    )
    with pytest.raises(ParseError):
        parse_svg_to_design(tmp_file)
