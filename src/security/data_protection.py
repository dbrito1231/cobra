"""OS-level file permission enforcement for C.O.B.R.A. data stores."""

from __future__ import annotations

import os
import stat
from pathlib import Path


def ensure_user_permissions(path: Path) -> None:
    """Apply user-only permissions to a file or directory (DP6)."""

    path = Path(path).expanduser()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix or "." in path.name:
            path.touch()
        else:
            path.mkdir(parents=True, exist_ok=True)

    mode = stat.S_IRUSR | stat.S_IWUSR
    if path.is_dir():
        mode |= stat.S_IXUSR
    os.chmod(path, mode)


def protect_cobra_paths(root: Path) -> None:
    """Ensure standard C.O.B.R.A. directories use OS file permissions only."""

    root = Path(root).expanduser()
    categories = [
        root / "wiki",
        root / "memory",
        root / "config.yaml",
        root / "voice",
        root / "logs",
        root / "backups",
    ]
    for category in categories:
        ensure_user_permissions(category)
