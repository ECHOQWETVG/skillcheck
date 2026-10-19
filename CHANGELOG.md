# Changelog

## 0.1.0

Initial alpha release. Requires Python 3.11 or newer. Install with:

```bash
python -m pip install "git+https://github.com/ECHOQWETVG/skillcheck.git@v0.1.0"
```

- Added local manifest validation for YAML, JSON, and TOML skill manifests.
- Added static secret, dangerous-command, prompt-injection, hidden-Unicode, and permission mismatch checks.
- Added declarative non-executing skill tests, agent compatibility checks, SARIF reports, and release artifacts with checksums and provenance.
- Added GitHub Actions integration and a starter skill template.
- Publishing now blocks on failing declarative tests and uses the same file inventory as the scanner.
- Added regression coverage for malformed input, symlink escapes, secret detection in test specifications, archive integrity, and source overwrite prevention.

Compatibility checks cover manifest declarations only. Static checks are heuristic; checksum verification does not authenticate the publisher. This release is intended for early adopters and feedback through GitHub Issues.
