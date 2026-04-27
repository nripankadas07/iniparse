"""Exception hierarchy for iniparse."""

from __future__ import annotations


class IniError(Exception):
    """Base exception for all iniparse failures."""


class ParseError(IniError):
    """Raised when INI text contains a syntax error.

    Carries the originating line number when known, so callers can show
    a helpful error to end users.
    """

    def __init__(self, message: str, *, line: int | None = None) -> None:
        if line is not None:
            super().__init__(f"line {line}: {message}")
        else:
            super().__init__(message)
        self.line = line


class InterpolationError(IniError):
    """Raised when a ``${...}`` reference cannot be resolved.

    The error covers both *missing* references (in strict mode only) and
    *circular* references (always — they cannot be expanded safely).
    """
