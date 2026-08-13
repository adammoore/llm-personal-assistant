#!/bin/sh
# imessage_nudge.sh — send one nudge as an iMessage via Messages.app (osascript).
# Adam lives in iMessage, not Signal, so this is the PA's nudge channel. Wired from nudge.sh's
# NUDGE_CMD; the message arrives as $1 (or $NUDGE_MESSAGE), the recipient in $IMESSAGE_TO.
#
# POSIX sh (nudge.sh runs it via `sh -c`). The message + target are passed to AppleScript as ARGV
# (not interpolated into the script text), so quotes/emoji/newlines can't break or inject into it.
# Requires Messages signed in (same account chat.db reads); Automation permission already granted.

MSG="${1:-${NUDGE_MESSAGE:-}}"
TGT="${IMESSAGE_TO:-}"

if [ -z "$MSG" ] || [ -z "$TGT" ]; then
  printf 'imessage_nudge: missing message or IMESSAGE_TO\n' >&2
  exit 1
fi

/usr/bin/osascript - "$MSG" "$TGT" <<'APPLESCRIPT'
on run argv
  set theMsg to item 1 of argv
  set theTgt to item 2 of argv
  tell application "Messages"
    send theMsg to participant theTgt of (1st account whose service type = iMessage)
  end tell
end run
APPLESCRIPT
