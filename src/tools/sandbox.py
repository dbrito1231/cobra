"""Sandbox gate and subprocess runner for approved tool calls."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.builtin import dispatch_builtin
from tools.config import sandbox_enabled_for_call
from tools.models import ToolCall, ToolResult


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = Path(__file__).resolve().parents[1]


def _restricted_env() -> dict[str, str]:
    """Build a clean subprocess environment without user secrets."""

    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "PYTHONPATH": str(SRC_ROOT),
        "COBRA_SANDBOX": "1",
    }
    return {key: value for key, value in env.items() if value}


def _parse_worker_output(stdout: str, stderr: str) -> tuple[bool, Any, str | None]:
    if stdout.strip():
        try:
            payload = json.loads(stdout)
            return bool(payload.get("success")), payload.get("output"), payload.get("error")
        except json.JSONDecodeError:
            if not stderr.strip():
                return False, None, "sandbox_worker_output_parse_error"

    if stderr.strip():
        try:
            payload = json.loads(stderr)
            return False, payload.get("traceback"), payload.get("error")
        except json.JSONDecodeError:
            return False, stderr, stderr

    return False, None, "Sandbox worker produced no output."


def run_sandboxed(call: ToolCall) -> ToolResult:
    """Node M: execute a tool in a child process with a restricted env."""

    try:
        process = subprocess.run(
            [sys.executable, "-m", "tools.sandbox_worker"],
            input=json.dumps(call.to_dict()),
            text=True,
            capture_output=True,
            cwd=str(WORKSPACE_ROOT),
            env=_restricted_env(),
            timeout=int(call.params.get("timeout_seconds", 30)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            success=False,
            output=None,
            tool_call=call,
            error="timeout",
        )

    success, output, error = _parse_worker_output(process.stdout, process.stderr)
    if process.returncode != 0:
        success = False
    return ToolResult(success=success, output=output, tool_call=call, error=error)


def run_unsandboxed(call: ToolCall) -> ToolResult:
    """Node N: execute with full process access and notify the user."""

    notification = "[SANDBOX OVERRIDE] Running tool with full system access."
    try:
        output = dispatch_builtin(call)
        return ToolResult(
            success=True,
            output=output,
            tool_call=call,
            notifications=[notification],
        )
    except Exception as exc:
        return ToolResult(
            success=False,
            output=None,
            tool_call=call,
            error=str(exc),
            notifications=[notification],
        )


def run_tool(call: ToolCall) -> ToolResult:
    """Node L: choose sandboxed default or explicit per-call override."""

    if sandbox_enabled_for_call(call):
        return run_sandboxed(call)
    return run_unsandboxed(call)
