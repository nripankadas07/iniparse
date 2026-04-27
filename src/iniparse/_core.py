"""Parser, serializer, and ``Config`` model for iniparse.

The implementation is intentionally compact: ``parse`` walks the text
once and builds an in-memory ``Config``; ``Config`` resolves the
inheritance chain lazily and applies ``${...}`` interpolation on every
``get`` call so callers always see the latest substitution result.
"""

from __future__ import annotations

import os
import re
from typing import Sequence

from ._errors import IniError, InterpolationError, ParseError

__all__ = ["Config", "parse", "parse_file", "dumps"]

_SECTION_RE = re.compile(
    r"^\[\s*(?P<name>[^\]:]+?)\s*"
    r"(?::\s*(?P<parents>[^\]]*?)\s*)?\]$"
)
_INTERP_RE = re.compile(r"\$\{([^${}]*)\}")
_MAX_INTERP_DEPTH = 25
_MISSING = object()


class Config:
    """Parsed INI configuration with section inheritance and interpolation.

    Sections are stored in insertion order. Each section may declare an
    optional list of parent sections (``[child : parent1, parent2]``);
    keys are resolved depth-first across that chain, with the first hit
    winning. Values containing ``${key}`` or ``${section:key}`` are
    expanded on every ``get`` (use ``raw=True`` to skip expansion).
    """

    def __init__(self, *, strict: bool = True) -> None:
        self._data: dict[str, dict[str, str]] = {}
        self._parents: dict[str, list[str]] = {}
        self._strict = strict

    def __repr__(self) -> str:
        return f"Config(sections={list(self._data)!r})"

    def __contains__(self, section: object) -> bool:
        return section in self._data

    def sections(self) -> list[str]:
        """Return all section names in insertion order."""
        return list(self._data)

    def parents(self, section: str) -> list[str]:
        """Return the declared parent sections for ``section``."""
        if section not in self._data:
            raise IniError(f"unknown section: {section!r}")
        return list(self._parents.get(section, ()))

    def has_section(self, section: str) -> bool:
        """Return True if ``section`` is declared."""
        return section in self._data

    def options(self, section: str) -> list[str]:
        """Return all options visible in ``section``, including inherited."""
        if section not in self._data:
            raise IniError(f"unknown section: {section!r}")
        seen: dict[str, None] = {}
        for ancestor in self._inheritance_chain(section):
            for key in self._data[ancestor]:
                seen.setdefault(key, None)
        return list(seen)

    def has_option(self, section: str, key: str) -> bool:
        """Return True if ``key`` resolves in ``section`` (own or inherited)."""
        if section not in self._data:
            return False
        for ancestor in self._inheritance_chain(section):
            if key in self._data[ancestor]:
                return True
        return False

    def get(
        self,
        section: str,
        key: str,
        *,
        fallback: object = _MISSING,
        raw: bool = False,
    ) -> str:
        """Return the value of ``key`` in ``section``, with interpolation.

        Falls back to inherited parents. Pass ``raw=True`` to skip
        ``${...}`` substitution. If ``fallback`` is provided, it is
        returned (without interpolation) when the section or key is
        missing; otherwise an :class:`IniError` is raised.
        """
        if section not in self._data:
            if fallback is not _MISSING:
                return fallback  # type: ignore[return-value]
            raise IniError(f"unknown section: {section!r}")
        for ancestor in self._inheritance_chain(section):
            if key in self._data[ancestor]:
                value = self._data[ancestor][key]
                if raw:
                    return value
                return self._interpolate(value, section, ())
        if fallback is not _MISSING:
            return fallback  # type: ignore[return-value]
        raise IniError(f"unknown key {key!r} in section {section!r}")

    def items(
        self, section: str, *, raw: bool = False
    ) -> list[tuple[str, str]]:
        """Return ``(key, value)`` pairs for every visible option."""
        return [
            (key, self.get(section, key, raw=raw))
            for key in self.options(section)
        ]

    def to_dict(self, *, raw: bool = False) -> dict[str, dict[str, str]]:
        """Materialize the config (with inheritance) into a plain dict."""
        return {section: dict(self.items(section, raw=raw)) for section in self._data}

    # -- internals ------------------------------------------------------

    def _add_section(
        self, name: str, parents: Sequence[str], *, line: int | None
    ) -> None:
        if name in self._data:
            if self._strict:
                raise ParseError(
                    f"duplicate section: {name!r}", line=line
                )
            return
        self._data[name] = {}
        self._parents[name] = list(parents)

    def _add_value(
        self, section: str, key: str, value: str, *, line: int | None
    ) -> None:
        if key in self._data[section] and self._strict:
            raise ParseError(
                f"duplicate key {key!r} in section {section!r}",
                line=line,
            )
        self._data[section][key] = value

    def _append_continuation(self, section: str, key: str, value: str) -> None:
        self._data[section][key] += "\n" + value

    def _inheritance_chain(self, section: str) -> list[str]:
        order: list[str] = []
        seen: set[str] = set()
        self._visit_chain(section, order, seen)
        return order

    def _visit_chain(
        self, name: str, order: list[str], seen: set[str]
    ) -> None:
        if name in seen or name not in self._data:
            return
        seen.add(name)
        order.append(name)
        for parent in self._parents.get(name, ()):
            self._visit_chain(parent, order, seen)

    def _interpolate(
        self, value: str, section: str, stack: tuple[str, ...]
    ) -> str:
        if len(stack) > _MAX_INTERP_DEPTH:
            raise InterpolationError(
                f"interpolation depth exceeded at {stack[-1]!r}"
            )

        def replace(match: "re.Match[str]") -> str:
            return self._resolve_ref(match, section, stack)

        return _INTERP_RE.sub(replace, value)

    def _resolve_ref(
        self,
        match: "re.Match[str]",
        section: str,
        stack: tuple[str, ...],
    ) -> str:
        ref = match.group(1).strip()
        if not ref:
            raise InterpolationError("empty interpolation: '${}'")
        target_section, target_key = self._split_ref(ref, section)
        ref_id = f"{target_section}:{target_key}"
        if ref_id in stack:
            chain = " -> ".join(stack + (ref_id,))
            raise InterpolationError(f"circular interpolation: {chain}")
        raw_value = self._raw_lookup(target_section, target_key)
        if raw_value is None:
            if self._strict:
                raise InterpolationError(f"unknown reference: {ref_id}")
            return match.group(0)
        return self._interpolate(raw_value, target_section, stack + (ref_id,))

    def _split_ref(self, ref: str, default_section: str) -> tuple[str, str]:
        if ":" in ref:
            section_part, key_part = ref.split(":", 1)
            return section_part.strip(), key_part.strip()
        return default_section, ref

    def _raw_lookup(self, section: str, key: str) -> str | None:
        if section not in self._data:
            return None
        for ancestor in self._inheritance_chain(section):
            if key in self._data[ancestor]:
                return self._data[ancestor][key]
        return None


