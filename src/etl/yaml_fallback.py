"""Minimal YAML loader for simple configuration files."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Tuple


@dataclass
class Line:
    raw: str
    indent: int
    content: str


def safe_load(text: str) -> Any:
    lines = [_prepare_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line is not None]
    parsed, _ = _parse_block(lines, 0, 0)
    return parsed


def _prepare_line(line: str) -> Line | None:
    if not line.strip() or line.lstrip().startswith("#"):
        return None
    indent = len(line) - len(line.lstrip(" "))
    return Line(raw=line.rstrip("\n"), indent=indent, content=line.strip())


def _parse_block(lines: List[Line], index: int, indent: int) -> Tuple[Any, int]:
    mapping: dict[str, Any] = {}
    sequence: List[Any] = []
    is_list: bool | None = None
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise ValueError(f"Unexpected indentation at line: {line.raw}")
        content = line.content
        if content.startswith("- "):
            if is_list is False:
                raise ValueError("Cannot mix list and mapping at the same level")
            is_list = True
            index += 1
            value_part = content[2:]
            if not value_part:
                item, index = _parse_block(lines, index, indent + 2)
                sequence.append(item)
                continue
            if ":" in value_part:
                key, val = [part.strip() for part in value_part.split(":", 1)]
                item: dict[str, Any] = {}
                item[key] = _parse_scalar(val) if val else None
                nested, index = _parse_block(lines, index, indent + 2)
                if isinstance(nested, dict):
                    item.update({k: v for k, v in nested.items() if v is not None})
                elif nested not in (None, {}):
                    item[key] = nested
                sequence.append(item)
                continue
            sequence.append(_parse_scalar(value_part))
            continue
        else:
            if is_list is True:
                raise ValueError("Cannot mix list and mapping at the same level")
            is_list = False
            if ":" not in content:
                raise ValueError(f"Invalid mapping entry: {line.raw}")
            key, val = [part.strip() for part in content.split(":", 1)]
            index += 1
            if val:
                mapping[key] = _parse_scalar(val)
            else:
                nested, index = _parse_block(lines, index, indent + 2)
                mapping[key] = nested
            continue
    if is_list:
        return sequence, index
    return mapping, index


def _parse_scalar(value: str) -> Any:
    if value is None:
        return None
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower in {"null", "none", "~"}:
        return None
    if value.isdigit():
        return int(value)
    try:
        return float(value)
    except ValueError:
        return value
