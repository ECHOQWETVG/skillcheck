"""The shared inventory used by scanning and packaging."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator


IGNORED_DIRS = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", ".pytest_cache"}
TEST_SPECS = {"skill-tests.json", ".skillcheck/tests.json"}


def skill_files(root: Path) -> Iterator[Path]:
    def on_error(error: OSError) -> None:
        raise error

    for directory, directories, files in os.walk(root, followlinks=False, onerror=on_error):
        base = Path(directory)
        for name in sorted(directories[:]):
            path = base / name
            if name in IGNORED_DIRS:
                directories.remove(name)
            elif path.is_symlink():
                directories.remove(name)
                yield path
            elif name == ".skillcheck":
                directories.remove(name)
                tests = path / "tests.json"
                if tests.exists() or tests.is_symlink():
                    yield tests
        for name in sorted(files):
            yield base / name
