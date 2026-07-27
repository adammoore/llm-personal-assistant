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

from lib.calevent import set_status as event_set_status
from lib.magictodo import breakdown
from lib.mailsummary import summarize as summarize_inbox
from lib.people import (
    cycle_priority,
    seed_from_mail,
    set_fields,
    set_kind,
)
from lib.pins import KINDS as PIN_KINDS
from lib.pins import toggle_pin
from lib.taskstore import (
    CATEGORIES,
    DEFAULT_CATEGORY,
    add_task,
    complete_task,
    delete_task,
    load_tasks,
    set_steps,
    update_task,
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

    def do_GET(self):
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

    def do_POST(self):
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
            elif path == "/delete":
                tid = first("id")
                if tid.isdigit():
                    delete_task(int(tid))
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
            elif path == "/pin":
                # Toggle an explicit priority pin on a task / person / message, then rebuild.
                kind = first("kind")
                obj_id = first("id")
                if kind in PIN_KINDS and obj_id:
                    toggle_pin(kind, obj_id)
                    _rebuild()
            elif path == "/person-kind":
                # Reclassify a person as person/org, then rebuild.
                if set_kind(first("id"), first("kind")):
                    _rebuild()
            elif path == "/person-priority":
                # Cycle a person's priority (low→normal→high→low), then rebuild.
                if cycle_priority(first("id")) is not None:
                    _rebuild()
            elif path == "/event-add":
                # Adam confirms a proposed appointment → queue it for the agent to create
                # (modify_calendar is confirm-required; this IS the confirmation, not the write).
                if event_set_status(first("key"), "confirmed"):
                    _rebuild()
            elif path == "/event-dismiss":
                if event_set_status(first("key"), "dismissed"):
                    _rebuild()
            elif path == "/person-edit":
                # Human correcting machine-guessed metadata on a person.
                if set_fields(first("id"), {
                        "name": first("name"), "kind": first("kind"),
                        "circle": first("circle"), "priority": first("priority"),
                        "context": first("context"), "birthday": first("birthday"),
                        "relationship": first("relationship"), "notes": first("notes")}):
                    _rebuild()
            elif path == "/refresh":
                # The slow, network path: refresh mail+calendar (glance), Reminders, and the
                # unified inbox into their caches, THEN rebuild. Mutations only rebuild (instant).
                for script, extra, to in ((REPO / "lib/glance.py", [], 90),
                                          (REPO / "lib/reminders.py", [], 30),
                                          (REPO / "lib/inbox.py", ["--cache"], 90),
                                          (REPO / "lib/brief.py", [], 120)):
                    subprocess.run(["python3", str(script), *extra],
                                   check=False, capture_output=True, timeout=to)
                _rebuild()
            elif path == "/pull-work":
                # Read the open Enact work tabs into data/work_cache.json, then rebuild.
                # Slow and needs the Enact Chrome; capture output and cap the runtime so a
                # hung/absent browser can't wedge the request.
                subprocess.run(
                    ["python3", str(REPO / "skills" / "work-pull" / "pull.py"), "--cache"],
                    check=False, capture_output=True, timeout=120,
                )
                _rebuild()
            elif path == "/summarize-mail":
                summarize_inbox()
                _rebuild()
            elif path == "/sync-people":
                seed_from_mail()
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
        # AJAX callers (the dashboard's own fetch) update the DOM themselves and don't want a
        # navigation — reply 204 (no reload). Plain form posts get Post/Redirect/Get as before.
        if self.headers.get("X-PA-Ajax"):
            self.send_response(204)
            self.end_headers()
            return
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
