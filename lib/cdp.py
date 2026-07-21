#!/usr/bin/env python3
"""cdp — a tiny zero-dependency Chrome DevTools Protocol client.

Talks to a Chrome launched with --remote-debugging-port (Adam's dedicated Enact profile runs
one on 127.0.0.1:9222). Lets the PA *read* the content of already-open, already-logged-in
work tabs (Outlook, Teams, Slack) over CDP — no credentials, no scraping of a login, no
extension. Read-only: it evaluates JS to pull visible text; it does not click or navigate.

Implements just enough of the WebSocket protocol (RFC 6455 client framing) to send one
Runtime.evaluate and read the reply, using only the standard library.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import struct
import urllib.request
from urllib.parse import urlparse

HOST, PORT = "127.0.0.1", 9222


def is_up(host: str = HOST, port: int = PORT) -> bool:
    """True if a CDP endpoint is reachable."""
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def targets(host: str = HOST, port: int = PORT) -> list[dict]:
    """List open page targets (tabs) via the CDP HTTP endpoint."""
    with urllib.request.urlopen(f"http://{host}:{port}/json", timeout=5) as r:
        return [t for t in json.load(r) if t.get("type") == "page"]


def find(url_substr: str, host: str = HOST, port: int = PORT) -> dict | None:
    """First page target whose URL contains `url_substr`."""
    for t in targets(host, port):
        if url_substr in t.get("url", ""):
            return t
    return None


# --- minimal RFC 6455 websocket client (client frames must be masked) --------------------

def _read_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed mid-frame")
        buf += chunk
    return buf


def _handshake(sock: socket.socket, path: str, host: str, port: int) -> None:
    key = base64.b64encode(os.urandom(16)).decode()
    req = (f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
           f"Sec-WebSocket-Version: 13\r\n\r\n")
    sock.sendall(req.encode())
    resp = b""
    while b"\r\n\r\n" not in resp:
        resp += sock.recv(4096)
    if b" 101 " not in resp.split(b"\r\n", 1)[0]:
        raise ConnectionError(f"ws upgrade failed: {resp[:80]!r}")


def _send_text(sock: socket.socket, text: str) -> None:
    payload = text.encode()
    header = bytearray([0x81])  # FIN + text opcode
    n = len(payload)
    mask_bit = 0x80
    if n < 126:
        header.append(mask_bit | n)
    elif n < 65536:
        header.append(mask_bit | 126)
        header += struct.pack(">H", n)
    else:
        header.append(mask_bit | 127)
        header += struct.pack(">Q", n)
    mask = os.urandom(4)
    header += mask
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    sock.sendall(bytes(header) + masked)


def _recv_message(sock: socket.socket) -> str:
    """Read one (possibly fragmented) text message; skip control/ping frames."""
    chunks = []
    while True:
        b1, b2 = _read_exact(sock, 2)
        fin, opcode = b1 & 0x80, b1 & 0x0F
        length = b2 & 0x7F
        if length == 126:
            length = struct.unpack(">H", _read_exact(sock, 2))[0]
        elif length == 127:
            length = struct.unpack(">Q", _read_exact(sock, 8))[0]
        data = _read_exact(sock, length) if length else b""
        if opcode == 0x8:  # close
            raise ConnectionError("ws closed by peer")
        if opcode in (0x9, 0xA):  # ping / pong — ignore
            continue
        chunks.append(data)
        if fin:
            break
    return b"".join(chunks).decode("utf-8", "replace")


def evaluate(target: dict, expression: str, timeout: int = 20):
    """Run JS in a target tab and return the (JSON-serialisable) result value, or None."""
    ws_url = target["webSocketDebuggerUrl"]
    u = urlparse(ws_url)
    sock = socket.create_connection((u.hostname, u.port), timeout=timeout)
    sock.settimeout(timeout)
    try:
        _handshake(sock, u.path, u.hostname, u.port)
        _send_text(sock, json.dumps({
            "id": 1, "method": "Runtime.evaluate",
            "params": {"expression": expression, "returnByValue": True, "awaitPromise": True},
        }))
        while True:
            msg = json.loads(_recv_message(sock))
            if msg.get("id") == 1:
                return msg.get("result", {}).get("result", {}).get("value")
    finally:
        sock.close()


def read_text(url_substr: str, selector: str = "body", *, limit: int = 6000) -> str | None:
    """Return the visible text of `selector` in the first tab matching url_substr (trimmed)."""
    t = find(url_substr)
    if not t:
        return None
    expr = (f"(document.querySelector({selector!r})||document.body)"
            f".innerText.slice(0,{limit})")
    return evaluate(t, expr)


def read_best(url_substr: str, selectors: list[str], *, limit: int = 2500) -> str | None:
    """Read the first selector that yields substantial text, falling back to body.

    Web apps (OWA, Teams, Slack) change their DOM often, so we try a prioritised list of
    selectors and take the first with real content — the caller (a summarising skill)
    tolerates messy text. Returns None if the tab isn't open.
    """
    t = find(url_substr)
    if not t:
        return None
    sel_js = json.dumps(selectors)
    expr = f"""(function(){{
      var sels={sel_js};
      for(var i=0;i<sels.length;i++){{
        var e=document.querySelector(sels[i]);
        if(e&&e.innerText&&e.innerText.trim().length>40) return e.innerText.slice(0,{limit});
      }}
      return document.body.innerText.slice(0,{limit});
    }})()"""
    return evaluate(t, expr)
