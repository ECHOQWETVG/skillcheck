from __future__ import annotations

import json
from typing import Iterable

from .scanner import Issue


def issue_dicts(issues: Iterable[Issue | dict]) -> list[dict]:
    return [issue.as_dict() if isinstance(issue, Issue) else issue for issue in issues]


def sarif(issues: Iterable[Issue | dict], tool_version: str) -> dict:
    results = []
    rules = {}
    for issue in issue_dicts(issues):
        code = issue["code"]
        level = "error" if issue["severity"] == "error" else "warning" if issue["severity"] == "warning" else "note"
        rules.setdefault(code, {"id": code, "name": code})
        result = {"ruleId": code, "level": level, "message": {"text": issue["message"]}}
        if issue.get("path"):
            location = {"physicalLocation": {"artifactLocation": {"uri": issue["path"]}}}
            if issue.get("line"):
                location["physicalLocation"]["region"] = {"startLine": issue["line"]}
            result["locations"] = [location]
        results.append(result)
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "skillcheck", "version": tool_version, "rules": list(rules.values())}}, "results": results}],
    }


def dumps_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"
