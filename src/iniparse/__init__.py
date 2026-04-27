"""iniparse — zero-dependency INI parser with inheritance and interpolation.

Public surface::

    from iniparse import parse, parse_file, dumps, Config
    from iniparse import IniError, ParseError, InterpolationError

See the README for usage examples.
"""

from __future__ import annotations

from ._core import Config, dumps, parse, parse_file
from ._errors import IniError, InterpolationError, ParseError

__all__ = [
    "Config",
    "IniError",
    "InterpolationError",
    "ParseError",
    "dumps",
    "parse",
    "parse_file",
]

__version__ = "0.1.0"
