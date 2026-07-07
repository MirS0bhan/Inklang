"""Tests for inklang.parser (YAML load + Jinja fill + schema validation)."""

from __future__ import annotations

import json

import pytest

from inklang.errors import DataError, DesignError, MissingVariableError, SchemaError
from inklang.parser import format_validation_error, load_data, load_design

VALID_YAML = """
design: "Card"
size: "350x200"
background: "#ffffff"
elements:
  - type: text
    content: "Hello, {{name}}!"
    position: [20, 40]
    color: "#111111"
    font: { family: Arial, size: 24, weight: bold }
  - type: rect
    position: [0, 0]
    size: [{{w}}, 200]
    fill: "#ffffff"
    corner_radius: 8
  - type: circle
    center: [300, 100]
    radius: 25
    fill: "#cc0000"
"""


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_valid_design_parses(tmp_path):
    f = _write(tmp_path / "d.yaml", VALID_YAML)
    design = load_design(f, {"name": "World", "w": 350})

    assert design.design == "Card"
    assert design.width == 350.0
    assert design.height == 200.0
    assert len(design.elements) == 3
    assert design.elements[0].content == "Hello, World!"
    assert design.elements[1].size == [350.0, 200.0]  # {{w}} substituted


def test_design_with_no_data_renders_when_no_variables(tmp_path):
    f = _write(tmp_path / "d.yaml", "design: x\nsize: 10x10\nelements: []\n")
    design = load_design(f)  # data=None -> empty record
    assert design.size == "10x10"


def test_missing_variable_raises_clear_error(tmp_path):
    f = _write(tmp_path / "d.yaml", VALID_YAML)
    with pytest.raises(MissingVariableError) as exc_info:
        load_design(f, {"w": 350})  # 'name' is missing
    assert "name" in str(exc_info.value)
    assert exc_info.value.variable == "name"


def test_missing_variable_error_points_at_line(tmp_path):
    f = _write(tmp_path / "d.yaml", VALID_YAML)
    with pytest.raises(MissingVariableError) as exc_info:
        load_design(f, {"name": "World"})  # 'w' is missing
    assert "w" in str(exc_info.value)
    assert exc_info.value.variable == "w"


def test_invalid_yaml_raises_design_error(tmp_path):
    f = _write(tmp_path / "d.yaml", "design: x\n  size: [bad: yaml\n")
    with pytest.raises(DesignError):
        load_design(f)


def test_missing_required_field_raises_schema_error(tmp_path):
    # rect is missing its required 'size'
    bad = (
        "design: x\nsize: 10x10\nelements:\n"
        "  - type: rect\n    position: [0, 0]\n    fill: '#fff'\n"
    )
    f = _write(tmp_path / "d.yaml", bad)
    with pytest.raises(SchemaError) as exc_info:
        load_design(f)
    # Plain-English message names the field.
    assert "size" in str(exc_info.value)


def test_bad_size_format_raises_schema_error(tmp_path):
    f = _write(tmp_path / "d.yaml", "design: x\nsize: big\nelements: []\n")
    with pytest.raises(SchemaError) as exc_info:
        load_design(f)
    assert "WIDTHxHEIGHT" in str(exc_info.value)


def test_unknown_element_type_raises_schema_error(tmp_path):
    f = _write(
        tmp_path / "d.yaml",
        "design: x\nsize: 10x10\nelements:\n  - type: star\n    points: 5\n",
    )
    with pytest.raises(SchemaError):
        load_design(f)


def test_missing_design_file_raises(tmp_path):
    with pytest.raises(DesignError):
        load_design(str(tmp_path / "nope.yaml"))


def test_format_validation_error_is_plain_english():
    from pydantic import ValidationError

    from inklang.schema import RectElement

    try:
        RectElement.model_validate({"position": [0, 0]})  # missing size + fill
    except ValidationError as exc:
        msg = format_validation_error(exc)
        assert "not valid InkLang" in msg
        assert "size" in msg
        assert "fill" in msg
    else:  # pragma: no cover
        pytest.fail("expected ValidationError")


# --------------------------------------------------------------------------- #
# load_data (CSV / JSON)
# --------------------------------------------------------------------------- #


def test_load_data_none_returns_single_empty_record():
    assert load_data(None) == [{}]


def test_load_data_json_object(tmp_path):
    f = tmp_path / "d.json"
    f.write_text(json.dumps({"name": "A", "x": 1}), encoding="utf-8")
    assert load_data(str(f)) == [{"name": "A", "x": 1}]


def test_load_data_json_list(tmp_path):
    f = tmp_path / "d.json"
    f.write_text(json.dumps([{"name": "A"}, {"name": "B"}]), encoding="utf-8")
    assert len(load_data(str(f))) == 2


def test_load_data_csv(tmp_path):
    f = tmp_path / "d.csv"
    f.write_text("name,title\nA,Founder\nB,CTO\n", encoding="utf-8")
    records = load_data(str(f))
    assert records == [
        {"name": "A", "title": "Founder"},
        {"name": "B", "title": "CTO"},
    ]


def test_load_data_missing_file(tmp_path):
    with pytest.raises(DataError):
        load_data(str(tmp_path / "nope.json"))


def test_load_data_bad_json(tmp_path):
    f = tmp_path / "d.json"
    f.write_text("{not json", encoding="utf-8")
    with pytest.raises(DataError):
        load_data(str(f))


def test_load_data_unsupported_type(tmp_path):
    f = tmp_path / "d.txt"
    f.write_text("whatever", encoding="utf-8")
    with pytest.raises(DataError):
        load_data(str(f))