def parse(text: str, *, strict: bool = True) -> Config:
    """Parse INI ``text`` and return a :class:`Config`.

    Comments start with ``;`` or ``#``. Sections are ``[name]`` or
    ``[name : parent1, parent2]``. Keys may use ``=`` or ``:`` as the
    separator (the first occurrence wins). Continuation lines start
    with whitespace and append to the most recent key with a literal
    newline. ``strict=False`` downgrades duplicate sections, duplicate
    keys, unknown parent inheritance, and missing ``${...}`` references
    from errors into accept-last / leave-literal behaviour.
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be str, got {type(text).__name__}")
    config = Config(strict=strict)
    state: _ParseState = _ParseState()
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        _process_line(raw_line, lineno, config, state)
    if strict:
        _verify_parents(config)
    return config


def parse_file(
    path: str | os.PathLike[str],
    *,
    strict: bool = True,
    encoding: str = "utf-8",
) -> Config:
    """Read ``path`` and parse it as INI text."""
    with open(path, encoding=encoding) as handle:
        return parse(handle.read(), strict=strict)


def dumps(config: Config) -> str:
    """Serialize ``config`` back to INI text.

    Direct keys are emitted; inherited keys are not duplicated. Values
    containing newlines are written as continuation lines so a round
    trip with ``parse`` recovers the same data. Comments are not
    preserved.
    """
    if not isinstance(config, Config):
        raise TypeError("dumps() requires a Config instance")
    chunks: list[str] = []
    for section in config._data:
        chunks.append(_format_section(section, config))
    if not chunks:
        return ""
    return "\n".join(chunks).rstrip() + "\n"


def _format_section(section: str, config: Config) -> str:
    parents = config._parents.get(section, [])
    if parents:
        header = f"[{section} : {', '.join(parents)}]"
    else:
        header = f"[{section}]"
    lines = [header]
    for key, value in config._data[section].items():
        value_lines = value.split("\n")
        lines.append(f"{key} = {value_lines[0]}")
        for cont in value_lines[1:]:
            lines.append(f"    {cont}")
    lines.append("")
    return "\n".join(lines)


def _verify_parents(config: Config) -> None:
    for section, parents in config._parents.items():
        for parent in parents:
            if parent not in config._data:
                raise ParseError(
                    f"section {section!r} inherits from unknown parent {parent!r}"
                )


class _ParseState:
    __slots__ = ("section", "last_key")

    def __init__(self) -> None:
        self.section: str | None = None
        self.last_key: str | None = None


def _process_line(
    raw_line: str,
    lineno: int,
    config: Config,
    state: _ParseState,
) -> None:
    line = raw_line.rstrip()
    if not line:
        state.last_key = None
        return
    stripped = line.lstrip()
    if stripped.startswith((";", "#")):
        state.last_key = None
        return
    if line[0] in (" ", "\t"):
        _handle_continuation(stripped, lineno, config, state)
        return
    if stripped.startswith("["):
        _handle_section(stripped, lineno, config, state)
        return
    _handle_kv(stripped, lineno, config, state)


def _handle_continuation(
    stripped: str, lineno: int, config: Config, state: _ParseState
) -> None:
    if state.section is None or state.last_key is None:
        raise ParseError(
            "continuation line without preceding key", line=lineno
        )
    config._append_continuation(state.section, state.last_key, stripped)


def _handle_section(
    stripped: str, lineno: int, config: Config, state: _ParseState
) -> None:
    if not stripped.endswith("]"):
        raise ParseError("unterminated section header", line=lineno)
    match = _SECTION_RE.match(stripped)
    if match is None:
        raise ParseError("malformed section header", line=lineno)
    name = match.group("name").strip()
    if not name:
        raise ParseError("empty section name", line=lineno)
    parents_raw = match.group("parents")
    parents = (
        [p.strip() for p in parents_raw.split(",") if p.strip()]
        if parents_raw is not None
        else []
    )
    config._add_section(name, parents, line=lineno)
    state.section = name
    state.last_key = None


def _handle_kv(
    stripped: str,
    lineno: int,
    config: Config,
    state: _ParseState,
) -> None:
    if state.section is None:
        raise ParseError(
            "key/value before any section header", line=lineno
        )
    key_raw, sep, value_raw = _split_key_value(stripped)
    if not sep:
        raise ParseError("expected '=' or ':' in key/value line", line=lineno)
    key = key_raw.strip()
    if not key:
        raise ParseError("empty key", line=lineno)
    value = value_raw.strip()
    config._add_value(state.section, key, value, line=lineno)
    state.last_key = key


def _split_key_value(line: str) -> tuple[str, str, str]:
    eq_index = line.find("=")
    colon_index = line.find(":")
    if eq_index == -1 and colon_index == -1:
        return line, "", ""
    if eq_index == -1:
        index = colon_index
    elif colon_index == -1:
        index = eq_index
    else:
        index = min(eq_index, colon_index)
    return line[:index], line[index], line[index + 1 :]
