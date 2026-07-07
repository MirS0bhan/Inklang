"""Pydantic models that define the InkLang design language.

A design YAML file looks like::

    design: Poster
    size: "350x200"
    background: "#ffffff"
    gradients:                 # optional: reusable paints, referenced as fill: "ref:name"
      sky: { type: linear, stops: [{offset: 0, color: "#f00"}, {offset: 100, color: "#00f"}] }
    clips:                      # optional: named clip shapes
      avatar: { type: circle, center: [50, 50], radius: 40 }
    filters:                    # optional: named SVG filters
      blur: { primitives: [{type: gaussianBlur, std_deviation: 2}] }
    masks:                      # optional: named masks
      fade: { shapes: [{type: rect, position: [0,0], size: [100,100], fill: "#fff"}] }
    elements:
      - type: text
        content: "Hello, {{name}}!"
        position: [20, 40]
        color: "#111111"
        font: { family: Arial, size: 24, weight: bold }
      - type: rect
        position: [0, 0]
        size: [350, 200]
        fill: "ref:sky"        # reference a gradient by name
        stroke: { color: "#333333", width: 2 }
        corner_radius: 8
        clip: avatar           # clip this element with a named clip
      - type: group            # nest elements; the group's opacity/transform cascade
        opacity: 0.8
        children:
          - type: circle
            center: [300, 100]
            radius: 25
            fill: "#cc0000"

Supported element types: ``text``, ``rect``, ``circle``, ``ellipse``, ``line``,
``polyline``, ``polygon``, ``path``, ``image`` and ``group`` (which recurses).
Every element accepts the shared ``id``, ``opacity``, ``transform``, ``clip``,
``filter`` and ``mask`` fields defined on :class:`ElementBase`. See the project
README for the design principles this schema encodes.
"""

from __future__ import annotations

import re
from typing import Annotated, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

# A size string like "350x200", "350X200" or "350 x 200". Whitespace tolerant,
# case-insensitive separator, accepts integer or decimal dimensions.
_SIZE_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*[xX]\s*([0-9]*\.?[0-9]+)\s*$")


def parse_size(size: str) -> tuple[float, float]:
    """Parse a ``"WIDTHxHEIGHT"`` string into a ``(width, height)`` tuple.

    Raises ValueError with a plain message if the format is wrong, which
    Pydantic turns into a field validation error.
    """
    match = _SIZE_RE.match(size or "")
    if not match:
        raise ValueError(
            f"size must look like 'WIDTHxHEIGHT' (e.g. '350x200'), "
            f"got {size!r}"
        )
    return float(match.group(1)), float(match.group(2))


class Font(BaseModel):
    """Font description for text elements. ``size`` is in pixels."""

    family: str = "Arial"
    size: int = 16
    weight: Optional[str] = "normal"
    style: Optional[str] = "normal"


class Stroke(BaseModel):
    """An outline. ``dash`` is a list of dash/gap lengths (in px)."""

    color: str
    width: float = 1
    dash: Optional[List[float]] = None


# --------------------------------------------------------------------------- #
# Transforms
# --------------------------------------------------------------------------- #


class RotateSpec(BaseModel):
    """A rotation. ``center`` is optional; omit for rotation about the origin."""

    angle: float
    center: Optional[List[float]] = None


class TransformSpec(BaseModel):
    """A declarative SVG transform.

    Fields are applied in the order ``translate rotate scale skewX skewY``.
    Because SVG applies transforms right-to-left, this means the element is
    skewed, then scaled, then rotated (about its own origin or ``center``),
    then translated to its final position — which matches the usual mental
    model. A raw ``matrix`` string overrides everything else as an escape hatch.
    """

    translate: Optional[List[float]] = None
    rotate: Optional[Union[float, RotateSpec]] = None
    scale: Optional[Union[float, List[float]]] = None
    skewX: Optional[float] = None
    skewY: Optional[float] = None
    matrix: Optional[str] = None

    def to_svg(self) -> str:
        """Render this transform to an SVG ``transform="..."`` string."""
        if self.matrix is not None:
            value = self.matrix.strip()
            return value if value.startswith("matrix") else f"matrix({value})"
        parts: List[str] = []
        if self.translate:
            parts.append(f"translate({self.translate[0]} {self.translate[1]})")
        if self.rotate is not None:
            if isinstance(self.rotate, RotateSpec):
                if self.rotate.center:
                    c = self.rotate.center
                    parts.append(f"rotate({self.rotate.angle} {c[0]} {c[1]})")
                else:
                    parts.append(f"rotate({self.rotate.angle})")
            else:
                parts.append(f"rotate({self.rotate})")
        if self.scale is not None:
            if isinstance(self.scale, list):
                parts.append(f"scale({self.scale[0]} {self.scale[1]})")
            else:
                parts.append(f"scale({self.scale})")
        if self.skewX is not None:
            parts.append(f"skewX({self.skewX})")
        if self.skewY is not None:
            parts.append(f"skewY({self.skewY})")
        return " ".join(parts)


