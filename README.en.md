# SkillCheck

[简体中文](README.md) | **English**

[![Package](https://github.com/ECHOQWETVG/skillcheck/actions/workflows/package.yml/badge.svg)](https://github.com/ECHOQWETVG/skillcheck/actions/workflows/package.yml)

SkillCheck is a local-first quality and security gate for AI agent skills. It checks a skill before it is shared with Claude Code, Codex, Cursor, OpenCode, or another compatible agent.

**Alpha release.** Compatibility checks validate the agents declared in your manifest; they do not run those agents or certify runtime compatibility. Security checks use static patterns and may have false positives and false negatives.

It does not need a website, account, database, model API, or hosted execution service. A skill is a normal Git repository. SkillCheck runs locally or in GitHub Actions and produces an integrity-checked archive that can be attached to a normal GitHub Release. There is no SkillCheck server to operate.

## Quick start

Requires Python 3.11 or newer. Install the tagged release directly from GitHub:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "git+https://github.com/ECHOQWETVG/skillcheck.git@v0.1.0"
skillcheck init my-skill
skillcheck lint my-skill
skillcheck test my-skill
skillcheck compat my-skill --agent codex
skillcheck publish my-skill
skillcheck verify my-skill/.skillcheck/artifacts/hello-skill-0.1.0.tar.gz
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`. You can also install the wheel from [Releases](https://github.com/ECHOQWETVG/skillcheck/releases) with `python -m pip install <downloaded-wheel>`.

`lint` returns exit code 1 for security or manifest errors. Warnings are visible but do not fail a normal lint run. Add `--strict` in CI when warnings should block publishing.

## Manifest

A skill declares its contract in `skill.yaml`:

```yaml
schema_version: 1
name: release-notes
version: 1.2.0
description: Generate release notes from merged pull requests
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
```

JSON and TOML manifests are also accepted as `skill.json` and `skill.toml`. The YAML format intentionally supports the small subset needed by the manifest, so the core CLI has no third-party runtime dependency.

## What is checked

- Required metadata, semantic version, license, declared files, and path traversal.
- Hard-coded API keys, GitHub tokens, private keys, and credential assignments.
- Remote-script execution, root deletion, force-push, unsafe permissions, and attempts to disable safety controls.
- Prompt injection patterns such as requests to reveal system prompts or hide actions from users.
- Hidden Unicode control characters.
- Network or shell references that contradict the declared permission contract.
- Agent compatibility declarations.
- Optional declarative tests in `skill-tests.json`.

## Declarative tests

Tests never execute the skill. They assert that expected text exists and unsafe text does not:

```json
{
  "cases": [
    {"name": "has-guidance", "file": "SKILL.md", "contains": ["# Release Notes"]},
    {"name": "no-force-push", "file": "SKILL.md", "forbid": ["git push --force"]}
  ]
}
```

## GitHub Action

Add the following workflow to a skill repository. This project's own workflow checks `examples/hello-skill`.

```yaml
name: SkillCheck
on: [push, pull_request]
permissions:
  contents: read
  security-events: write
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install "git+https://github.com/ECHOQWETVG/skillcheck.git@v0.1.0"
      - run: skillcheck test . --strict --format sarif > skillcheck.sarif
      - uses: github/codeql-action/upload-sarif@v3
        if: always() && hashFiles('skillcheck.sarif') != '' && (github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository)
        with:
          sarif_file: skillcheck.sarif
```

## Local publishing

`skillcheck publish` validates the skill, creates `.skillcheck/artifacts/<name>-<version>.tar.gz`, writes a SHA-256 integrity checksum, and writes a provenance JSON file. Upload those three files to a GitHub Release. Verify the download with `skillcheck verify <artifact>.tar.gz`. The artifact is never executed by SkillCheck.

Publishing blocks on warnings, errors, and failing declarative tests. Source files and release files share the same file inventory. Build directories, virtual environments, caches, and internal reports are excluded; a fresh security report is included. Test specifications still receive secret checks, while dangerous-command assertions are allowed. Non-UTF-8 files and files over 5 MiB are flagged as unscanned. Use `--output` for an archive outside the skill or under its `.skillcheck/artifacts/` directory.

Checksums detect changes when compared against a trusted checksum. They do not prove publisher identity; provenance here is unsigned metadata.

## Development

```bash
git clone https://github.com/ECHOQWETVG/skillcheck.git
cd skillcheck
make install-dev
make check
make build
```

The runtime package has no third-party dependency. The optional development set installs pytest, build, and twine for tests and release validation. GitHub CI builds and tests the installed wheel on Python 3.11, 3.12, and 3.13. Pushing a tag matching the package version builds a draft prerelease for review before publication.

Report bugs and feature requests through [Issues](https://github.com/ECHOQWETVG/skillcheck/issues). For security vulnerabilities, follow [SECURITY.md](SECURITY.md). Maintenance includes bug fixes, scanner rule updates, and changes to packaging and agent conventions.

MIT License.
