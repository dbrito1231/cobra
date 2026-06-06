"""Application control — open, close, activate, and list applications."""

from __future__ import annotations

import platform
import subprocess
from typing import Any

from tools.models import ToolCall


def _app_name(call: ToolCall) -> str:
    name = call.params.get("app_name") or call.params.get("application") or call.params.get("name")
    if not name:
        raise ValueError("app_control requires app_name (or application).")
    return str(name).strip()


def _run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=check,
        timeout=int(30),
    )


def _open_app(call: ToolCall) -> dict[str, Any]:
    app_name = _app_name(call) if call.params.get("app_name") or call.params.get("application") or call.params.get("name") else ""
    url = call.params.get("url")
    path = call.params.get("path")
    system = platform.system()

    if url:
        if system == "Windows":
            process = _run(["cmd", "/c", "start", "", str(url)], check=False)
        elif system == "Linux":
            process = _run(["xdg-open", str(url)], check=False)
        else:
            process = _run(["open", str(url)], check=False)
    elif path:
        if system == "Windows":
            process = _run(["cmd", "/c", "start", "", str(path)], check=False)
        elif system == "Linux":
            process = _run(["xdg-open", str(path)], check=False)
        else:
            process = _run(["open", str(path)], check=False)
    elif not app_name:
        raise ValueError("app_control open requires app_name, url, or path.")
    elif system == "Windows":
        process = _run(["cmd", "/c", "start", "", app_name], check=False)
    elif system == "Linux":
        process = _run(["xdg-open", app_name], check=False)
    else:
        process = _run(["open", "-a", app_name], check=False)

    if process.returncode != 0:
        error = (process.stderr or process.stdout or "open failed").strip()
        raise RuntimeError(error)
    return {
        "operation": "open",
        "status": "opened",
        "app_name": app_name or None,
        "target": url or path or app_name,
    }


def _close_app(call: ToolCall) -> dict[str, Any]:
    app_name = _app_name(call)
    system = platform.system()

    if system == "Darwin":
        script = f'tell application "{app_name}" to quit'
        process = _run(["osascript", "-e", script], check=False)
    elif system == "Windows":
        process = _run(["taskkill", "/IM", app_name, "/F"], check=False)
    else:
        process = _run(["pkill", "-f", app_name], check=False)

    if process.returncode != 0:
        error = (process.stderr or process.stdout or "close failed").strip()
        raise RuntimeError(error)
    return {"operation": "close", "status": "closed", "app_name": app_name}


def _activate_app(call: ToolCall) -> dict[str, Any]:
    app_name = _app_name(call)
    system = platform.system()

    if system == "Darwin":
        script = f'tell application "{app_name}" to activate'
        process = _run(["osascript", "-e", script], check=False)
    elif system == "Windows":
        process = _run(
            [
                "powershell",
                "-Command",
                f'(New-Object -ComObject WScript.Shell).AppActivate("{app_name}")',
            ],
            check=False,
        )
    else:
        process = _run(["wmctrl", "-a", app_name], check=False)

    if process.returncode != 0:
        error = (process.stderr or process.stdout or "activate failed").strip()
        raise RuntimeError(error)
    return {"operation": "activate", "status": "activated", "app_name": app_name}


def _list_apps() -> dict[str, Any]:
    system = platform.system()

    if system == "Darwin":
        script = (
            'tell application "System Events" to get name of every process '
            "whose background only is false"
        )
        process = _run(["osascript", "-e", script], check=False)
        if process.returncode != 0:
            raise RuntimeError((process.stderr or process.stdout or "list failed").strip())
        raw = process.stdout.strip()
        apps = [item.strip() for item in raw.split(", ") if item.strip()]
        return {"operation": "list", "status": "ok", "applications": apps}

    if system == "Windows":
        process = _run(
            ["powershell", "-Command", "Get-Process | Select-Object -ExpandProperty ProcessName"],
            check=False,
        )
        apps = [line.strip() for line in process.stdout.splitlines() if line.strip()]
        return {"operation": "list", "status": "ok", "applications": apps}

    process = _run(["ps", "-eo", "comm="], check=False)
    apps = sorted({line.strip() for line in process.stdout.splitlines() if line.strip()})
    return {"operation": "list", "status": "ok", "applications": apps}


def handle(call: ToolCall) -> dict[str, Any]:
    operation = str(call.params.get("operation", "open")).lower()

    if operation == "open":
        return _open_app(call)
    if operation == "close":
        return _close_app(call)
    if operation in {"activate", "focus", "interact"}:
        return _activate_app(call)
    if operation == "list":
        return _list_apps()

    raise NotImplementedError(f"Unsupported app_control operation: {operation}")