# --------------------------------------------------------------------------- #
# Elements
# --------------------------------------------------------------------------- #


class ElementBase(BaseModel):
    """Fields shared by every element type.

    ``opacity`` (0–1), an optional ``id``, a declarative ``transform``, and
    optional references to named ``clip`` / ``filter`` / ``mask`` definitions
    declared at the top level of the design.
    """

    id: Optional[str] = None
    opacity: Optional[float] = 1.0
    transform: Optional[TransformSpec] = None
    clip: Optional[str] = None
    filter: Optional[str] = None
    mask: Optional[str] = None


class TextElement(ElementBase):
    type: Literal["text"]
    content: str
    position: List[float]
    font: Font = Field(default_factory=Font)
    color: str = "#000000"


class RectElement(ElementBase):
    type: Literal["rect"]
    position: List[float]
    size: List[float]
    fill: str
    stroke: Optional[Stroke] = None
    corner_radius: Optional[float] = 0


class CircleElement(ElementBase):
    type: Literal["circle"]
    center: List[float]
    radius: float
    fill: str
    stroke: Optional[Stroke] = None


class EllipseElement(ElementBase):
    type: Literal["ellipse"]
    center: List[float]
    radii: List[float]  # [rx, ry]
    fill: str
    stroke: Optional[Stroke] = None


class LineElement(ElementBase):
    type: Literal["line"]
    start: List[float]
    end: List[float]
    stroke: Stroke  # required — a line has no fill


class PolylineElement(ElementBase):
    type: Literal["polyline"]
    points: List[List[float]]
    stroke: Stroke  # required
    fill: Optional[str] = None  # defaults to "none" in the renderer


class PolygonElement(ElementBase):
    type: Literal["polygon"]
    points: List[List[float]]
    fill: str = "#000000"
    stroke: Optional[Stroke] = None


class PathElementModel(ElementBase):
    """A freeform path. ``d`` is raw SVG path data (e.g. ``"M 0 0 L 10 10"``).

    Named ``PathElementModel`` (not ``PathElement``) to avoid clashing with the
    inkex :class:`inkex.PathElement` class used at render time.
    """

    type: Literal["path"]
    d: str
    fill: str = "#000000"
    stroke: Optional[Stroke] = None


class ImageElement(ElementBase):
    type: Literal["image"]
    src: str
    position: List[float]
    size: List[float]


class GroupElement(ElementBase):
    """A group of nested elements. Children recurse via the Element union."""

    type: Literal["group"]
    children: List["Element"] = []


# Discriminated union: Pydantic inspects ``type`` to pick the right model,
# giving precise errors (e.g. "rect is missing 'size'") instead of a generic
# "could not match any variant" message. Includes GroupElement, so the union
# is recursive — resolved by the model_rebuild() calls at the end of the module.
Element = Annotated[
    Union[
        TextElement,
        RectElement,
        CircleElement,
        EllipseElement,
        LineElement,
        PolylineElement,
        PolygonElement,
        PathElementModel,
        ImageElement,
        GroupElement,
    ],
    Field(discriminator="type"),
]


# Geometry-only shapes — used for clip paths and mask contents, where paint is
# either irrelevant (clips use only the outline) or set explicitly by the author
# (mask luminance comes from fill). Kept separate from the styled element models
# so that, e.g., a clip circle needs no ``fill``.
class RectGeo(BaseModel):
    type: Literal["rect"]
    position: List[float]
    size: List[float]
    fill: Optional[str] = None
    stroke: Optional[Stroke] = None


class CircleGeo(BaseModel):
    type: Literal["circle"]
    center: List[float]
    radius: float
    fill: Optional[str] = None
    stroke: Optional[Stroke] = None


class EllipseGeo(BaseModel):
    type: Literal["ellipse"]
    center: List[float]
    radii: List[float]
    fill: Optional[str] = None
    stroke: Optional[Stroke] = None


class PolygonGeo(BaseModel):
    type: Literal["polygon"]
    points: List[List[float]]
    fill: Optional[str] = None
    stroke: Optional[Stroke] = None


