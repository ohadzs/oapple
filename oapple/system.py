"""I/O-free macOS system-control core.

Thin, reliable wrappers over osascript / pmset / networksetup / pbcopy — the scattered
"Mac control" osascript calls, consolidated. Brightness and Focus/DND are deliberately
absent: macOS exposes no clean public API for them (Focus → run a Shortcut instead).
"""
import subprocess


def _run(args: list[str]) -> str:
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip() or f"{args[0]} failed")
    return p.stdout.strip()


def _osa(script: str) -> str:
    return _run(["osascript", "-e", script])


# ---- volume ----

def get_volume() -> int:
    return int(_osa("output volume of (get volume settings)"))


def set_volume(level: int) -> int:
    level = max(0, min(100, level))
    _osa(f"set volume output volume {level}")
    return level


# ---- dark mode ----

def get_dark() -> bool:
    p = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                       capture_output=True, text=True)
    return p.stdout.strip() == "Dark"  # errors (non-zero) when Light


def set_dark(on: bool | None) -> bool:
    """on=None toggles."""
    if on is None:
        on = not get_dark()
    val = "true" if on else "false"
    _osa(f'tell application "System Events" to tell appearance preferences '
         f'to set dark mode to {val}')
    return on


# ---- battery ----

def battery() -> dict:
    out = _run(["pmset", "-g", "batt"])
    pct = None
    for tok in out.replace(";", " ").split():
        if tok.endswith("%") and tok[:-1].isdigit():
            pct = int(tok[:-1])
            break
    charging = "AC Power" in out
    state = "charged" if "charged" in out else ("charging" if charging else "battery")
    return {"percent": pct, "power": "AC" if charging else "battery", "state": state,
            "raw": out.split("\n")[-1].strip()}


# ---- wifi ----

def _wifi_iface() -> str:
    out = _run(["networksetup", "-listallhardwareports"])
    lines = out.splitlines()
    for i, ln in enumerate(lines):
        if "Wi-Fi" in ln and i + 1 < len(lines) and "Device:" in lines[i + 1]:
            return lines[i + 1].split(":", 1)[1].strip()
    return "en0"


def get_wifi() -> bool:
    iface = _wifi_iface()
    return _run(["networksetup", "-getairportpower", iface]).strip().endswith("On")


def set_wifi(on: bool) -> bool:
    iface = _wifi_iface()
    _run(["networksetup", "-setairportpower", iface, "on" if on else "off"])
    return on


# ---- clipboard ----

def get_clipboard() -> str:
    return _run(["pbpaste"])


def set_clipboard(text: str) -> None:
    p = subprocess.run(["pbcopy"], input=text, text=True)
    if p.returncode != 0:
        raise RuntimeError("pbcopy failed")


# ---- power / session ----

def sleep_now() -> None:
    _run(["pmset", "sleepnow"])


def lock_screen() -> None:
    # CGSession helper was removed in recent macOS; the Lock-Screen keystroke is reliable.
    _osa('tell application "System Events" to keystroke "q" using {control down, command down}')
