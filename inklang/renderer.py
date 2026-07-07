"""Build an inkex SVG document from a validated :class:`~inklang.schema.Design`.

Each element type has a dedicated ``render_*`` function that takes the validated
Pydantic object and returns a fully-configured inkex element. Shared concerns
(id, opacity, transform, clip/filter/mask references) are applied uniformly by
:func:`_apply_common` after the type-specific renderer runs, and groups recurse
through :func:`_render_element`. :func:`render` assembles the document, paints
the optional background, and registers any gradient/clip/filter/mask definitions
in ``<defs>``.

We use inkex (Inkscape's own SVG library) rather than hand-built strings, so
elements, attributes and units are always SVG-correct and the output opens
cleanly in Inkscape for further editing.
"""

from __future__ import annotations

from typing import Any, Dict

from inkex import (
    Circle,
    ClipPath,
    Ellipse,
    Filter,
    Group,
    Image,
    Line,
    LinearGradient,
    Mask,
    Polygon,
    Polyline,
    RadialGradient,
    Rectangle,
    Stop,
    TextElement,
)
from inkex import PathElement as InkexPath  # avoid clashing with schema.PathElementModel
from inkex.base import SvgOutputMixin
from lxml import etree

from .errors import RenderError
from .schema import (
    CircleElement,
    Design,
    EllipseElement,
    ImageElement,
    LineElement,
    PathElementModel,
    PolygonElement,
    PolylineElement,
    RectElement,
    Stroke,
    TextElement as TextModel,
)


def _apply_stroke(element: Any, stroke: Stroke) -> None:
    """Apply a Stroke model to an element's inline ``style``."""
    element.style["stroke"] = stroke.color
    element.style["stroke-width"] = f"{stroke.width}px"
    if stroke.dash:
        element.style["stroke-dasharray"] = " ".join(str(d) for d in stroke.dash)


def _points_str(points) -> str:
    """Render a list of ``[x, y]`` pairs as an SVG ``points`` string."""
    return " ".join(f"{x},{y}" for x, y in points)


# --------------------------------------------------------------------------- #
# Per-element render functions (return an inkex node; shared attrs applied later)
# --------------------------------------------------------------------------- #


def render_text(el: TextModel) -> TextElement:
    """``<text x= y=>content</text>`` with font + colour."""
    node = TextElement(el.content, x=str(el.position[0]), y=str(el.position[1]))
    node.style["fill"] = el.color
    node.style["font-family"] = el.font.family
    node.style["font-size"] = f"{el.font.size}px"
    if el.font.weight and el.font.weight != "normal":
        node.style["font-weight"] = el.font.weight
    if el.font.style and el.font.style != "normal":
        node.style["font-style"] = el.font.style
    return node


def render_rect(el: RectElement) -> Rectangle:
    """``<rect x= y= width= height= rx=>`` with fill + optional stroke."""
    node = Rectangle.new(el.position[0], el.position[1], el.size[0], el.size[1])
    node.style["fill"] = el.fill
    if el.corner_radius:
        node.set("rx", str(el.corner_radius))
        node.set("ry", str(el.corner_radius))
    if el.stroke:
        _apply_stroke(node, el.stroke)
    return node


def render_circle(el: CircleElement) -> Circle:
    """``<circle cx= cy= r=>`` with fill + optional stroke."""
    node = Circle.new((el.center[0], el.center[1]), el.radius)
    node.style["fill"] = el.fill
    if el.stroke:
        _apply_stroke(node, el.stroke)
    return node


def render_ellipse(el: EllipseElement) -> Ellipse:
    """``<ellipse cx= cy= rx= ry=>`` with fill + optional stroke."""
    node = Ellipse.new((el.center[0], el.center[1]), (el.radii[0], el.radii[1]))
    node.style["fill"] = el.fill
    if el.stroke:
        _apply_stroke(node, el.stroke)
    return node


