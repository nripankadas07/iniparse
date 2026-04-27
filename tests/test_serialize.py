"""Serialization (dumps) and parse_file round-trip behaviour."""

from __future__ import annotations

import pytest

from iniparse import Config, dumps, parse, parse_file


def test_dumps_empty_config_returns_empty_string() -> None:
    assert dumps(Config()) == ""


def test_dumps_single_section_uses_equals_separator() -> None:
    text = "[s]\nk = v\n"
    assert dumps(parse(text)) == text


def test_dumps_preserves_section_order() -> None:
    text = "[b]\nx = 1\n\n[a]\ny = 2\n"
    expected = "[b]\nx = 1\n\n[a]\ny = 2\n"
    assert dumps(parse(text)) == expected


def test_dumps_writes_inheritance_header() -> None:
    text = "[base]\nk = 1\n[child : base]\nx = 2\n"
    out = dumps(parse(text))
    assert "[child : base]" in out


def test_dumps_writes_multiple_parents_separated_by_comma() -> None:
    text = "[a]\nk=1\n[b]\nk=2\n[c : a, b]\nx=3\n"
    out = dumps(parse(text))
    assert "[c : a, b]" in out


def test_dumps_emits_continuation_lines_for_multiline_values() -> None:
    text = "[s]\nmessage = first\n  second\n  third\n"
    config = parse(text)
    assert config.get("s", "message") == "first\nsecond\nthird"
    out = dumps(config)
    assert "message = first" in out
    assert "    second" in out
    assert "    third" in out


def test_dumps_round_trip_preserves_data() -> None:
    text = (
        "[base]\nhost = localhost\nport = 80\n"
        "[web : base]\npath = /\nport = 8080\n"
    )
    first = parse(text)
    serialized = dumps(first)
    second = parse(serialized)
    assert first.to_dict() == second.to_dict()


def test_dumps_does_not_duplicate_inherited_keys() -> None:
    text = "[base]\nk = 1\n[child : base]\nk = 2\nx = 3\n"
    out = dumps(parse(text))
    # base's `k` and child's `k` are different lines; child should not
    # also include base's `k = 1` again.
    assert out.count("k = 1") == 1
    assert "k = 2" in out


def test_dumps_rejects_non_config_argument() -> None:
    with pytest.raises(TypeError):
        dumps({"s": {"k": "v"}})  # type: ignore[arg-type]


def test_parse_file_reads_from_disk(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "settings.ini"
    path.write_text("[s]\nname = file\n")
    assert parse_file(path).get("s", "name") == "file"


def test_parse_file_supports_strict_false(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "settings.ini"
    path.write_text("[s]\nk = 1\nk = 2\n")
    assert parse_file(path, strict=False).get("s", "k") == "2"


def test_parse_file_with_custom_encoding(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "settings.ini"
    path.write_text("[π]\nμ = αβγ\n", encoding="utf-16")
    assert parse_file(path, encoding="utf-16").get("π", "μ") == "αβγ"
