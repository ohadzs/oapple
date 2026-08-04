"""I/O-free Notes core (AppleScript).

Apple exposes no public framework for Notes, so this drives the Notes app via
AppleScript (osascript). Bodies are HTML in Notes; we read the plaintext form and
set new bodies as plain text (Notes wraps them).
"""
import json
import subprocess


def _run(script: str) -> str:
    p = subprocess.run(["osascript", "-l", "JavaScript", "-e", script],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "osascript failed")
    return p.stdout.strip()


def _esc(s: str) -> str:
    return json.dumps(s)  # safe JS string literal


def list_folders() -> list[str]:
    out = _run("""
        const app = Application('Notes');
        JSON.stringify(app.folders().map(f => f.name()));
    """)
    return json.loads(out or "[]")


def list_notes(folder: str | None = None) -> list[dict]:
    """Note names + ids (+ folder). Optionally scoped to one folder."""
    scope = f"app.folders.byName({_esc(folder)}).notes()" if folder else "app.notes()"
    out = _run(f"""
        const app = Application('Notes');
        const ns = {scope};
        JSON.stringify(ns.map(n => ({{
            id: n.id(), name: n.name(),
            folder: n.container().name(),
            modified: n.modificationDate().toISOString()
        }})));
    """)
    return json.loads(out or "[]")


def read(name: str) -> dict:
    """Read a note by name (first match). Returns name, folder, plaintext body."""
    out = _run(f"""
        const app = Application('Notes');
        const matches = app.notes.whose({{name: {_esc(name)}}})();
        if (matches.length === 0) {{ "null"; }} else {{
            const n = matches[0];
            JSON.stringify({{
                id: n.id(), name: n.name(),
                folder: n.container().name(),
                body: n.plaintext()
            }});
        }}
    """)
    if not out or out == "null":
        raise ValueError(f"No note named {name!r}.")
    return json.loads(out)


def create(name: str, body: str = "", folder: str | None = None) -> dict:
    """Create a note. First line becomes the title in Notes."""
    html = f"<div><b>{name}</b></div>" + ("<div>" + body + "</div>" if body else "")
    target = f"app.folders.byName({_esc(folder)})" if folder else "app.defaultAccount.defaultFolder"
    out = _run(f"""
        const app = Application('Notes');
        const folder = {target};
        const n = app.Note({{body: {_esc(html)}}});
        folder.notes.push(n);
        JSON.stringify({{id: n.id(), name: n.name(), folder: n.container().name()}});
    """)
    return json.loads(out)


def append(name: str, text: str) -> dict:
    """Append a line to an existing note's body."""
    out = _run(f"""
        const app = Application('Notes');
        const matches = app.notes.whose({{name: {_esc(name)}}})();
        if (matches.length === 0) {{ "null"; }} else {{
            const n = matches[0];
            n.body = n.body() + "<div>" + {_esc(text)} + "</div>";
            JSON.stringify({{id: n.id(), name: n.name()}});
        }}
    """)
    if not out or out == "null":
        raise ValueError(f"No note named {name!r}.")
    return json.loads(out)


def delete(name: str) -> str:
    out = _run(f"""
        const app = Application('Notes');
        const matches = app.notes.whose({{name: {_esc(name)}}})();
        if (matches.length === 0) {{ "null"; }} else {{
            const nm = matches[0].name();
            app.delete(matches[0]);
            nm;
        }}
    """)
    if not out or out == "null":
        raise ValueError(f"No note named {name!r}.")
    return out
