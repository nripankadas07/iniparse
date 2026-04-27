"""Force pytest to put its tmpdirs under /tmp to avoid the mounted
workspace cleanup loop documented in the Night 19 learnings."""

from __future__ import annotations

import os


def pytest_configure(config: object) -> None:
    if any(part == "mnt" for part in os.getcwd().split(os.sep)):
        config.option.basetemp = "/tmp/pytest-run/iniparse"  # type: ignore[attr-defined]
