#!/usr/bin/env python3
"""serve_dashboard — the always-on desktop surface.

Serves the PA dashboard at http://127.0.0.1:8787 (local only, private) so Adam can keep one
tab open as his central glance. The page auto-refreshes every 60s (meta refresh); the monitor
regenerates the underlying HTML as things change, so the open tab stays current on its own.

Only the dashboard file is served — never the rest of data/ — and only on loopback.

Usage:  python3 serve_dashboard.py [--port 8787]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parent
DASHBOARD = REPO / "data" / "PA_DASHBOARD.html"
sys.path.insert(0, str(REPO))

from lib.magictodo import breakdown  # noqa: E402
from lib.mailsummary import summarize as summarize_inbox  # noqa: E402
from lib.taskstore import (  # noqa: E402
    CATEGORIES, DEFAULT_CATEGORY, add_task, complete_task, load_tasks, set_steps, update_task,
)


def _rebuild() -> None:
    """Regenerate the dashboard HTML (after a task change) so the next load is current."""
    subprocess.run(["python3", str(REPO / "build_pa_dashboard.py")],
                   check=False, capture_output=True, timeout=60)


def _ensure_built() -> None:
    """Build the dashboard once if it does not exist yet (e.g. first run)."""
    if not DASHBOARD.exists():
        _rebuild()


class Handler(BaseHTTPRequestHandler):
    """Serve the dashboard for any path; refuse everything else. Loopback only."""

    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler API)
        _ensure_built()
        try:
            body = DASHBOARD.read_bytes()
        except OSError:
            self.send_error(503, "dashboard not available")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        """Handle the dashboard's own forms: /capture (add) and /complete (mark done)."""
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0) or 0)
        params = parse_qs(self.rfile.read(length).decode("utf-8")) if length else {}

        def first(key: str, default: str = "") -> str:
            return (params.get(key, [default]) or [default])[0].strip()

        try:
            if path == "/capture":
                title = first("title")
                if title:
                    cat = first("category", DEFAULT_CATEGORY)
                    add_task(
                        title,
                        category=cat if cat in CATEGORIES else DEFAULT_CATEGORY,
                        theme=first("theme") or None,
                        priority=first("priority", "normal") or "normal",
                        energy=first("energy", "medium") or "medium",
                        source="dashboard",
                    )
                    _rebuild()
            elif path == "/complete":
                tid = first("id")
                if tid.isdigit():
                    complete_task(int(tid))
                    _rebuild()
            elif path == "/edit":
                tid = first("id")
                if tid.isdigit():
                    update_task(int(tid), {
                        "title": first("title"), "category": first("category"),
                        "theme": first("theme"), "priority": first("priority"),
                        "energy": first("energy"), "due_date": first("due"),
                    })
                    _rebuild()
            elif path == "/summarize-mail":
                summarize_inbox()
                _rebuild()
            elif path == "/breakdown":
                tid = first("id")
                spice = first("spice", "3")
                if tid.isdigit():
                    match = [t for t in load_tasks() if t["id"] == int(tid)]
                    if match:
                        steps = breakdown(match[0]["title"],
                                          int(spice) if spice.isdigit() else 3)
                        if steps:
                            set_steps(int(tid), steps)
                        _rebuild()
        except Exception:  # noqa: BLE001 — a bad form post must not kill the server
            pass
        # Redirect back to the dashboard (Post/Redirect/Get).
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, *_args):  # keep the daemon log quiet
        return


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Serve the PA dashboard on loopback.")
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args(argv)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"PA dashboard at http://127.0.0.1:{args.port}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
