from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .yamlmini import MiniYAMLError, load as load_yaml


MANIFEST_NAMES = ("skill.yaml", "skill.yml", "skill.json", "skill.toml")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


class ManifestError(ValueError):
    pass


@dataclass
class Manifest:
    root: Path
    path: Path
    data: dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.data.get("name", ""))

    @property
    def version(self) -> str:
        return str(self.data.get("version", ""))

    def get(self, *keys: str, default: Any = None) -> Any:
        value: Any = self.data
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value

    def declared_files(self) -> list[str]:
        files = self.get("entrypoints", "files", default=[])
        if isinstance(files, str):
            return [files]
        return [str(item) for item in files] if isinstance(files, list) else []


def discover(root: Path) -> Path:
    root = root.resolve()
    found = [root / name for name in MANIFEST_NAMES if (root / name).is_file()]
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        names = ", ".join(path.name for path in found)
        raise ManifestError(f"multiple manifests found: {names}; keep exactly one")
    raise ManifestError(f"no manifest found; expected one of: {', '.join(MANIFEST_NAMES)}")


def load_manifest(root: str | Path) -> Manifest:
    root_path = Path(root).resolve()
    if root_path.is_file():
        path = root_path
        root_path = path.parent
    else:
        path = discover(root_path)
    try:
        if path.suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix == ".toml":
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        else:
            data = load_yaml(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, tomllib.TOMLDecodeError, MiniYAMLError) as exc:
        raise ManifestError(f"could not read {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError("manifest root must be an object")
    return Manifest(root_path, path, data)


def validate_manifest(manifest: Manifest) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    def add(code: str, message: str, severity: str = "error", path: str | None = None) -> None:
        item: dict[str, Any] = {"code": code, "message": message, "severity": severity}
        if path:
            item["path"] = path
        issues.append(item)

    data = manifest.data
    if data.get("schema_version") not in (1, "1"):
        add("manifest.schema", "schema_version must be 1")
    if not isinstance(data.get("name"), str) or not NAME_RE.fullmatch(data["name"]):
        add("manifest.name", "name must match [a-z0-9][a-z0-9._-]{1,63}", path="name")
    if not isinstance(data.get("version"), str) or not VERSION_RE.fullmatch(data["version"]):
        add("manifest.version", "version must be semantic versioning, such as 1.2.3", path="version")
    if not isinstance(data.get("description"), str) or not data["description"].strip():
        add("manifest.description", "description is required", path="description")
    if not isinstance(data.get("license"), str) or not data["license"].strip():
        add("manifest.license", "license is required", path="license")

    compatibility = data.get("compatibility", {})
    if not isinstance(compatibility, dict):
        add("manifest.compatibility", "compatibility must be an object", path="compatibility")
    else:
        agents = compatibility.get("agents", [])
        if not isinstance(agents, (list, str)):
            add("manifest.agents", "compatibility.agents must be a list or '*'")
        elif isinstance(agents, list) and not agents:
            add("manifest.agents", "declare at least one supported agent")

    permissions = data.get("permissions", {})
    if not isinstance(permissions, dict):
        add("manifest.permissions", "permissions must be an object", path="permissions")
    else:
        for key in ("shell", "network", "write_files"):
            if key in permissions and not isinstance(permissions[key], bool):
                add("manifest.permission_type", f"permissions.{key} must be true or false", path=f"permissions.{key}")

    if not manifest.declared_files():
        add("manifest.entrypoints", "entrypoints.files must list at least one file", path="entrypoints.files")
    for file_name in manifest.declared_files():
        candidate = (manifest.root / file_name).resolve()
        try:
            candidate.relative_to(manifest.root)
        except ValueError:
            add("manifest.path_traversal", f"declared file escapes skill root: {file_name}", path=file_name)
        else:
            if not candidate.is_file():
                add("manifest.missing_file", f"declared file does not exist: {file_name}", path=file_name)
    return issues
