"""A small dependency-free YAML reader for SkillCheck manifests."""

from __future__ import annotations

import ast
import json
import re
from typing import Any


class MiniYAMLError(ValueError):
    pass


def _scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return None
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.startswith(("'", '"')) and value.endswith(value[0]):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return [_scalar(part) for part in value[1:-1].split(",") if part.strip()]
    if value.startswith("{") and value.endswith("}"):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise MiniYAMLError(f"invalid inline mapping: {value}") from exc
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def _lines(text: str) -> list[tuple[int, str, int]]:
    result = []
    for number, raw in enumerate(text.splitlines(), 1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise MiniYAMLError(f"tabs are not supported (line {number})")
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        result.append((indent, stripped, number))
    return result


def load(text: str) -> dict[str, Any]:
    rows = _lines(text)
    if not rows:
        return {}

    def parse_block(position: int, indent: int) -> tuple[Any, int]:
        if position >= len(rows) or rows[position][0] < indent:
            return {}, position
        is_list = rows[position][1].startswith("-")
        result: Any = [] if is_list else {}
        while position < len(rows):
            row_indent, content, line_no = rows[position]
            if row_indent < indent:
                break
            if row_indent > indent:
                raise MiniYAMLError(f"unexpected indentation (line {line_no})")
            if is_list:
                if not content.startswith("-"):
                    raise MiniYAMLError(f"mixed list and mapping (line {line_no})")
                rest = content[1:].strip()
                if not rest:
                    if position + 1 < len(rows) and rows[position + 1][0] > indent:
                        child, position = parse_block(position + 1, rows[position + 1][0])
                        result.append(child)
                    else:
                        result.append(None)
                        position += 1
                    continue
                if ":" in rest and not rest.startswith(("http://", "https://")):
                    key, tail = rest.split(":", 1)
                    key = key.strip()
                    child: dict[str, Any] = {key: _scalar(tail)} if tail.strip() else {key: {}}
                    position += 1
                    if position < len(rows) and rows[position][0] > indent:
                        nested, position = parse_block(position, rows[position][0])
                        if child[key] == {}:
                            child[key] = nested
                        elif isinstance(nested, dict):
                            child.update(nested)
                    result.append(child)
                else:
                    result.append(_scalar(rest))
                    position += 1
            else:
                if content.startswith("-") or ":" not in content:
                    raise MiniYAMLError(f"expected key: value (line {line_no})")
                key, tail = content.split(":", 1)
                key = key.strip()
                if not key:
                    raise MiniYAMLError(f"empty key (line {line_no})")
                if key in result:
                    raise MiniYAMLError(f"duplicate key: {key} (line {line_no})")
                tail = tail.strip()
                position += 1
                if tail:
                    result[key] = _scalar(tail)
                elif position < len(rows) and rows[position][0] > indent:
                    result[key], position = parse_block(position, rows[position][0])
                else:
                    result[key] = {}
        return result, position

    parsed, position = parse_block(0, rows[0][0])
    if position != len(rows):
        raise MiniYAMLError(f"could not parse line {rows[position][2]}")
    if not isinstance(parsed, dict):
        raise MiniYAMLError("manifest root must be a mapping")
    return parsed
