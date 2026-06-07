"""Code execution built-in tool."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from cobra_platform.env import merge_subprocess_env
from tools.models import ToolCall


def _execution_env() -> dict[str, str]:
    return merge_subprocess_env(pythonpath=os.environ.get("PYTHONPATH", ""))


def handle(call: ToolCall) -> dict:
    language = str(call.params.get("language", "python")).lower()
    if language not in {"python", "py"}:
        raise NotImplementedError("Only Python code execution is supported in this phase.")

    code = str(call.params.get("code", ""))
    if not code.strip():
        raise ValueError("code_execution requires a non-empty code parameter.")

    timeout = int(call.params.get("timeout_seconds", 30))
    with tempfile.TemporaryDirectory(prefix="cobra-code-") as temp_dir:
        process = subprocess.run(
            [sys.executable, "-c", code],
            text=True,
            capture_output=True,
            cwd=temp_dir,
            env=_execution_env(),
            timeout=timeout,
            check=False,
        )

    return {
        "language": "python",
        "return_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }
