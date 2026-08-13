#!/usr/bin/env python3
"""onedrive — read-only view of recently-touched files in synced OneDrive/SharePoint folders.

Adam's new-job documents live in the institutional OneDrive, synced locally by the official
OneDrive client (the sanctioned path — no scraping, no credentials). This surfaces recent
work files so the PA can mention "you were last in <doc>" without opening anything.

Read-only and defensive: missing folder or unreadable entry → skipped, never raises.
The PA must not copy work-document *contents* into its outputs — this lists file metadata
(name, folder, when) only, respecting data governance.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Files/dirs we never surface (noise, system, in-progress).
_SKIP_NAMES = {".DS_Store", "desktop.ini", ".lock"}
_SKIP_SUFFIXES = {".tmp", ".laccdb", "~"}

# Bounds on the walk. Institutional SharePoint libraries hold tens of thousands of files, and this
# runs on the 15-min surface refresh — an unbounded os.walk stats every one each cycle, hammering
# the File-Provider on an already disk-pressured machine. Cap the scan (files stat'd) and the depth
# so cost is bounded regardless of tree size; if the cap clips the scan we say so rather than imply
# the list is the whole tree. Only stat() is called here — it never downloads placeholder content.
_MAX_SCAN = 6000                                          # files stat'd before we stop, per call
_MAX_DEPTH = 7                                            # directory levels below a sync root


def sync_roots() -> list[Path]:
    """All local OneDrive/SharePoint sync roots (institutional + personal), if any."""
    base = Path.home() / "Library" / "CloudStorage"
    if not base.is_dir():
        return []
    return sorted(p for p in base.glob("OneDrive*") if p.is_dir())


def _is_noise(name: str) -> bool:
    return name in _SKIP_NAMES or any(name.endswith(s) for s in _SKIP_SUFFIXES)


def recent_files(days: int = 7, limit: int = 20,
                 roots: list[Path] | None = None) -> list[dict]:
    """Files modified in the last `days`, newest first, as [{name, folder, modified, root}]."""
    roots = roots if roots is not None else sync_roots()
    cutoff = datetime.now() - timedelta(days=days)
    found: list[dict] = []
    scanned = 0
    truncated = False
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            # Prune hidden dirs in place so we don't descend into them.
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            # Depth guard: stop descending past _MAX_DEPTH levels below the root.
            depth = len(Path(dirpath).relative_to(root).parts)
            if depth >= _MAX_DEPTH:
                dirnames[:] = []
            for fn in filenames:
                if fn.startswith(".") or _is_noise(fn):
                    continue
                if scanned >= _MAX_SCAN:                   # scan cap: stop stat'ing, don't walk on
                    truncated = True
                    break
                scanned += 1
                fp = Path(dirpath) / fn
                try:
                    mtime = datetime.fromtimestamp(fp.stat().st_mtime)
                except OSError:
                    continue
                if mtime < cutoff:
                    continue
                found.append({
                    "name": fn,
                    "folder": str(Path(dirpath).relative_to(root)),
                    "modified": mtime.isoformat(timespec="minutes"),
                    "root": root.name,
                })
            if truncated:
                break
        if truncated:
            break
    if truncated:
        # No silent cap: the result is a bounded scan, not the whole tree — say so.
        print(f"onedrive: scan cap ({_MAX_SCAN} files) hit — recent-files list is partial",
              file=sys.stderr)
    found.sort(key=lambda f: f["modified"], reverse=True)
    return found[:limit]


def render(days: int = 7, limit: int = 15) -> str:
    """Calm markdown list of recent work files (metadata only)."""
    roots = sync_roots()
    if not roots:
        return "_No OneDrive/SharePoint sync folder found._\n"
    files = recent_files(days=days, limit=limit, roots=roots)
    lines = [f"# Recent work files — last {days} days", ""]
    if not files:
        lines.append("_Nothing touched recently._")
    else:
        for f in files:
            where = f["folder"] if f["folder"] != "." else f["root"]
            lines.append(f"- {f['modified'][:16]} — {f['name']}  ·  _{where}_")
    return "\n".join(lines) + "\n"


def main() -> int:
    print(render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
