"""Subprocess worker used by sandbox.py."""

from __future__ import annotations

import json
import sys
import traceback

from tools.builtin import dispatch_builtin
from tools.models import ToolCall


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        call = ToolCall.from_dict(payload)
        output = dispatch_builtin(call)
        print(json.dumps({"success": True, "output": output}, default=str))
        return 0
    except Exception as exc:  # pragma: no cover - defensive worker boundary
        print(
            json.dumps(
                {
                    "success": False,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