def render_line(el: LineElement) -> Line:
    """``<line x1= y1= x2= y2=>`` with a required stroke (no fill)."""
    node = Line.new((el.start[0], el.start[1]), (el.end[0], el.end[1]))
    _apply_stroke(node, el.stroke)
    return node


def render_polyline(el: PolylineElement) -> Polyline:
    """``<polyline points=>`` with a required stroke; fill defaults to none."""
    node = Polyline()
    node.set("points", _points_str(el.points))
    node.style["fill"] = el.fill if el.fill is not None else "none"
    _apply_stroke(node, el.stroke)
    return node


def render_polygon(el: PolygonElement) -> Polygon:
    """``<polygon points=>`` (closed) with fill + optional stroke."""
    node = Polygon()
    node.set("points", _points_str(el.points))
    node.style["fill"] = el.fill
    if el.stroke:
        _apply_stroke(node, el.stroke)
    return node


def render_path(el: PathElementModel) -> InkexPath:
    """``<path d=>`` with fill + optional stroke."""
    node = InkexPath.new(el.d)
    node.style["fill"] = el.fill
    if el.stroke:
        _apply_stroke(node, el.stroke)
    return node


def render_image(el: ImageElement) -> Image:
    """``<image x= y= width= height= xlink:href=>`` (opacity is shared)."""
    node = Image.new(
        x=str(el.position[0]),
        y=str(el.position[1]),
        width=f"{el.size[0]}px",
        height=f"{el.size[1]}px",
    )
    # xlink:href is the classic form Inkscape reads; href is the SVG2 form.
    # Set both so the image resolves in any viewer.
    node.set("xlink:href", el.src)
    node.set("href", el.src)
    return node


# --------------------------------------------------------------------------- #
# Shared attributes, references, and the recursive dispatch
# --------------------------------------------------------------------------- #


def _require(definitions: Dict[str, Any], name: str, kind: str, path: str) -> None:
    """Raise a located RenderError if ``name`` is not a known definition."""
    if name not in definitions:
        raise RenderError(f"{path}: unknown {kind} reference {name!r}")


def _apply_common(node: Any, el: Any, design: Design, path: str) -> None:
    """Apply id/opacity/transform/clip/filter/mask to any rendered node.

    Runs after the type-specific renderer. Group nodes get these too, so a
    group's opacity/transform/clip/filter/mask cascade to its children.
    """
    if el.id:
        node.set("id", el.id)
    if el.opacity is not None and el.opacity != 1.0:
        node.style["opacity"] = str(el.opacity)
    if el.transform is not None:
        transform = el.transform.to_svg()
        if transform:
            node.transform = transform
    if el.clip is not None:
        _require(design.clips, el.clip, "clip", path)
        node.set("clip-path", f"url(#{el.clip})")
    if el.mask is not None:
        _require(design.masks, el.mask, "mask", path)
        node.set("mask", f"url(#{el.mask})")
    if el.filter is not None:
        _require(design.filters, el.filter, "filter", path)
        node.style["filter"] = f"url(#{el.filter})"


def render_group(el: Any, design: Design, path: str) -> Group:
    """``<g>`` containing recursively-rendered children (common attrs applied
    by the caller via :func:`_apply_common`)."""
    group = Group()
    for index, child in enumerate(el.children):
        group.add(_render_element(child, design, f"{path}.children[{index}]"))
    return group


def _render_element(el: Any, design: Design, path: str) -> Any:
    """Dispatch one element to its renderer, apply common attrs, and wrap any
    failure in a located :class:`RenderError`."""
    try:
        if el.type == "group":
            node = render_group(el, design, path)
        else:
            renderer = _RENDERERS.get(el.type)
            if renderer is None:  # pragma: no cover - schema guarantees a known type
                raise RenderError(f"Unknown element type {el.type!r} at {path}")
            node = renderer(el)
        _apply_common(node, el, design, path)
        return node
    except RenderError:
        raise
    except Exception as exc:  # wrap so the user knows which element broke
        raise RenderError(
            f"Failed to render {el.type!r} element at {path}: {exc}"
        ) from exc


