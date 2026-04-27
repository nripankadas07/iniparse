"""Parse-error surface and strict/lax mode behaviour."""

from __future__ import annotations

import pytest

from iniparse import IniError, ParseError, parse


def test_parse_rejects_non_string_text() -> None:
    with pytest.raises(TypeError):
        parse(b"[s]\nk=v\n")  # type: ignore[arg-type]


def test_unterminated_section_header_raises() -> None:
    with pytest.raises(ParseError) as info:
        parse("[server\nhost = localhost\n")
    assert info.value.line == 1


def test_empty_section_name_raises() -> None:
    with pytest.raises(ParseError) as info:
        parse("[ ]\n")
    assert info.value.line == 1


def test_kv_before_first_section_raises() -> None:
    with pytest.raises(ParseError) as info:
        parse("orphan = 1\n")
    assert info.value.line == 1


def test_line_without_separator_raises() -> None:
    with pytest.raises(ParseError) as info:
        parse("[s]\nbadline\n")
    assert info.value.line == 2


def test_empty_key_raises() -> None:
    with pytest.raises(ParseError) as info:
        parse("[s]\n=value\n")
    assert info.value.line == 2


def test_continuation_without_prior_key_raises() -> None:
    with pytest.raises(ParseError) as info:
        parse("[s]\n   continuation = oops\n")
    assert info.value.line == 2


def test_strict_mode_rejects_duplicate_section() -> None:
    with pytest.raises(ParseError):
        parse("[s]\na = 1\n[s]\nb = 2\n")


def test_lax_mode_keeps_first_section_and_appends_keys() -> None:
    config = parse("[s]\na = 1\n[s]\nb = 2\n", strict=False)
    assert config.sections() == ["s"]
    assert config.get("s", "a") == "1"
    assert config.get("s", "b") == "2"


def test_strict_mode_rejects_duplicate_key() -> None:
    with pytest.raises(ParseError):
        parse("[s]\nk = 1\nk = 2\n")


def test_lax_mode_keeps_last_value_for_duplicate_key() -> None:
    config = parse("[s]\nk = 1\nk = 2\n", strict=False)
    assert config.get("s", "k") == "2"


def test_strict_mode_rejects_unknown_parent() -> None:
    with pytest.raises(ParseError) as info:
        parse("[child : missing]\nk = v\n")
    assert "missing" in str(info.value)


def test_lax_mode_keeps_unknown_parent_silently() -> None:
    config = parse("[child : missing]\nk = v\n", strict=False)
    assert config.get("child", "k") == "v"


def test_parse_error_carries_line_number_in_message() -> None:
    try:
        parse("[s]\n[bad\n")
    except ParseError as err:
        assert "line 2" in str(err)
        assert err.line == 2
    else:
        pytest.fail("expected ParseError")


def test_parse_error_without_line_omits_prefix() -> None:
    err = ParseError("standalone")
    assert str(err) == "standalone"
    assert err.line is None


def test_unknown_section_for_options_uses_iniError() -> None:
    config = parse("")
    with pytest.raises(IniError):
        config.options("missing")


def test_parents_for_unknown_section_raises() -> None:
    config = parse("")
    with pytest.raises(IniError):
        config.parents("missing")


def test_section_header_with_extra_brackets_is_rejected() -> None:
    with pytest.raises(ParseError):
        parse("[[s]]\nk = 1\n")
