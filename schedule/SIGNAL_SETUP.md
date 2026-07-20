# Signal nudges — remaining setup (your side)

The nudge path is **wired and correct**: `schedule/nudge.env` routes to
`openclaw message send --channel signal`, and OpenClaw's Signal channel is now enabled.
`nudge.sh` fails non-fatally until the piece below is in place, so schedules run safely
regardless.

## The one blocker

OpenClaw's Signal adapter expects a local signal-cli JSON-RPC/HTTP API at
`http://127.0.0.1:8080`, and `signal-cli listAccounts` is currently empty — i.e. signal-cli
does not yet have your number registered/linked, and nothing is serving the API.

## Steps (must be done by you — involves phone verification)

1. **Register or link signal-cli to your number** (linking as a secondary device is easiest —
   scan the QR with Signal on your phone):
   ```bash
   signal-cli link -n "macbook-pro"      # prints a tsdevice:/ link → render as QR, scan in Signal
   # OR register primary (needs SMS/voice code, possibly a captcha):
   # signal-cli -a <YOUR_NUMBER> register
   # signal-cli -a <YOUR_NUMBER> verify <CODE>
   ```
2. **Serve the API OpenClaw expects on :8080.** Run signal-cli in daemon mode (or a
   signal-cli REST API) bound to `127.0.0.1:8080`. A LaunchAgent (like the existing
   OpenClaw / granola ones) keeps it alive across reboots.
3. **Restart the OpenClaw gateway and test:**
   ```bash
   launchctl kickstart -k "gui/$(id -u)/ai.openclaw.gateway"
   bash schedule/nudge.sh "test — did this reach my phone?"
   ```

Verify delivery: the message should arrive in Signal on your phone. Once it does, the daily
07:30 / weekly Mon 08:00 / monthly 1st 09:00 nudges reach you automatically.

(Registration/verification codes and captchas can't be done by the assistant — that step is
yours.)
