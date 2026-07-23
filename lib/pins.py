#!/usr/bin/env python3
"""pins — explicit, cross-type prioritisation for the dashboard's main view.

Adam wants to hand-pick what matters *right now* — a task, a person, a message — rather than
rely only on derived urgency/priority. A pin is a deliberate "this, in my face" signal. Pinned
objects surface together in a Priorities card at the top of the dashboard, independent of type.

Store: data/pins.json = {"task": ["3"], "person": ["cora"], "message": ["<key>"]}. Ids are kept
as strings so task ints, person slugs, and message keys all coexist. Order is preserved =
most-recently-pinned last (the UI can show newest first).
"""

from __future__ import annotations

import json
from pathlib import Path

PINS_PATH = Path(__file__).resolve().parents[1] / "data" / "pins.json"
KINDS = ("task", "person", "message")


def load_pins(path: Path = PINS_PATH) -> dict:
    """{'task': [...], 'person': [...], 'message': [...]} — always all keys present."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    return {k: [str(x) for x in (raw.get(k) or [])] for k in KINDS}


def save_pins(pins: dict, path: Path = PINS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({k: pins.get(k, []) for k in KINDS}, indent=2), encoding="utf-8")


def is_pinned(kind: str, obj_id: str | int, path: Path = PINS_PATH) -> bool:
    return str(obj_id) in load_pins(path).get(kind, [])


def toggle_pin(kind: str, obj_id: str | int, path: Path = PINS_PATH) -> bool:
    """Flip a pin. Returns the new state (True = now pinned). No-op for unknown kinds."""
    if kind not in KINDS:
        return False
    pins = load_pins(path)
    sid = str(obj_id)
    lst = pins[kind]
    if sid in lst:
        lst.remove(sid)
        now_pinned = False
    else:
        lst.append(sid)
        now_pinned = True
    save_pins(pins, path)
    return now_pinned


def count(path: Path = PINS_PATH) -> int:
    p = load_pins(path)
    return sum(len(p[k]) for k in KINDS)
