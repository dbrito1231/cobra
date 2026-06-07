"""Built-in tool dispatch helpers."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from tools.models import ToolCall
from tools.registry import CUSTOM_HANDLERS, get_tool_meta


def dispatch_builtin(call: ToolCall) -> Any:
    """Run the registered handler for a built-in tool call."""

    custom = CUSTOM_HANDLERS.get(call.tool_name)
    if custom is not None:
        return custom(call)

    meta = get_tool_meta(call.tool_name)
    module_name, function_name = meta.handler.rsplit(".", 1)
    module = import_module(module_name)
    handler = getattr(module, function_name)
    return handler(call)
