"""Loading and validating design + data files.

The pipeline implemented here is exactly:

1. Read the design YAML file as raw text.
2. Fill ``{{variables}}`` with one data record (Jinja2).
3. Parse the filled text with ``yaml.safe_load``.
4. Validate the resulting dict against the InkLang :mod:`~inklang.schema`.
5. Return a :class:`~inklang.schema.Design`.

Every failure along the way is raised as a subclass of
:class:`~inklang.errors.InklangError` with a plain-English message.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import ValidationError

from .errors import DataError, DesignError, SchemaError
from .schema import Design
from .template_filler import fill


def _format_loc(loc) -> str:
    """Turn a Pydantic error location tuple into ``elements[0].size``."""
    parts: List[str] = []
    for part in loc:
        if isinstance(part, int):
            parts.append(f"[{part}]")
        else:
            parts.append(("." if parts else "") + str(part))
    return "".join(parts) or "<root>"


def format_validation_error(exc: ValidationError) -> str:
    """Render a Pydantic validation error as a plain-English message."""
    seen = set()
    lines: List[str] = []
    for err in exc.errors():
        loc = _format_loc(err.get("loc", ()))
        msg = err.get("msg", "is invalid")
        key = (loc, msg)
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"  • {loc}: {msg}")
    body = "\n".join(lines) if lines else "  • (no details available)"
    return "The design file is not valid InkLang:\n" + body


def load_data(path: Optional[str]) -> List[Dict[str, Any]]:
    """Load a data file into a list of record dicts.

    Supports:
      * ``.json`` — a single object (wrapped to length 1) or a list of objects.
      * ``.csv``  — one record per row (header row supplies the field names).

    Returns ``[{}]`` (one empty record) when *path* is ``None`` so that a
    design with no variables still renders.

    Raises :class:`~inklang.errors.DataError` on missing files or bad JSON.
    """
    if path is None:
        return [{}]

    p = Path(path)
    if not p.is_file():
        raise DataError(f"Data file not found: {path}")

    suffix = p.suffix.lower()
    try:
        if suffix == ".json":
            with p.open(encoding="utf-8") as fh:
                records = json.load(fh)
            if isinstance(records, dict):
                records = [records]
            elif not isinstance(records, list):
                raise DataError(
                    f"JSON data file must be an object or a list, got "
                    f"{type(records).__name__}: {path}"
                )
            # Normalise: every entry must be a dict.
            normalised: List[Dict[str, Any]] = []
            for i, rec in enumerate(records):
                if not isinstance(rec, dict):
                    raise DataError(
                        f"JSON data entry #{i} must be an object, got "
                        f"{type(rec).__name__}: {path}"
                    )
                normalised.append(rec)
            return normalised

        if suffix == ".csv":
            with p.open(encoding="utf-8", newline="") as fh:
                return list(csv.DictReader(fh))

        raise DataError(
            f"Unsupported data file type {suffix!r} (expected .json or .csv): "
            f"{path}"
        )
    except DataError:
        raise
    except (json.JSONDecodeError, OSError) as exc:
        raise DataError(f"Could not read data file {path}: {exc}") from exc


def load_design(yaml_path: str, data: Optional[Dict[str, Any]] = None) -> Design:
    """Load, fill, parse and validate a design file into a :class:`Design`.

    Args:
        yaml_path: Path to the design ``.yaml`` file.
        data:      A single data record (dict) used to fill ``{{variables}}``.
            ``None`` means no data — any referenced variable will raise.

    Raises:
        DesignError:            file missing, unreadable, or not valid YAML.
        MissingVariableError:   a ``{{variable}}`` has no value in *data*.
        SchemaError:            the parsed dict does not match the schema.
    """
    path = Path(yaml_path)
    if not path.is_file():
        raise DesignError(f"Design file not found: {yaml_path}")

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DesignError(f"Could not read design file {yaml_path}: {exc}") from exc

    # 1. Fill {{variables}} before parsing, so a value can shape the YAML itself.
    filled = fill(raw, data)

    # 2. Parse YAML.
    try:
        parsed = yaml.safe_load(filled)
    except yaml.YAMLError as exc:
        raise DesignError(
            f"The design file is not valid YAML:\n  {exc}" f"\n  File: {yaml_path}"
        ) from exc

    if not isinstance(parsed, dict):
        raise DesignError(
            "The design file must contain a YAML mapping at the top level "
            f"(got {type(parsed).__name__}): {yaml_path}"
        )

    # 3. Validate against the schema.
    try:
        return Design.model_validate(parsed)
    except ValidationError as exc:
        raise SchemaError(format_validation_error(exc)) from exc
