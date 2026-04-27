"""Happy-path INI parsing: sections, keys, comments, blanks."""

from __future__ import annotations

import pytest

from iniparse import Config, IniError, parse


def test_empty_text_returns_empty_config() -> None:
    config = parse("")
    assert config.sections() == []


def test_only_blank_lines_and_comments_yield_no_sections() -> None:
    text = "\n\n   \n; a comment\n# another\n"
    config = parse(text)
    assert config.sections() == []


def test_simple_section_with_two_keys() -> None:
    text = "[server]\nhost = localhost\nport = 8080\n"
    config = parse(text)
    assert config.sections() == ["server"]
    assert config.get("server", "host") == "localhost"
    assert config.get("server", "port") == "8080"


def test_colon_separator_is_supported() -> None:
    config = parse("[s]\nname: example\n")
    assert config.get("s", "name") == "example"


def test_first_separator_wins() -> None:
    config = parse("[s]\nurl = http://example.com:8080\n")
    assert config.get("s", "url") == "http://example.com:8080"


def test_value_with_colon_then_equals_keeps_colon() -> None:
    config = parse("[s]\nfoo : bar=baz\n")
    assert config.get("s", "foo") == "bar=baz"


def test_inline_pound_in_value_is_preserved() -> None:
    config = parse("[s]\nweight = 5#1\n")
    assert config.get("s", "weight") == "5#1"


def test_keys_and_values_are_trimmed() -> None:
    config = parse("[s]\nkey   =   spaced value   \n")
    assert config.get("s", "key") == "spaced value"


def test_sections_keep_insertion_order() -> None:
    text = "[b]\nx = 1\n[a]\ny = 2\n[c]\nz = 3\n"
    assert parse(text).sections() == ["b", "a", "c"]


def test_options_returns_keys_in_insertion_order() -> None:
    text = "[s]\nb = 1\na = 2\nc = 3\n"
    assert parse(text).options("s") == ["b", "a", "c"]


def test_has_section_and_has_option() -> None:
    config = parse("[s]\nk = v\n")
    assert config.has_section("s") is True
    assert config.has_section("missing") is False
    assert config.has_option("s", "k") is True
    assert config.has_option("s", "missing") is False
    assert config.has_option("missing", "k") is False


def test_unicode_keys_and_values_round_trip_through_get() -> None:
    config = parse("[π]\nμ = αβγ\n")
    assert config.get("π", "μ") == "αβγ"


def test_in_operator_uses_section_membership() -> None:
    config = parse("[s]\nk=v\n")
    assert "s" in config
    assert "missing" not in config


def test_continuation_line_appends_with_newline() -> None:
    text = "[s]\nmessage = first\n  second\n  third\n"
    assert parse(text).get("s", "message") == "first\nsecond\nthird"


def test_blank_line_breaks_continuation() -> None:
    text = "[s]\nfoo = bar\n\n  not_a_continuation = oops\n"
    with pytest.raises(IniError):
        parse(text)


def test_get_with_fallback_when_section_missing() -> None:
    config = parse("[s]\nk = v\n")
    assert config.get("missing", "k", fallback="default") == "default"


def test_get_with_fallback_when_key_missing() -> None:
    config = parse("[s]\nk = v\n")
    assert config.get("s", "missing", fallback="default") == "default"


def test_get_without_fallback_raises_for_missing_section() -> None:
    config = parse("[s]\nk = v\n")
    with pytest.raises(IniError):
        config.get("missing", "k")


def test_get_without_fallback_raises_for_missing_key() -> None:
    config = parse("[s]\nk = v\n")
    with pytest.raises(IniError):
        config.get("s", "missing")


def test_items_returns_pairs_in_order() -> None:
    text = "[s]\nb = 1\na = 2\n"
    assert parse(text).items("s") == [("b", "1"), ("a", "2")]


def test_to_dict_materializes_all_sections() -> None:
    text = "[a]\nx = 1\n[b]\ny = 2\n"
    assert parse(text).to_dict() == {"a": {"x": "1"}, "b": {"y": "2"}}


def test_options_for_unknown_section_raises() -> None:
    config = parse("")
    with pytest.raises(IniError):
        config.options("missing")


def test_repr_shows_section_list() -> None:
    config = parse("[a]\n[b]\n")
    assert repr(config) == "Config(sections=['a', 'b'])"


def test_isinstance_check_is_true() -> None:
    assert isinstance(parse(""), Config)
