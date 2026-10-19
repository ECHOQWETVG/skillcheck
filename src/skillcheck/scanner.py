from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from pathlib import Path

from .files import TEST_SPECS, skill_files
from .manifest import Manifest


@dataclass
class Issue:
    code: str
    severity: str
    message: str
    path: str | None = None
    line: int | None = None

    def as_dict(self) -> dict:
        return {key: value for key, value in asdict(self).items() if value is not None}


SECRET_PATTERNS = [
    ("secret.aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "possible AWS access key"),
    ("secret.github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"), "possible GitHub token"),
    ("secret.openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "possible API key"),
    ("secret.private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private key material"),
    ("secret.assignment", re.compile(r"\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*['\"][^'\"]{12,}['\"]", re.I), "hard-coded credential assignment"),
]

DANGEROUS_PATTERNS = [
    ("danger.pipe_to_shell", re.compile(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sh|bash|zsh)\b", re.I), "downloads and executes a remote script"),
    ("danger.root_delete", re.compile(r"\brm\s+-[a-z]*r[a-z]*f\s+/(?:\s|$)", re.I), "recursive deletion from filesystem root"),
    ("danger.force_push", re.compile(r"\bgit\s+push\b[^\n]*--force(?:-with-lease)?", re.I), "force-push command"),
    ("danger.world_writable", re.compile(r"\bchmod\s+(?:-R\s+)?777\b", re.I), "world-writable permission change"),
    ("danger.disable_security", re.compile(r"\b(?:disable|bypass|turn off)\b[^\n]{0,40}\b(?:security|safety|sandbox|approval|verification)\b", re.I), "attempt to disable a safety control"),
]

INJECTION_PATTERNS = [
    ("injection.ignore_instructions", re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.I), "prompt injection phrase"),
    ("injection.system_prompt", re.compile(r"(?:reveal|show|print|expose)\s+(?:the\s+)?(?:system|developer)\s+prompt", re.I), "request to reveal a privileged prompt"),
    ("injection.secrecy", re.compile(r"(?:do not|don't)\s+(?:tell|show|inform)\s+(?:the\s+)?user", re.I), "instruction to hide behavior from the user"),
    ("injection.exfiltration", re.compile(r"\b(?:exfiltrate|send|upload)\b[^\n]{0,80}\b(?:secret|token|credential|private|password)\b", re.I), "possible secret exfiltration instruction"),
]

ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\u2066-\u206f\ufeff]")
MAX_TEXT_BYTES = 5 * 1024 * 1024


def scan(manifest: Manifest) -> list[Issue]:
    issues: list[Issue] = []
    permissions = manifest.get("permissions", default={})
    if not isinstance(permissions, dict):
        permissions = {}
    shell_allowed = bool(permissions.get("shell", False))
    network_allowed = bool(permissions.get("network", False))

    for path in skill_files(manifest.root):
        relative = path.relative_to(manifest.root).as_posix()
        if path.is_symlink():
            resolved = path.resolve()
            try:
                resolved.relative_to(manifest.root)
            except ValueError:
                issues.append(Issue("file.symlink_escape", "error", "symlink points outside the skill root", relative))
            else:
                issues.append(Issue("file.symlink", "warning", "symlink is included; review archive contents", relative))
            continue
        try:
            if not path.is_file():
                issues.append(Issue("file.special", "error", "only regular files can be scanned", relative))
                continue
            size = path.stat().st_size
        except OSError as exc:
            issues.append(Issue("file.unreadable", "error", f"cannot inspect file: {exc}", relative))
            continue
        if size > MAX_TEXT_BYTES:
            issues.append(Issue("file.too_large", "warning", "file exceeds the 5 MiB scan limit; review before publishing", relative))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            issues.append(Issue("file.binary", "warning", "non-UTF-8 file cannot be inspected by the text scanner", relative))
            continue
        except OSError:
            issues.append(Issue("file.unreadable", "error", "cannot read file", relative))
            continue
        lines = text.splitlines()
        for line_no, line in enumerate(lines, 1):
            if ZERO_WIDTH.search(line):
                issues.append(Issue("text.hidden_unicode", "error", "hidden Unicode control character", relative, line_no))
            for code, pattern, message in SECRET_PATTERNS:
                if pattern.search(line):
                    issues.append(Issue(code, "error", message, relative, line_no))
            if relative in TEST_SPECS:
                # Test assertions may name forbidden commands; secrets still fail.
                continue
            for code, pattern, message in DANGEROUS_PATTERNS:
                if pattern.search(line):
                    issues.append(Issue(code, "error", message, relative, line_no))
            for code, pattern, message in INJECTION_PATTERNS:
                if pattern.search(line):
                    issues.append(Issue(code, "warning", message, relative, line_no))
        if relative in TEST_SPECS:
            continue
        lower = text.lower()
        shell_hint = re.search(r"(?:^|[\s`$])(bash|sh|zsh|powershell|pwsh|npm|pip|python|node|git|rm)\b", lower)
        if shell_hint and not shell_allowed:
            issues.append(Issue("permission.shell_mismatch", "warning", "skill contains shell-like commands but permissions.shell is false", relative))
        # Plain documentation links are harmless. Only flag code/tool hints
        # that imply an outbound request.
        network_hint = re.search(r"\b(?:curl|wget|requests?\.|urllib\.|fetch\s*\(|httpx)\b", lower)
        if network_hint and not network_allowed:
            issues.append(Issue("permission.network_mismatch", "warning", "skill references network access but permissions.network is false", relative))

    return issues
