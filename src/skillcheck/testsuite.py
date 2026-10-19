from __future__ import annotations

import json
from pathlib import Path

from .manifest import Manifest


def _load_spec(root: Path) -> dict | None:
    for name in ("skill-tests.json", ".skillcheck/tests.json"):
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("test specification must not be a symlink")
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def run(manifest: Manifest) -> list[dict]:
    results: list[dict] = []
    spec = _load_spec(manifest.root)
    if spec is None:
        return results
    if not isinstance(spec, dict) or "cases" not in spec:
        return [{"name": "test-spec", "passed": False, "message": "test spec must be an object with cases"}]
    cases = spec["cases"]
    if not isinstance(cases, list):
        return [{"name": "test-spec", "passed": False, "message": "cases must be a list"}]
    for index, case in enumerate(cases, 1):
        if not isinstance(case, dict):
            results.append({"name": f"case-{index}", "passed": False, "message": "case must be an object"})
            continue
        name = str(case.get("name", f"case-{index}"))
        contains, forbid = case.get("contains", []), case.get("forbid", [])
        if any(not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value)
               for value in (contains, forbid)) or not (contains or forbid):
            results.append({"name": name, "passed": False, "message": "contains/forbid must be lists of nonempty strings with at least one assertion"})
            continue
        file_name = case.get("file")
        if not isinstance(file_name, str):
            results.append({"name": name, "passed": False, "message": "file is required"})
            continue
        path = (manifest.root / file_name).resolve()
        try:
            path.relative_to(manifest.root)
        except ValueError:
            results.append({"name": name, "passed": False, "message": "file escapes skill root"})
            continue
        if not path.is_file():
            results.append({"name": name, "passed": False, "message": f"missing file: {file_name}"})
            continue
        text = path.read_text(encoding="utf-8")
        missing = [str(item) for item in case.get("contains", []) if str(item) not in text]
        forbidden = [str(item) for item in case.get("forbid", []) if str(item) in text]
        passed = not missing and not forbidden
        message = "passed" if passed else "; ".join(
            ([f"missing: {', '.join(missing)}"] if missing else [])
            + ([f"forbidden: {', '.join(forbidden)}"] if forbidden else [])
        )
        results.append({"name": name, "passed": passed, "message": message})
    return results
