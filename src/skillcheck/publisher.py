from __future__ import annotations

import hashlib
import json
import re
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .files import skill_files
from .manifest import Manifest
from .report import issue_dicts
from .scanner import Issue


def publish(manifest: Manifest, issues: list[Issue], output: str | None = None) -> Path:
    if any(item.severity == "error" for item in issues):
        raise ValueError("cannot publish a skill with security or manifest errors")
    artifact_dir = manifest.root / ".skillcheck" / "artifacts"
    if artifact_dir.parent.is_symlink() or artifact_dir.is_symlink():
        raise ValueError("artifact directories must not be symlinks")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(output).resolve() if output else artifact_dir / f"{manifest.name}-{manifest.version}.tar.gz"
    if output_path.is_relative_to(manifest.root) and not output_path.is_relative_to(artifact_dir):
        raise ValueError("output inside the skill must be under .skillcheck/artifacts to avoid overwriting source files")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path = manifest.root / ".skillcheck" / "SECURITY-REPORT.json"
    if report_path.is_symlink():
        raise ValueError("security report must not be a symlink")
    report_path.write_text(json.dumps({"tool": "skillcheck", "version": __version__, "issues": issue_dicts(issues)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with tarfile.open(output_path, "w:gz") as archive:
        for path in [*skill_files(manifest.root), report_path]:
            relative = path.relative_to(manifest.root)
            if (not path.is_file() or path.is_symlink()
                    or path.resolve() == output_path):
                continue
            archive.add(path, arcname=f"{manifest.name}-{manifest.version}/{relative}")
    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    checksum = output_path.with_suffix(output_path.suffix + ".sha256")
    checksum.write_text(f"{digest}  {output_path.name}\n", encoding="utf-8")
    provenance = output_path.with_suffix(output_path.suffix + ".provenance.json")
    provenance.write_text(json.dumps({
        "schema_version": 1,
        "name": manifest.name,
        "version": manifest.version,
        "artifact": output_path.name,
        "sha256": digest,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tool": f"skillcheck/{__version__}",
        "source_manifest": manifest.path.name,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def verify_artifact(path: str | Path) -> tuple[bool, str]:
    artifact = Path(path).resolve()
    checksum = artifact.with_suffix(artifact.suffix + ".sha256")
    if not artifact.is_file():
        return False, f"artifact not found: {artifact}"
    if not checksum.is_file():
        return False, f"checksum not found: {checksum}"
    try:
        fields = checksum.read_text(encoding="utf-8").strip().split()
    except (OSError, UnicodeError):
        return False, "could not read checksum file"
    if not fields or not re.fullmatch(r"[0-9a-fA-F]{64}", fields[0]):
        return False, "invalid checksum file"
    expected = fields[0].lower()
    try:
        actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
    except OSError:
        return False, "could not read artifact"
    if expected != actual:
        return False, "SHA-256 checksum mismatch"
    provenance = artifact.with_suffix(artifact.suffix + ".provenance.json")
    if provenance.is_file():
        try:
            data = json.loads(provenance.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return False, "invalid provenance JSON"
        if not isinstance(data, dict) or data.get("sha256") != actual:
            return False, "provenance checksum mismatch"
    return True, actual