# Maps the schema's ``type`` discriminator to its leaf render function. Groups
# are handled separately (they recurse) and are deliberately not listed here.
_RENDERERS = {
    "text": render_text,
    "rect": render_rect,
    "circle": render_circle,
    "ellipse": render_ellipse,
    "line": render_line,
    "polyline": render_polyline,
    "polygon": render_polygon,
    "path": render_path,
    "image": render_image,
}


# --------------------------------------------------------------------------- #
# Definitions: gradients, clips, filters, masks
# --------------------------------------------------------------------------- #


def _resolve_fill_refs(design: Design) -> None:
    """Rewrite ``ref:name`` fills to ``url(#name)`` across the element tree.

    Renderers stay ignorant of gradients — by the time they run, every fill is
    either a plain colour or an explicit ``url(#...)``. Unknown refs raise a
    located :class:`RenderError`.
    """
    for index, el in enumerate(design.elements):
        _resolve_el_fill(el, design, f"elements[{index}]")


def _resolve_el_fill(el: Any, design: Design, path: str) -> None:
    fill = getattr(el, "fill", None)
    if isinstance(fill, str) and fill.startswith("ref:"):
        name = fill[len("ref:") :]
        _require(design.gradients, name, "gradient", path)
        el.fill = f"url(#{name})"
    if getattr(el, "type", None) == "group":
        for index, child in enumerate(el.children):
            _resolve_el_fill(child, design, f"{path}.children[{index}]")


def _build_gradient(name: str, spec: Any) -> Any:
    """Build a ``LinearGradient``/``RadialGradient`` with stop children.

    Coordinates are written verbatim as strings (SVG defaults to
    objectBoundingBox units). ``Stop`` requires a string offset.
    """
    if spec.type == "linear":
        gradient = LinearGradient(
            id=name,
            x1=str(spec.x1),
            y1=str(spec.y1),
            x2=str(spec.x2),
            y2=str(spec.y2),
        )
    else:  # radial
        attrs = dict(id=name, cx=str(spec.cx), cy=str(spec.cy), r=str(spec.r))
        if spec.fx is not None:
            attrs["fx"] = str(spec.fx)
        if spec.fy is not None:
            attrs["fy"] = str(spec.fy)
        gradient = RadialGradient(**attrs)

    for stop in spec.stops:
        node = Stop(offset=str(stop.offset))
        node.style["stop-color"] = stop.color
        if stop.opacity is not None and stop.opacity != 1.0:
            node.style["stop-opacity"] = str(stop.opacity)
        gradient.add(node)
    return gradient


def _render_geo(geo: Any) -> Any:
    """Build a bare inkex shape from a clip/mask geometry model.

    Paint is optional: clips ignore it (only the outline matters); mask authors
    set ``fill`` to control luminance.
    """
    if geo.type == "rect":
        node = Rectangle.new(geo.position[0], geo.position[1], geo.size[0], geo.size[1])
    elif geo.type == "circle":
        node = Circle.new((geo.center[0], geo.center[1]), geo.radius)
    elif geo.type == "ellipse":
        node = Ellipse.new((geo.center[0], geo.center[1]), (geo.radii[0], geo.radii[1]))
    elif geo.type == "polygon":
        node = Polygon()
        node.set("points", _points_str(geo.points))
    else:  # path
        node = InkexPath.new(geo.d)
    if geo.fill:
        node.style["fill"] = geo.fill
    if geo.stroke:
        _apply_stroke(node, geo.stroke)
    return node


