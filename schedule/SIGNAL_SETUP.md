# Signal nudges — status: ✅ LIVE

Outbound Signal nudges reach Adam's phone. Confirmed 2026-07-20.

## The working setup

```
run_checkin.sh / nudge.sh
   └─ NUDGE_CMD (schedule/nudge.env, git-ignored)
        └─ openclaw message send --channel signal --target +44…
             └─ OpenClaw gateway  →  signal-cli JSON-RPC API @ 127.0.0.1:8080
                  └─ signal-cli 0.14.6 (linked device)  →  Signal  →  phone
```

Components:
- **signal-cli 0.14.6** (`/opt/homebrew/bin`, ARM) — linked as a secondary device to
  +447712553049. (The earlier 409s were an old Intel 0.14.3 build + device contention;
  resolved by reinstalling the ARM build and re-linking cleanly.)
- **signal-cli daemon** on `127.0.0.1:8080` — kept alive by the launch agent
  `com.adamvialsmoore.signal-cli-daemon` (RunAtLoad + KeepAlive). Template in
  `schedule/launchagents/*.plist.example`; the number-filled copy lives only in
  `~/Library/LaunchAgents`.
- **OpenClaw** `channels.signal.enabled = true`, driving signal-cli.
- **nudge.env** (`git-ignored`): `NUDGE_CMD='openclaw message send --channel signal --target +44… -m "$NUDGE_MESSAGE"'`.

## Manage / verify

```bash
launchctl list | grep signal-cli-daemon         # daemon running?
lsof -iTCP:8080 -sTCP:LISTEN                     # :8080 served?
bash schedule/nudge.sh "test — did this reach my phone?"
tail -f /tmp/signal-cli-daemon.log              # daemon logs
```

If the daemon stops serving :8080: `launchctl kickstart -k gui/$(id -u)/com.adamvialsmoore.signal-cli-daemon`.

## Still to wire (two-way / inbound)

Outbound is done. To reply *from* the phone and trigger skills ("today", "capture …"),
bind an OpenClaw agent to this repo — see `ROADMAP.md` (iPhone two-way).
