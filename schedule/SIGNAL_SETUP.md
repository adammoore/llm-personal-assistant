# Signal — status: ✅ LIVE (send + receive)

Signal nudges reach Adam's phone, and inbound Signal messages are operationalised into tasks.

## Architecture (important correction, 2026-07-21)

**OpenClaw manages signal-cli itself.** Its Signal provider launches and owns the signal-cli
JSON-RPC daemon on `127.0.0.1:8080` for both send and receive.

> ⚠️ Do **not** run a separate signal-cli daemon (e.g. a `com.adamvialsmoore.signal-cli-daemon`
> LaunchAgent). It grabs the account config lock, OpenClaw's own provider then can't start
> (`Config file is in use by another instance`), and **inbound Signal silently dies** — only
> outbound squeaks through. This exact conflict was found and removed on 2026-07-21.

## The working setup

```
outbound:  run_checkin.sh / nudge.sh → NUDGE_CMD (schedule/nudge.env, git-ignored)
             → openclaw message send --channel signal → OpenClaw's signal-cli daemon → phone
inbound:   phone → Signal → OpenClaw signal provider → the bound "anthropic" agent
             → (guided by ~/.openclaw/workspace-anthropic/CLAUDE.md) runs the PA skills
             → captures todos into the task store, replies
```

- **signal-cli 0.14.6** (ARM), linked device for `+447712553049`. OpenClaw starts the daemon.
- **OpenClaw** `channels.signal.enabled = true`; agent `anthropic` bound to signal.
- **Inbound behaviour** is defined in `~/.openclaw/workspace-anthropic/CLAUDE.md`: send a todo
  → it runs `task-capture` per item and rebuilds the dashboard.

## Manage / verify

```bash
lsof -iTCP:8080 -sTCP:LISTEN                       # OpenClaw's signal-cli serving?
tail -f ~/.openclaw/logs/gateway.log              # gateway + signal provider
bash schedule/nudge.sh "test"                     # outbound
# inbound: text yourself a todo on Signal → it should land in the dashboard tasks
launchctl kickstart -k gui/$(id -u)/ai.openclaw.gateway   # restart if signal is stuck
```
