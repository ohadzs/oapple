"""I/O-free Shortcuts core — wraps the `/usr/bin/shortcuts` CLI.

An escape hatch to app actions that have no AppleScript dictionary: anything you can
build as an Apple Shortcut (Set Focus, smart-home, app-specific actions) becomes
callable here.
"""
import subprocess
import tempfile
import os


def list_shortcuts() -> list[str]:
    p = subprocess.run(["shortcuts", "list"], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "shortcuts list failed")
    return [ln for ln in p.stdout.splitlines() if ln.strip()]


def run(name: str, input_text: str | None = None) -> str:
    """Run a shortcut by name; returns its text output (if any)."""
    args = ["shortcuts", "run", name]
    in_path = None
    out_fd, out_path = tempfile.mkstemp()
    os.close(out_fd)
    try:
        if input_text is not None:
            in_fd, in_path = tempfile.mkstemp()
            with os.fdopen(in_fd, "w") as f:
                f.write(input_text)
            args += ["--input-path", in_path]
        args += ["--output-path", out_path]
        p = subprocess.run(args, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(p.stderr.strip() or f"shortcut {name!r} failed")
        with open(out_path) as f:
            return f.read().strip()
    finally:
        os.unlink(out_path)
        if in_path:
            os.unlink(in_path)
