from __future__ import annotations

from pathlib import Path


def expand_user_path(value: str | Path) -> Path:
    return Path(value).expanduser()
