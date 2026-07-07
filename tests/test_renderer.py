"""Tests for inklang.renderer (SVG element construction via inkex).

We assert on the actual SVG attributes/style produced — not just "it didn't
crash" — by inspecting the inkex elements directly and by round-tripping the
written file through an XML parse.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

import pytest

from inklang.renderer import (
    render,
    render_circle,
    render_image,
    render_rect,
    render_text,
    write_svg,
)
from inklang.schema import (
    CircleElement,
    Design,
    ImageElement,
    RectElement,
    Stroke,
    TextElement as TextModel,
)

NS = "{http://www.w3.org/2000/svg}"


def _design(**overrides):
    base = {"design": "t", "size": "100x50", "elements": []}
    base.update(overrides)
    return Design.model_validate(base)


# --------------------------------------------------------------------------- #
# Per-element render functions
# --------------------------------------------------------------------------- #


def test_rect_attributes_and_style():
    el = RectElement.model_validate(
        {
            "type": "rect",
            "position": [10, 20],
            "size": [30, 40],
            "fill": "#ff0000",
            "stroke": {"color": "#000000", "width": 2, "dash": [4, 2]},
            "corner_radius": 6,
        }
    )
    r = render_rect(el)
    assert r.get("x") == "10.0"
    assert r.get("y") == "20.0"
    assert r.get("width") == "30.0"
    assert r.get("height") == "40.0"
    assert r.get("rx") == "6.0"
    assert r.get("ry") == "6.0"
    assert r.style["fill"] == "#ff0000"
    assert r.style["stroke"] == "#000000"
    assert r.style["stroke-width"] == "2.0px"
    assert r.style["stroke-dasharray"] == "4.0 2.0"


def test_rect_without_stroke_or_radius():
    el = RectElement.model_validate(
        {"type": "rect", "position": [0, 0], "size": [1, 1], "fill": "#fff"}
    )
    r = render_rect(el)
    assert r.style["fill"] == "#fff"
    assert r.get("rx") is None  # no corner radius set
    assert "stroke" not in r.style


def test_circle_attributes():
    el = CircleElement.model_validate(
        {"type": "circle", "center": [50, 60], "radius": 12, "fill": "blue"}
    )
    c = render_circle(el)
    assert c.get("cx") == "50.0"
    assert c.get("cy") == "60.0"
    assert c.get("r") == "12.0"
    assert c.style["fill"] == "blue"


def test_text_content_and_font():
    el = TextModel.model_validate(
        {
            "type": "text",
            "content": "Hello",
            "position": [5, 15],
            "color": "#222",
            "font": {"family": "Georgia", "size": 28, "weight": "bold", "style": "italic"},
        }
    )
    t = render_text(el)
    assert t.text == "Hello"
    assert t.get("x") == "5.0"
    assert t.get("y") == "15.0"
    assert t.style["fill"] == "#222"
    assert t.style["font-family"] == "Georgia"
    assert t.style["font-size"] == "28px"
    assert t.style["font-weight"] == "bold"
    assert t.style["font-style"] == "italic"


def test_text_default_font_omits_weight_style():
    el = TextModel.model_validate(
        {"type": "text", "content": "x", "position": [1, 2], "color": "#000"}
    )
    t = render_text(el)
    assert "font-weight" not in t.style  # 'normal' is the default -> omitted
    assert "font-style" not in t.style
    assert t.style["font-size"] == "16px"


def test_image_href_and_opacity():
    el = ImageElement.model_validate(
        {
            "type": "image",
            "src": "logo.png",
            "position": [0, 0],
            "size": [40, 40],
            "opacity": 0.5,
        }
    )
    img = render_image(el)
    assert img.get("x") == "0.0"
    assert img.get("width") == "40.0px"
    assert img.get("height") == "40.0px"
    assert img.get("{http://www.w3.org/1999/xlink}href") == "logo.png"
    assert img.get("href") == "logo.png"
    assert img.style["opacity"] == "0.5"


def test_image_full_opacity_omitted():
    el = ImageElement.model_validate(
        {"type": "image", "src": "a.png", "position": [0, 0], "size": [1, 1]}
    )
    img = render_image(el)
    assert "opacity" not in img.style


# --------------------------------------------------------------------------- #
# Full document assembly
# --------------------------------------------------------------------------- #


def test_render_sets_canvas_size_and_viewbox():
    svg = render(_design(size="350x200"))
    assert svg.get("width") == "350px"
    assert svg.get("height") == "200px"
    assert svg.get("viewBox") == "0 0 350 200"


def test_background_inserted_behind_elements():
    design = _design(
        size="350x200",
        background="#abcdef",
        elements=[
            {"type": "rect", "position": [0, 0], "size": [1, 1], "fill": "#fff"}
        ],
    )
    svg = render(design)
    children = list(svg)
    # First child is the full-canvas background rect.
    assert children[0].get("id") == "background"
    assert children[0].get("fill") == "#abcdef"
    assert children[0].get("width") == "350"
    assert children[0].get("height") == "200"


def test_no_background_when_unset():
    svg = render(_design())
    assert not [c for c in svg if c.get("id") == "background"]


def test_write_svg_round_trips_as_xml(tmp_path):
    design = _design(
        elements=[
            {"type": "rect", "position": [0, 0], "size": [10, 10], "fill": "#f00"},
            {"type": "text", "content": "Hi", "position": [1, 2], "color": "#000"},
        ]
    )
    out = tmp_path / "out.svg"
    write_svg(design, str(out))

    tree = ET.parse(out)
    root = tree.getroot()
    assert root.tag == f"{NS}svg"
    assert root.get("viewBox") == "0 0 100 50"
    tags = [child.tag for child in root]
    assert f"{NS}rect" in tags
    assert f"{NS}text" in tags
    # Text content survived the round trip.
    text_node = next(c for c in root if c.tag == f"{NS}text")
    assert text_node.text == "Hi"


def test_write_svg_has_xml_declaration_and_is_pretty(tmp_path):
    design = _design(
        elements=[{"type": "rect", "position": [0, 0], "size": [1, 1], "fill": "#fff"}]
    )
    out = tmp_path / "out.svg"
    write_svg(design, str(out))
    text = out.read_text(encoding="utf-8")
    assert text.startswith("<?xml")
    assert "\n  <rect" in text  # indented child = human-readable


def test_render_wraps_per_element_errors(monkeypatch):
    # Renderer dispatches through the _RENDERERS dict, so patch that entry to
    # force a failure and confirm it is wrapped as a RenderError naming the index.
    design = _design(
        elements=[{"type": "rect", "position": [0, 0], "size": [1, 1], "fill": "#fff"}]
    )

    def boom(_el):
        raise RuntimeError("kaboom")

    import inklang.renderer as renderer

    monkeypatch.setitem(renderer._RENDERERS, "rect", boom)

    with pytest.raises(renderer.RenderError) as exc_info:
        render(design)
    assert "elements[0]" in str(exc_info.value)
    assert "kaboom" in str(exc_info.value)
