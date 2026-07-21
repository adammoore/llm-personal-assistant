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

REPO = Path(__file__).resolve().parent
DASHBOARD = REPO / "data" / "PA_DASHBOARD.html"


def _ensure_built() -> None:
    """Build the dashboard once if it does not exist yet (e.g. first run)."""
    if not DASHBOARD.exists():
        subprocess.run(["python3", str(REPO / "build_pa_dashboard.py")],
                       check=False, capture_output=True, timeout=60)


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