def _add_primitive(filt: Filter, prim: Any) -> None:
    """Append one filter primitive (feGaussianBlur, feOffset, …) to ``filt``."""
    kind = prim.type
    if kind == "gaussianBlur":
        sd = prim.std_deviation
        sd_str = " ".join(str(v) for v in sd) if isinstance(sd, list) else str(sd)
        filt.add_primitive("feGaussianBlur", stdDeviation=sd_str)
    elif kind == "offset":
        filt.add_primitive("feOffset", dx=str(prim.dx), dy=str(prim.dy))
    elif kind == "colorMatrix":
        attrs = {"type": prim.mode}
        if prim.values is not None:
            attrs["values"] = prim.values
        filt.add_primitive("feColorMatrix", **attrs)
    elif kind == "blend":
        filt.add_primitive("feBlend", mode=prim.mode, in2=prim.in2)
    elif kind == "merge":
        merge = filt.add_primitive("feMerge")
        for input_name in prim.nodes:
            merge_node = Filter.MergeNode()
            merge_node.set("in", input_name)
            merge.append(merge_node)


def _build_filter(name: str, spec: Any) -> Filter:
    """Build a ``<filter>`` with its region and primitive chain."""
    filt = Filter(id=name)
    region = spec.region
    if region is not None:
        if region.x is not None:
            filt.set("x", str(region.x))
        if region.y is not None:
            filt.set("y", str(region.y))
        if region.width is not None:
            filt.set("width", str(region.width))
        if region.height is not None:
            filt.set("height", str(region.height))
        if region.units is not None:
            filt.set("filterUnits", region.units)
    for prim in spec.primitives:
        _add_primitive(filt, prim)
    return filt


def _register_defs(svg: Any, design: Design) -> None:
    """Register gradients, clips, filters and masks into ``<defs>``.

    ``svg.defs`` is get-or-create and prepends itself, so this is safe to call
    before the background rectangle is inserted at index 0.
    """
    for name, spec in design.gradients.items():
        svg.defs.add(_build_gradient(name, spec))
    for name, geo in design.clips.items():
        clip = ClipPath(id=name)
        clip.add(_render_geo(geo))
        svg.defs.add(clip)
    for name, spec in design.filters.items():
        svg.defs.add(_build_filter(name, spec))
    for name, spec in design.masks.items():
        mask = Mask(id=name)
        if spec.type is not None:
            mask.set("mask-type", spec.type)
        for geo in spec.shapes:
            mask.add(_render_geo(geo))
        svg.defs.add(mask)


# --------------------------------------------------------------------------- #
# Document assembly
# --------------------------------------------------------------------------- #


def render(design: Design) -> Any:
    """Build and return an ``inkex`` ``SvgDocumentElement`` for *design*.

    Sets the canvas size + viewBox, resolves gradient references, registers any
    definitions in ``<defs>``, paints the optional background as a full-canvas
    rectangle behind everything, then appends each element.
    """
    width = int(design.width)
    height = int(design.height)
    svg = SvgOutputMixin.get_template(width=width, height=height, unit="px").getroot()
    svg.set("viewBox", f"0 0 {width} {height}")

    _resolve_fill_refs(design)
    _register_defs(svg, design)

    if design.background:
        svg.insert(
            0,
            Rectangle.new(0, 0, width, height, fill=design.background, id="background"),
        )

    for index, element in enumerate(design.elements):
        svg.add(_render_element(element, design, f"elements[{index}]"))

    return svg


def write_svg(design: Design, path: str) -> str:
    """Render *design* and write it to a clean, human-readable ``.svg`` file.

    The output is pretty-printed XML with a UTF-8 declaration, so a designer
    can open it directly in Inkscape and keep editing.
    """
    svg = render(design)
    tree = etree.ElementTree(svg)
    # lxml's pretty_print only indents whitespace it parsed in; for a tree we
    # built by hand, indent() is what adds the line breaks and 2-space steps.
    etree.indent(tree, space="  ")
    tree.write(path, pretty_print=True, xml_declaration=True, encoding="utf-8")
    return path
