#!/usr/bin/env python3
"""surface_audit — what the PA reads (ingest) and where it reaches Adam (surfaces), plus health.

A repeatable, read-only diagnostic. Run it to see at a glance which INPUT sources are fresh / stale
/ blind and which OUTPUT surfaces are live — with an explicit OFF-DESKTOP column, since the desktop
dashboard is only one surface and the phone/Watch/Siri/Signal reach is what's easy to leave broken.

    python3 lib/surface_audit.py            # readable report
    python3 lib/surface_audit.py --json     # machine-readable

Each row: kind (ingest|surface), name, direction (in|out|both), off_desktop, status, detail.
Status vocabulary: live/fresh · stale · blind (should have data, doesn't) · absent (not wired).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"


def _cache(name: str) -> dict:
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _age_h(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        return (datetime.now() - datetime.fromisoformat(str(iso)[:19])).total_seconds() / 3600
    except ValueError:
        return None


def _freshness(age: float | None, fresh: float = 2, stale: float = 24) -> str:
    if age is None:
        return "?"
    return "fresh" if age <= fresh else ("stale" if age <= stale else "old")


def _row(kind, name, direction, off, status, detail):
    return {"kind": kind, "name": name, "direction": direction, "off_desktop": off,
            "status": status, "detail": detail}


def _http_ok(url: str, timeout: int = 5) -> bool:
    import urllib.error
    import urllib.request
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 400
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _imessage_latest() -> str | None:
    try:
        import sys
        sys.path.insert(0, str(REPO))
        from lib.imessage import _connect
        r = _connect().execute(
            "SELECT datetime(MAX(date)/1000000000 + 978307200,'unixepoch','localtime') "
            "FROM message").fetchone()
        return r[0] if r else None
    except Exception:  # noqa: BLE001 — diagnostic must never raise
        return None


def audit() -> list[dict]:
    rows: list[dict] = []

    # ---- INGEST (what the PA reads in) --------------------------------------------------------
    g = _cache("glance_cache.json")
    gage = _age_h(g.get("at"))
    mail_n = sum(len(v.get("worth", [])) for v in (g.get("mail") or {}).values())
    ev_n = sum(len(v) for v in (g.get("events") or {}).values())
    rows.append(_row("ingest", "mail (himalaya)", "in", False,
                     "blind" if g and mail_n == 0 else _freshness(gage), f"{mail_n} worth-a-look"))
    rows.append(_row("ingest", "calendar (gog)", "in", False,
                     "blind" if g and ev_n == 0 else _freshness(gage), f"{ev_n} events"))

    inbox = _cache("inbox_cache.json").get("items", [])
    rows.append(_row("ingest", "unified inbox", "in", False,
                     "live" if inbox else "blind", f"{len(inbox)} items"))

    im = _imessage_latest()
    im_age = _age_h(im and im.replace(" ", "T"))
    rows.append(_row("ingest", "iMessage/SMS (chat.db+WAL)", "in", True,
                     "blind" if im_age is None else _freshness(im_age, 24, 72),
                     f"latest {im or '—'}"))

    rem = _cache("reminders_cache.json")
    rows.append(_row("ingest", "Apple Reminders (mirror)", "in", True,
                     "live" if rem.get("ok") else "blind", f"{len(rem.get('items', []))} open"))

    work = _cache("work_cache.json")
    rows.append(_row("ingest", "work (Enact Chrome/CDP)", "in", False,
                     "live" if work.get("up") else "absent",
                     "up" if work.get("up") else "Enact Chrome not pulled"))

    gran = _cache("granola_cache.json").get("items", [])
    rows.append(_row("ingest", "Granola meetings", "in", False,
                     "live" if gran else "absent", f"{len(gran)} cached"))

    cpath = Path.home() / "cider-outputs" / ".store" / "activity_cache.json"
    try:
        cider = json.loads(cpath.read_text(encoding="utf-8")) if cpath.exists() else {}
    except (OSError, ValueError):
        cider = {}
    rows.append(_row("ingest", "cider-store atoms", "in", False,
                     "live" if cider.get("items") else "absent",
                     f"{len(cider.get('items', []))} atoms"))

    wa_exe = shutil.which("wacli") or (Path.home() / "go/bin/wacli").exists()
    wa_wired = (REPO / "lib" / "whatsapp.py").exists()
    rows.append(_row("ingest", "WhatsApp (wacli)", "in", True,
                     "live" if (wa_exe and wa_wired) else ("absent" if wa_exe else "missing"),
                     "wired into event ingest (read-only)" if wa_wired else "CLI present, not wired"))
    rows.append(_row("ingest", "Signal inbound (OpenClaw)", "in", True,
                     "absent", "outbound only — no inbound read (reply-to-confirm)"))

    # ---- SURFACES (where the PA reaches Adam) -------------------------------------------------
    rows.append(_row("surface", "dashboard — desktop", "out", False,
                     "live" if _http_ok("http://127.0.0.1:8787/") else "down", "127.0.0.1:8787"))

    ts_url = ""
    try:
        out = subprocess.run(["tailscale", "serve", "status"], capture_output=True, text=True,
                             timeout=8).stdout
        for line in out.splitlines():
            if "8443" in line and "ts.net" in line:
                ts_url = line.split()[0]
    except (subprocess.SubprocessError, OSError):
        pass
    rows.append(_row("surface", "dashboard — tailnet (mobile)", "out", True,
                     "live" if ts_url else "absent", ts_url or "no tailscale serve mapping"))

    nudge_env = (REPO / "schedule" / "nudge.env")
    rows.append(_row("surface", "Signal nudges (OpenClaw)", "out", True,
                     "live" if nudge_env.exists() else "absent",
                     "nudge.env present" if nudge_env.exists() else "not configured"))

    pushed = _cache("pushed_reminders.json")
    rows.append(_row("surface", "Apple Reminders push (tasks)", "out", True,
                     "live" if pushed else "idle",
                     f"{len(pushed)} tasks on 'PA Tasks' list"))

    focus_note = (REPO / "skills" / "focus" / "focus.py")
    rows.append(_row("surface", "Apple Note push (focus)", "out", True,
                     "available" if focus_note.exists() else "absent", "focus --push-note"))

    brief = _cache("brief_cache.json")
    rows.append(_row("surface", "situational brief", "out", False,
                     _freshness(_age_h(brief.get("at"))), "claude -p, 90-min throttle"))

    return rows


def main() -> int:
    import sys
    rows = audit()
    if "--json" in sys.argv:
        print(json.dumps(rows, indent=2))
        return 0
    mark = {"fresh": "🟢", "live": "🟢", "available": "🟢", "stale": "🟡", "idle": "🟡",
            "old": "🟠", "blind": "🔴", "down": "🔴", "absent": "⚪", "missing": "⚪", "?": "⚪"}
    for kind in ("ingest", "surface"):
        print(f"\n{'INGEST (reads in)' if kind == 'ingest' else 'SURFACES (reaches Adam)'}")
        for r in [x for x in rows if x["kind"] == kind]:
            off = "📱" if r["off_desktop"] else "  "
            print(f"  {mark.get(r['status'], '·')} {off} {r['name']:30} {r['status']:8} "
                  f"{r['direction']:4} {r['detail']}")
    gaps = [r for r in rows if r["status"] in ("blind", "down", "absent", "missing")]
    off_gaps = [r for r in gaps if r["off_desktop"]]
    print(f"\n{len(gaps)} gaps ({len(off_gaps)} off-desktop): "
          + ", ".join(r["name"] for r in gaps))
    return 0


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(REPO))
    raise SystemExit(main())
