from __future__ import annotations

from .manifest import Manifest


KNOWN_AGENTS = {
    "claude-code",
    "codex",
    "cursor",
    "opencode",
    "github-copilot",
    "gemini-cli",
    "pi",
}


def supported_agents(manifest: Manifest) -> set[str]:
    value = manifest.get("compatibility", "agents", default=[])
    if value == "*":
        return set(KNOWN_AGENTS)
    if isinstance(value, str):
        return {value.strip().lower()}
    if isinstance(value, list):
        return {str(item).strip().lower() for item in value}
    return set()


def check(manifest: Manifest, agent: str | None = None) -> list[dict]:
    declared = supported_agents(manifest)
    issues: list[dict] = []
    if agent and agent.lower() not in declared:
        issues.append({
            "code": "compat.unsupported_agent",
            "severity": "error",
            "message": f"skill does not declare compatibility with {agent}",
            "path": "compatibility.agents",
        })
    for item in sorted(declared - KNOWN_AGENTS):
        issues.append({
            "code": "compat.unknown_agent",
            "severity": "warning",
            "message": f"unknown agent identifier: {item}",
            "path": "compatibility.agents",
        })
    return issues
