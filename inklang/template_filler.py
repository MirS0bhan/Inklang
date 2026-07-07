"""Jinja2 ``{{variable}}`` substitution for design files.

A design file may reference values from a data record with Jinja2 syntax,
e.g. ``content: "Hello, {{name}}!"`` or ``src: "logos/{{client}}.png"``. This
module fills those in *before* the YAML is parsed.

We use :class:`jinja2.StrictUndefined` so that a referenced-but-missing
variable raises immediately, instead of silently rendering as an empty string.
The error is converted into a :class:`~inklang.errors.MissingVariableError`
that names the variable and points at the line where it appears.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from jinja2 import StrictUndefined, TemplateError, UndefinedError
from jinja2.environment import Environment

from .errors import MissingVariableError

_UNDEFINED_NAME = re.compile(r"'(.+?)' is undefined")


def _find_context(variable: str, template: str) -> Optional[str]:
    """Return a short description of where ``variable`` appears in the text."""
    needle = "{{" + variable
    for line in template.splitlines():
        if needle in line:
            return f"line: {line.strip()}"
    return None


def fill(template: str, data: Optional[Dict[str, Any]] = None) -> str:
    """Render ``{{variables}}`` in *template* using *data*.

    Args:
        template: Raw design-file text.
        data:     Mapping of variable name -> value. ``None`` is treated as an
                  empty mapping (so any used variable is reported as missing).

    Raises:
        MissingVariableError: if the design references a variable that ``data``
            does not provide.
        TemplateError:        for any other Jinja2 rendering error (e.g. a
            malformed ``{% %}`` block).
    """
    data = data or {}
    env = Environment(
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,
    )
    try:
        return env.from_string(template).render(**data)
    except UndefinedError as exc:
        match = _UNDEFINED_NAME.search(str(exc))
        variable = match.group(1) if match else "<unknown>"
        context = _find_context(variable, template)
        raise MissingVariableError(variable, context) from exc
    except TemplateError:
        # Re-raise other Jinja errors unchanged; the parser will wrap them.
        raise
