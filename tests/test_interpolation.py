"""``${...}`` interpolation: same-section, cross-section, recursion, errors."""

from __future__ import annotations

import pytest

from iniparse import InterpolationError, parse


def test_same_section_interpolation() -> None:
    text = "[s]\nname = world\ngreeting = hello ${name}\n"
    assert parse(text).get("s", "greeting") == "hello world"


def test_cross_section_interpolation() -> None:
    text = "[net]\nhost = example.com\n[web]\nurl = http://${net:host}/\n"
    assert parse(text).get("web", "url") == "http://example.com/"


def test_inherited_value_can_reference_inherited_key() -> None:
    text = "[base]\nname = base\nfull = ${name}-suffix\n[child : base]\n"
    assert parse(text).get("child", "full") == "base-suffix"


def test_inheritance_chain_used_for_interpolation_targets() -> None:
    text = "[base]\nname = base\n[child : base]\nlabel = ${name}!\n"
    assert parse(text).get("child", "label") == "base!"


def test_recursive_interpolation_expands_until_fixed_point() -> None:
    text = "[s]\na = ${b}\nb = ${c}\nc = leaf\n"
    assert parse(text).get("s", "a") == "leaf"


def test_multiple_references_in_one_value() -> None:
    text = "[s]\nuser = alice\nhost = example.com\nemail = ${user}@${host}\n"
    assert parse(text).get("s", "email") == "alice@example.com"


def test_raw_skips_interpolation() -> None:
    text = "[s]\nname = world\ngreeting = hi ${name}\n"
    config = parse(text)
    assert config.get("s", "greeting", raw=True) == "hi ${name}"


def test_items_raw_skips_interpolation() -> None:
    text = "[s]\nname = world\ngreeting = hi ${name}\n"
    items = parse(text).items("s", raw=True)
    assert ("greeting", "hi ${name}") in items


def test_circular_reference_raises_with_helpful_chain() -> None:
    text = "[s]\na = ${b}\nb = ${a}\n"
    with pytest.raises(InterpolationError) as info:
        parse(text).get("s", "a")
    assert "circular" in str(info.value)


def test_self_reference_is_circular() -> None:
    text = "[s]\nk = ${k}\n"
    with pytest.raises(InterpolationError):
        parse(text).get("s", "k")


def test_missing_reference_raises_in_strict_mode() -> None:
    text = "[s]\ngreeting = hi ${missing}\n"
    with pytest.raises(InterpolationError) as info:
        parse(text).get("s", "greeting")
    assert "missing" in str(info.value)


def test_missing_reference_left_literal_in_lax_mode() -> None:
    text = "[s]\ngreeting = hi ${missing}\n"
    assert parse(text, strict=False).get("s", "greeting") == "hi ${missing}"


def test_missing_cross_section_reference_raises_in_strict_mode() -> None:
    text = "[s]\nx = ${other:k}\n"
    with pytest.raises(InterpolationError):
        parse(text).get("s", "x")


def test_missing_cross_section_reference_left_literal_in_lax_mode() -> None:
    text = "[s]\nx = ${other:k}\n"
    assert parse(text, strict=False).get("s", "x") == "${other:k}"


def test_empty_reference_braces_raise() -> None:
    text = "[s]\nbad = ${}\n"
    with pytest.raises(InterpolationError):
        parse(text).get("s", "bad")


def test_whitespace_inside_reference_is_trimmed() -> None:
    text = "[s]\nname = world\ngreeting = hi ${  name  }\n"
    assert parse(text).get("s", "greeting") == "hi world"


def test_non_reference_dollar_text_is_preserved() -> None:
    text = "[s]\namount = $5.00\n"
    assert parse(text).get("s", "amount") == "$5.00"


def test_long_reference_chain_within_depth_limit() -> None:
    keys = [f"k{i}" for i in range(10)]
    body = "".join(f"{key} = ${{{next_key}}}\n" for key, next_key in zip(keys, keys[1:]))
    body += f"{keys[-1]} = end\n"
    text = "[s]\n" + body
    assert parse(text).get("s", "k0") == "end"


def test_overflow_chain_raises_interpolation_error() -> None:
    keys = [f"k{i}" for i in range(50)]
    body = "".join(f"{key} = ${{{next_key}}}\n" for key, next_key in zip(keys, keys[1:]))
    body += f"{keys[-1]} = end\n"
    text = "[s]\n" + body
    config = parse(text)
    # The value of the chain itself fits; force over the limit by
    # threading a back-reference to k0 mid-way to grow the stack.
    config._data["s"]["k25"] = "${k0}-${k26}"
    with pytest.raises(InterpolationError):
        config.get("s", "k0")
