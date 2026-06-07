"""System control — volume, brightness, wifi, and status on macOS."""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
from typing import Any

from tools.models import ToolCall


def _run(command: list[str], *, check: bool = False, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=check,
        timeout=timeout,
    )


def _is_darwin() -> bool:
    return platform.system() == "Darwin"


def _wifi_interface() -> str | None:
    process = _run(["networksetup", "-listallhardwareports"], check=False)
    if process.returncode != 0:
        return None

    lines = process.stdout.splitlines()
    for index, line in enumerate(lines):
        if "Wi-Fi" in line or "AirPort" in line:
            for follow in lines[index + 1 : index + 4]:
                if follow.startswith("Device:"):
                    return follow.split(":", 1)[1].strip()
    return "en0"


def _get_volume() -> int | None:
    process = _run(["osascript", "-e", "output volume of (get volume settings)"], check=False)
    if process.returncode != 0:
        return None
    try:
        return int(process.stdout.strip())
    except ValueError:
        return None


def _set_volume(level: int) -> dict[str, Any]:
    bounded = max(0, min(100, int(level)))
    process = _run(["osascript", "-e", f"set volume output volume {bounded}"], check=False)
    if process.returncode != 0:
        error = (process.stderr or process.stdout or "volume change failed").strip()
        raise RuntimeError(error)
    return {"operation": "volume", "status": "set", "level": bounded}


def _parse_ioreg_brightness(stdout: str) -> int | None:
    match = re.search(r'"IODisplayBrightness"\s*=\s*(0x[0-9a-fA-F]+|\d+)', stdout)
    if not match:
        return None
    raw = match.group(1)
    value = int(raw, 16) if raw.startswith("0x") else int(raw)
    if value <= 1:
        return int(round(value * 100))
    if value <= 100:
        return value
    return int(round(value / 65535 * 100))


def _get_brightness() -> int | None:
    result = subprocess.run(
        ["ioreg", "-l", "-w", "0"],
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        return None
    stdout = result.stdout.decode("utf-8", errors="replace")
    return _parse_ioreg_brightness(stdout)


def _set_brightness(level: int) -> dict[str, Any]:
    bounded = max(0, min(100, int(level)))
    brightness_cli = shutil.which("brightness")
    if brightness_cli:
        normalized = bounded / 100.0
        process = _run([brightness_cli, str(normalized)], check=False)
        if process.returncode == 0:
            return {"operation": "brightness", "status": "set", "level": bounded}

    steps = max(1, round(bounded / 6.25))
    reset_script = 'tell application "System Events" to repeat 16 times\nkey code 145\nend repeat'
    set_script = (
        f'tell application "System Events" to repeat {steps} times\nkey code 144\nend repeat'
    )
    reset = _run(["osascript", "-e", reset_script], check=False)
    if reset.returncode != 0:
        error = (reset.stderr or reset.stdout or "brightness reset failed").strip()
        raise RuntimeError(error)
    process = _run(["osascript", "-e", set_script], check=False)
    if process.returncode != 0:
        error = (process.stderr or process.stdout or "brightness change failed").strip()
        raise RuntimeError(error)
    return {
        "operation": "brightness",
        "status": "set",
        "level": bounded,
        "method": "key_codes",
    }


def _get_wifi_status() -> dict[str, Any]:
    interface = _wifi_interface()
    if not interface:
        return {"status": "unavailable", "message": "Wi-Fi interface not found."}

    power = _run(["networksetup", "-getairportpower", interface], check=False)
    network = _run(["networksetup", "-getairportnetwork", interface], check=False)

    powered_on = None
    if power.returncode == 0:
        powered_on = power.stdout.strip().lower().endswith("on")

    ssid = None
    connected = False
    if network.returncode == 0:
        text = network.stdout.strip()
        if "Current Wi-Fi Network:" in text:
            ssid = text.split(":", 1)[1].strip()
            connected = bool(ssid)
        elif "You are not associated with an AirPort network" in text:
            connected = False

    return {
        "interface": interface,
        "powered_on": powered_on,
        "connected": connected,
        "ssid": ssid,
    }


def _set_volume_linux(level: int) -> dict[str, Any]:
    bounded = max(0, min(100, int(level)))
    if shutil.which("pactl"):
        process = _run(
            ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{bounded}%"],
            check=False,
        )
    elif shutil.which("amixer"):
        process = _run(["amixer", "set", "Master", f"{bounded}%"], check=False)
    else:
        return {
            "operation": "volume",
            "status": "unsupported",
            "message": "Install pactl (PulseAudio) or amixer (ALSA) for Linux volume control.",
        }
    if process.returncode != 0:
        error = (process.stderr or process.stdout or "volume change failed").strip()
        raise RuntimeError(error)
    return {"operation": "volume", "status": "set", "level": bounded}


def _set_volume_windows(level: int) -> dict[str, Any]:
    bounded = max(0, min(100, int(level)))
    nircmd = shutil.which("nircmd")
    if nircmd:
        scalar = int(bounded * 655.35)
        process = _run([nircmd, "setsysvolume", str(scalar)], check=False)
        if process.returncode != 0:
            error = (process.stderr or process.stdout or "volume change failed").strip()
            raise RuntimeError(error)
        return {"operation": "volume", "status": "set", "level": bounded}
    return {
        "operation": "volume",
        "status": "partial",
        "level": bounded,
        "message": "Windows volume control requires nircmd or use Tier 1 macOS for full system control.",
    }


def _status_payload() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "operation": "status",
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
    }
    if _is_darwin():
        volume = _get_volume()
        if volume is not None:
            payload["volume"] = volume
        brightness = _get_brightness()
        if brightness is not None:
            payload["brightness"] = brightness
        payload["wifi"] = _get_wifi_status()
    return payload


def handle(call: ToolCall) -> dict[str, Any]:
    operation = str(call.params.get("operation", "status")).lower()

    if operation in {"status", "read"}:
        return _status_payload() | {"operation": operation}

    if operation in {"notifications", "settings"}:
        return {
            "operation": operation,
            "status": "unsupported",
            "message": f"Operation '{operation}' is not implemented on any platform yet.",
        }

    if operation == "volume":
        level = call.params.get("level")
        if level is None:
            raise ValueError("volume operation requires level (0-100).")
        system = platform.system()
        if _is_darwin():
            return _set_volume(int(level))
        if system == "Linux":
            return _set_volume_linux(int(level))
        if system == "Windows":
            return _set_volume_windows(int(level))
        return {
            "operation": "volume",
            "status": "unsupported",
            "message": "Volume control is not supported on this OS.",
        }

    if not _is_darwin():
        return {
            "operation": operation,
            "status": "unsupported",
            "message": f"Operation '{operation}' is only implemented on macOS.",
        }

    if operation == "brightness":
        level = call.params.get("level")
        if level is None:
            raise ValueError("brightness operation requires level (0-100).")
        return _set_brightness(int(level))

    if operation == "wifi":
        return {"operation": "wifi", **_get_wifi_status()}

    raise NotImplementedError(f"Unsupported system_control operation: {operation}")
