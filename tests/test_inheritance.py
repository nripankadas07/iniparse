"""Section inheritance: depth-first lookup, multiple parents, overrides."""

from __future__ import annotations

import pytest

from iniparse import IniError, parse


def test_single_parent_inheritance_resolves_keys() -> None:
    text = "[base]\nhost = localhost\nport = 80\n[web : base]\npath = /\n"
    config = parse(text)
    assert config.get("web", "host") == "localhost"
    assert config.get("web", "port") == "80"
    assert config.get("web", "path") == "/"


def test_child_overrides_parent_value() -> None:
    text = "[base]\nport = 80\n[web : base]\nport = 8080\n"
    assert parse(text).get("web", "port") == "8080"


def test_parents_listed_via_public_api() -> None:
    text = "[base]\nk = 1\n[child : base]\n"
    assert parse(text).parents("child") == ["base"]


def test_multiple_parents_resolved_in_declaration_order() -> None:
    text = (
        "[a]\nshared = from_a\nonly_a = 1\n"
        "[b]\nshared = from_b\nonly_b = 2\n"
        "[child : a, b]\nname = child\n"
    )
    config = parse(text)
    assert config.get("child", "shared") == "from_a"
    assert config.get("child", "only_a") == "1"
    assert config.get("child", "only_b") == "2"
    assert config.get("child", "name") == "child"


def test_grandparent_inheritance_via_chain() -> None:
    text = (
        "[grand]\nroot = g\n"
        "[middle : grand]\nmid = m\n"
        "[leaf : middle]\nleaf = l\n"
    )
    config = parse(text)
    assert config.get("leaf", "root") == "g"
    assert config.get("leaf", "mid") == "m"
    assert config.get("leaf", "leaf") == "l"


def test_options_includes_inherited_keys_without_duplicates() -> None:
    text = "[a]\nx = 1\ny = 2\n[b : a]\ny = 3\nz = 4\n"
    assert parse(text).options("b") == ["y", "z", "x"]


def test_has_option_walks_inheritance_chain() -> None:
    text = "[a]\nshared = 1\n[b : a]\n"
    config = parse(text)
    assert config.has_option("b", "shared") is True
    assert config.has_option("b", "missing") is False


def test_circular_inheritance_does_not_loop() -> None:
    text = "[a : b]\nfrom_a = 1\n[b : a]\nfrom_b = 2\n"
    config = parse(text, strict=False)
    assert config.get("a", "from_b") == "2"
    assert config.get("b", "from_a") == "1"


def test_self_inheritance_is_silently_ignored() -> None:
    text = "[a : a]\nk = v\n"
    assert parse(text, strict=False).get("a", "k") == "v"


def test_items_uses_inherited_values() -> None:
    text = "[a]\nx = 1\n[b : a]\ny = 2\n"
    items = parse(text).items("b")
    assert items == [("y", "2"), ("x", "1")]


def test_parents_separator_with_extra_whitespace() -> None:
    text = "[a]\nk=1\n[b]\nk=2\n[c :   a ,   b   ]\nx=1\n"
    assert parse(text).parents("c") == ["a", "b"]


def test_inheritance_skips_blank_parent_entries() -> None:
    text = "[a]\nk=1\n[child : a, , ]\nx=1\n"
    assert parse(text).parents("child") == ["a"]


def test_to_dict_includes_inherited_keys() -> None:
    text = "[a]\nx = 1\n[b : a]\ny = 2\n"
    assert parse(text).to_dict() == {
        "a": {"x": "1"},
        "b": {"y": "2", "x": "1"},
    }


def test_get_unknown_key_with_inheritance_chain_still_raises() -> None:
    text = "[a]\nx = 1\n[b : a]\ny = 2\n"
    with pytest.raises(IniError):
        parse(text).get("b", "missing")