class PathGeo(BaseModel):
    type: Literal["path"]
    d: str
    fill: Optional[str] = None
    stroke: Optional[Stroke] = None


ClipShape = Annotated[
    Union[
        RectGeo,
        CircleGeo,
        EllipseGeo,
        PolygonGeo,
        PathGeo,
    ],
    Field(discriminator="type"),
]


# --------------------------------------------------------------------------- #
# Definitions: gradients, filters, masks (clips reuse ClipShape above)
# --------------------------------------------------------------------------- #


class StopSpec(BaseModel):
    """A gradient stop. ``offset`` is a percentage in the range 0–100."""

    offset: float = 0.0
    color: str = "#000000"
    opacity: Optional[float] = 1.0


class LinearGradientSpec(BaseModel):
    """A linear gradient. Coordinates are in objectBoundingBox units (0–1)."""

    type: Literal["linear"]
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 1.0
    y2: float = 0.0
    stops: List[StopSpec]


class RadialGradientSpec(BaseModel):
    """A radial gradient. Coordinates are in objectBoundingBox units (0–1)."""

    type: Literal["radial"]
    cx: float = 0.5
    cy: float = 0.5
    r: float = 0.5
    fx: Optional[float] = None
    fy: Optional[float] = None
    stops: List[StopSpec]


Gradient = Annotated[
    Union[LinearGradientSpec, RadialGradientSpec],
    Field(discriminator="type"),
]


# Filter primitives — a curated set covering the common effects (blur, offset,
# drop shadows, colour shifts, compositing). Each is discriminated by ``type``.
class GaussianBlurPrimitive(BaseModel):
    type: Literal["gaussianBlur"]
    std_deviation: Union[float, List[float]]


class OffsetPrimitive(BaseModel):
    type: Literal["offset"]
    dx: float = 0.0
    dy: float = 0.0


class ColorMatrixPrimitive(BaseModel):
    type: Literal["colorMatrix"]
    mode: Literal["matrix", "saturate", "hueRotate", "luminanceToAlpha"] = "saturate"
    values: Optional[str] = None


class BlendPrimitive(BaseModel):
    type: Literal["blend"]
    mode: str = "normal"
    in2: str = "SourceGraphic"


class MergePrimitive(BaseModel):
    type: Literal["merge"]
    nodes: List[str] = []  # input names, e.g. ["SourceGraphic"]


FilterPrimitive = Annotated[
    Union[
        GaussianBlurPrimitive,
        OffsetPrimitive,
        ColorMatrixPrimitive,
        BlendPrimitive,
        MergePrimitive,
    ],
    Field(discriminator="type"),
]


class FilterRegion(BaseModel):
    """The filter region. All fields optional; omitted fields use the SVG
    default (typically -10%/-10%/120%/120% of the bounding box)."""

    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    units: Optional[str] = None  # e.g. "userSpaceOnUse"


class FilterSpec(BaseModel):
    region: Optional[FilterRegion] = None
    primitives: List[FilterPrimitive]


class MaskSpec(BaseModel):
    """A mask. ``type`` sets the SVG ``mask-type`` (luminance by default). The
    mask's visible area is the union of ``shapes``."""

    type: Optional[Literal["luminance", "alpha"]] = None
    shapes: List[ClipShape] = []


# --------------------------------------------------------------------------- #
# Design
# --------------------------------------------------------------------------- #


class Design(BaseModel):
    """The top-level validated design object."""

    design: str
    size: str
    background: Optional[str] = None
    gradients: Dict[str, Gradient] = {}
    clips: Dict[str, ClipShape] = {}
    filters: Dict[str, FilterSpec] = {}
    masks: Dict[str, MaskSpec] = {}
    elements: List[Element] = []

    @field_validator("size")
    @classmethod
    def _validate_size(cls, v: str) -> str:
        parse_size(v)  # raises ValueError with a clear message if malformed
        return v

    @property
    def width(self) -> float:
        """Canvas width parsed from :attr:`size`, in pixels."""
        return parse_size(self.size)[0]

    @property
    def height(self) -> float:
        """Canvas height parsed from :attr:`size`, in pixels."""
        return parse_size(self.size)[1]


# Resolve the recursive forward reference in GroupElement.children (which uses
# the Element union defined above) and rebind Design's element list. Forgetting
# this leaves children accepted as unvalidated dicts — the worst failure mode.
GroupElement.model_rebuild()
Design.model_rebuild()
