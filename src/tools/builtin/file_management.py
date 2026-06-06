"""File management built-in tool."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from tools.models import ToolCall


READ_OPERATIONS = {"read", "list", "exists"}


def _operation_for(call: ToolCall) -> str:
    if call.tool_name == "file_read":
        return "read"
    if call.tool_name == "file_write":
        return "write"
    return str(call.params.get("operation", "read")).lower()


def _resolve_path(raw_path: str) -> Path:
    if not raw_path:
        raise ValueError("file_management requires a path parameter.")

    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path

    resolved = path.resolve()
    if os.environ.get("COBRA_SANDBOX") == "1":
        workspace = Path.cwd().resolve()
        if resolved != workspace and workspace not in resolved.parents:
            raise PermissionError("Sandboxed file operations are limited to the workspace.")
    return resolved


def _read(path: Path) -> dict:
    return {"path": str(path), "content": path.read_text(encoding="utf-8")}


def _list(path: Path) -> dict:
    return {
        "path": str(path),
        "entries": sorted(child.name for child in path.iterdir()),
    }


def _write(path: Path, content: str) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"path": str(path), "bytes_written": len(content.encode("utf-8"))}


def _delete(path: Path) -> dict:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return {"path": str(path), "deleted": True}


def _organize(root: Path, rules: dict[str, str]) -> dict:
    moved: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    for item in root.iterdir():
        if not item.is_file():
            skipped.append({"path": str(item), "reason": "not_a_file"})
            continue

        extension = item.suffix.lower()
        destination_dir_name = rules.get(extension)
        if not destination_dir_name:
            skipped.append({"path": str(item), "reason": "no_matching_rule"})
            continue

        destination_dir = Path(destination_dir_name).expanduser()
        if not destination_dir.is_absolute():
            destination_dir = (root / destination_dir).resolve()
        else:
            destination_dir = _resolve_path(str(destination_dir))

        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / item.name
        shutil.move(str(item), str(destination))
        moved.append({"source": str(item), "destination": str(destination)})

    return {"path": str(root), "moved": moved, "skipped": skipped}


def handle(call: ToolCall) -> dict:
    operation = _operation_for(call)
    path = _resolve_path(str(call.params.get("path", "")))

    if operation == "exists":
        return {"path": str(path), "exists": path.exists()}
    if operation == "read":
        return _read(path)
    if operation == "list":
        return _list(path)
    if operation == "write":
        return _write(path, str(call.params.get("content", "")))
    if operation == "delete":
        return _delete(path)
    if operation == "mkdir":
        path.mkdir(parents=True, exist_ok=True)
        return {"path": str(path), "created": True}
    if operation == "move":
        destination = _resolve_path(str(call.params.get("destination", "")))
        shutil.move(str(path), str(destination))
        return {"source": str(path), "destination": str(destination)}
    if operation == "copy":
        destination = _resolve_path(str(call.params.get("destination", "")))
        if path.is_dir():
            shutil.copytree(path, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
        return {"source": str(path), "destination": str(destination)}
    if operation == "organize":
        rules = call.params.get("rules") or {}
        if not isinstance(rules, dict) or not rules:
            raise ValueError("organize requires a rules mapping of extensions to destination directories.")
        normalized_rules = {str(key).lower(): str(value) for key, value in rules.items()}
        return _organize(path, normalized_rules)

    raise NotImplementedError(f"Unsupported file operation: {operation}")
