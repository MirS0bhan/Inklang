"""Custom, human-readable exception classes for InkLang.

Every error raised by InkLang subclasses :class:`InklangError` so the CLI can
catch it once and print a clean message instead of a stack trace.
"""

from __future__ import annotations

from typing import Optional


class InklangError(Exception):
    """Base class for all InkLang errors. Carry a plain-English message."""


class DesignError(InklangError):
    """A design file could not be read or located on disk."""


class DataError(InklangError):
    """A data file (CSV/JSON) could not be read or parsed."""


class MissingVariableError(InklangError):
    """A ``{{variable}}`` used in the design has no value in the data.

    Attributes:
        variable: The name of the missing variable (without braces).
        context:  Where it appeared, when known (e.g. an element description).
    """

    def __init__(self, variable: str, context: Optional[str] = None) -> None:
        self.variable = variable
        self.context = context
        location = f" (used in {context})" if context else ""
        super().__init__(
            f"Missing variable: '{variable}' is used in the design but was "
            f"not provided in the data{location}."
        )


class SchemaError(InklangError):
    """The parsed design does not match the InkLang schema.

    The wrapped ``errors`` list is the reformatted Pydantic validation output.
    """

    def __init__(self, message: str, errors=None) -> None:
        self.errors = errors or []
        super().__init__(message)


class RenderError(InklangError):
    """Something went wrong while building the SVG document."""


class ExportError(InklangError):
    """Inkscape is unavailable or the export command failed."""
