#!/usr/bin/env python3
"""applenotes — read Apple Notes and capture into a dedicated PA note (macOS, AppleScript).

Adam keeps real to-do/shopping lists in Apple Notes, so the PA captures there too. Writes go
to ONE dedicated note (`PA Inbox`) that the PA owns — it never edits Adam's existing notes.

Reads may span all notes (per Adam's instruction), but callers must honour the PA/legal
separation: Notes also holds sensitive case/medical material, so surface only list/logistics
content into PA outputs — never case content into the dashboard, nudges, or drafts.

All AppleScript is passed via stdin with dynamic values as `argv`, so note text never has to
be escaped into the script body. Requires macOS Automation permission for Notes (granted once).
"""

from __future__ import annotations

import subprocess

ACCOUNT = "iCloud"
FOLDER = "Notes"
PA_NOTE = "PA Inbox"


def _osascript(script: str, *args: str) -> tuple[bool, str]:
    """Run an AppleScript (from stdin) with argv; return (ok, stdout). Never raises."""
    try:
        proc = subprocess.run(
            ["osascript", "-", *args],
            input=script, capture_output=True, text=True, timeout=20,
        )
        return proc.returncode == 0, proc.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return False, ""


# Ensure the PA note exists, then append one line to it. Idempotent create.
_APPEND = """
on run argv
  set t to item 1 of argv
  set ln to item 2 of argv
  tell application "Notes"
    tell account "%(account)s"
      if not (exists note t of folder "%(folder)s") then
        make new note at folder "%(folder)s" with properties {name:t, body:"<div><b>" & t & "</b></div>"}
      end if
      set theNote to note t of folder "%(folder)s"
      set body of theNote to (body of theNote) & "<div>" & ln & "</div>"
      return "ok"
    end tell
  end tell
end run
"""


def append_to_pa_note(line: str, *, note: str = PA_NOTE) -> bool:
    """Append one line to the PA note (creating it if absent). Best-effort; returns success."""
    script = _APPEND % {"account": ACCOUNT, "folder": FOLDER}
    ok, _ = _osascript(script, note, line)
    return ok


_LIST_TITLES = 'tell application "Notes" to get name of notes'


def list_titles() -> list[str]:
    """Every note title (across the account). '' -> [] on failure."""
    ok, out = _osascript(_LIST_TITLES)
    if not ok or not out:
        return []
    # AppleScript returns a comma+space separated list.
    return [t.strip() for t in out.split(", ") if t.strip()]


_READ_NOTE = """
on run argv
  set t to item 1 of argv
  tell application "Notes"
    tell account "%(account)s"
      if not (exists note t of folder "%(folder)s") then
        return ""
      end if
      return body of note t of folder "%(folder)s"
    end tell
  end tell
end run
"""


def read_note(title: str) -> str:
    """Return a note's body as plain-ish text (HTML tags stripped). '' if missing."""
    script = _READ_NOTE % {"account": ACCOUNT, "folder": FOLDER}
    ok, out = _osascript(script, title)
    if not ok or not out:
        return ""
    # Notes bodies are HTML; do a light strip for readability (not a full parser).
    import re
    text = re.sub(r"<[^>]+>", "\n", out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
