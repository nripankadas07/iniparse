# iniparse

Zero-dependency INI/config parser for Python with section inheritance,
`${...}` interpolation, typed errors, and round-trip serialization.

It is intentionally small: useful when `configparser` is more permissive or
stateful than you want, and when pulling in a full configuration framework would
be overkill.

## Install

From a repository checkout:

```bash
python -m pip install -e .
```

## Quick Start

```python
from iniparse import parse

config = parse("""
[default]
host = localhost
port = 5432

[prod:default]
host = db.internal
url = postgres://${host}:${port}/app
""")

config["prod"]["host"]  # "db.internal"
config["prod"]["port"]  # "5432"
config["prod"]["url"]   # "postgres://db.internal:5432/app"
```

## API

- `parse(text)` parses an INI string into a `Config`.
- `parse_file(path)` reads UTF-8 text from disk and parses it.
- `dumps(config)` serializes a `Config` back to INI text.
- `Config` behaves like a section mapping with inherited values resolved.
- `IniError`, `ParseError`, and `InterpolationError` distinguish syntax,
  lookup, and interpolation failures.

## Scope

Supported features include comments, sections, `key = value` assignments,
section inheritance with `[child:parent]`, and `${name}` interpolation. The
library does not try to be a full application-settings framework: it leaves
schema validation, environment loading, and type coercion to callers.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
```

## License

MIT - see [LICENSE](./LICENSE).
