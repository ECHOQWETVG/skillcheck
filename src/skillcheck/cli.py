from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .compat import KNOWN_AGENTS, check as check_compat
from .manifest import ManifestError, load_manifest, validate_manifest
from .publisher import publish, verify_artifact
from .report import dumps_json, issue_dicts, sarif
from .scanner import Issue, scan
from .testsuite import run as run_tests


def _all_issues(root: str | Path, agent: str | None = None):
    manifest = load_manifest(root)
    issues: list[Issue | dict] = validate_manifest(manifest)
    issues.extend(scan(manifest))
    issues.extend(check_compat(manifest, agent))
    return manifest, issues


def _has_errors(issues: list[Issue | dict], strict: bool = False) -> bool:
    for item in issues:
        severity = item["severity"] if isinstance(item, dict) else item.severity
        if severity == "error" or (strict and severity == "warning"):
            return True
    return False


def _print_issues(issues: list[Issue | dict], output: str, strict: bool = False) -> None:
    values = issue_dicts(issues)
    if output == "json":
        print(dumps_json({"issues": values, "ok": not _has_errors(issues, strict)}), end="")
    elif output == "sarif":
        print(dumps_json(sarif(issues, __version__)), end="")
    elif not values:
        print("OK: no issues found")
    else:
        for item in values:
            location = ""
            if item.get("path"):
                location = f" ({item['path']}{':' + str(item['line']) if item.get('line') else ''})"
            print(f"{item['severity'].upper():7} {item['code']}: {item['message']}{location}")


def _cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()) and not args.force:
        print(f"directory is not empty: {root}; use --force to continue", file=sys.stderr)
        return 2
    manifest = """schema_version: 1
name: hello-skill
version: 0.1.0
description: A small cross-agent skill
license: MIT
compatibility:
  agents:
    - claude-code
    - codex
    - cursor
permissions:
  shell: false
  network: false
  write_files: false
entrypoints:
  files:
    - SKILL.md
"""
    skill = """---
name: hello-skill
description: A small cross-agent skill
---

# Hello Skill

Explain the task, inspect the existing project, and make the smallest safe change.
"""
    (root / "skill.yaml").write_text(manifest, encoding="utf-8")
    (root / "SKILL.md").write_text(skill, encoding="utf-8")
    print(f"created {root}")
    return 0


def _cmd_lint(args: argparse.Namespace) -> int:
    try:
        _, issues = _all_issues(args.path, args.agent)
    except (ManifestError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    _print_issues(issues, args.format, args.strict)
    return 1 if _has_errors(issues, args.strict) else 0


def _cmd_test(args: argparse.Namespace) -> int:
    try:
        manifest, issues = _all_issues(args.path, args.agent)
        tests = run_tests(manifest)
    except (ManifestError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    failed = [item for item in tests if not item["passed"]]
    if args.format == "text":
        _print_issues(issues, "text", args.strict)
        if not tests:
            print("TEST: no skill-tests.json found; manifest and security checks completed")
        for item in tests:
            print(f"{'PASS' if item['passed'] else 'FAIL'} {item['name']}: {item['message']}")
    elif args.format == "json":
        payload = {"issues": issue_dicts(issues), "tests": tests, "ok": not _has_errors(issues, args.strict) and not failed}
        print(dumps_json(payload), end="")
    else:
        report_issues = list(issues)
        report_issues.extend({"code": "test.failed", "severity": "error", "message": item["message"], "path": "skill-tests.json"} for item in failed)
        print(dumps_json(sarif(report_issues, __version__)), end="")
    return 1 if _has_errors(issues, args.strict) or failed else 0


def _cmd_compat(args: argparse.Namespace) -> int:
    try:
        manifest = load_manifest(args.path)
        issues = check_compat(manifest, args.agent)
    except (ManifestError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    _print_issues(issues, args.format)
    return 1 if issues else 0


def _cmd_publish(args: argparse.Namespace) -> int:
    try:
        manifest, issues = _all_issues(args.path)
        if _has_errors(issues, strict=True):
            _print_issues(issues, "text", strict=True)
            print("ERROR: fix all findings before publishing", file=sys.stderr)
            return 1
        failed_tests = [item for item in run_tests(manifest) if not item["passed"]]
        if failed_tests:
            for item in failed_tests:
                print(f"FAIL {item['name']}: {item['message']}", file=sys.stderr)
            print("ERROR: fix failing tests before publishing", file=sys.stderr)
            return 1
        scanner_issues = [item for item in issues if isinstance(item, Issue)]
        artifact = publish(manifest, scanner_issues, args.output)
    except (ManifestError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"published {artifact}")
    print(f"sha256 {artifact}.sha256")
    print(f"provenance {artifact}.provenance.json")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    ok, message = verify_artifact(args.artifact)
    print(("OK: " if ok else "ERROR: ") + message)
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skillcheck", description="Quality and security gates for AI agent skills")
    parser.add_argument("--version", action="version", version=f"skillcheck {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="create a starter skill")
    init.add_argument("directory", nargs="?", default=".")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=_cmd_init)

    for name, help_text in (("lint", "validate and scan a skill"), ("test", "run declarative skill tests")):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("path", nargs="?", default=".")
        command.add_argument("--format", choices=("text", "json", "sarif"), default="text")
        command.add_argument("--strict", action="store_true", help="treat warnings as failures")
        command.add_argument("--agent", help="check compatibility with one agent")
        command.set_defaults(func=_cmd_lint if name == "lint" else _cmd_test)

    compat = sub.add_parser("compat", help="check declared agent compatibility")
    compat.add_argument("path", nargs="?", default=".")
    compat.add_argument("--agent", choices=sorted(KNOWN_AGENTS), required=True)
    compat.add_argument("--format", choices=("text", "json", "sarif"), default="text")
    compat.set_defaults(func=_cmd_compat)

    package = sub.add_parser("publish", help="build a validated local artifact")
    package.add_argument("path", nargs="?", default=".")
    package.add_argument("--output")
    package.set_defaults(func=_cmd_publish)

    verify = sub.add_parser("verify", help="verify an artifact checksum and provenance")
    verify.add_argument("artifact")
    verify.set_defaults(func=_cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
