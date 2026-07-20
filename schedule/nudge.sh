#!/usr/bin/env bash
#
# nudge.sh — send a single Signal nudge, safely and configurably.
#
# The PA's scheduled check-ins call this to invite Adam (never to demand). It is
# deliberately SAFE BY DEFAULT: with no configuration it sends nothing and just logs what
# it *would* have sent, so wiring the schedules can never spam you by accident.
#
# Configure by copying schedule/nudge.env.example -> schedule/nudge.env (git-ignored) and
# setting ONE of:
#   • SIGNAL_FROM + SIGNAL_TO   -> sends via signal-cli
#   • NUDGE_CMD                 -> any command; the message arrives in $NUDGE_MESSAGE
#                                  (e.g. an OpenClaw / send_signal_alert wrapper)
#
# Usage:  nudge.sh "message text"
# Exit:   0 always (a nudge must never break the scheduled job); logs outcome.

set -euo pipefail

MESSAGE="${1:-}"
if [[ -z "${MESSAGE}" ]]; then
  echo "nudge.sh: empty message, nothing to send" >&2
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/nudge.env"

# Load config if present (git-ignored; never committed).
if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
fi

# Preferred: an explicit custom command (OpenClaw / adam-local send_signal_alert wrapper).
if [[ -n "${NUDGE_CMD:-}" ]]; then
  export NUDGE_MESSAGE="${MESSAGE}"
  # The custom command references $NUDGE_MESSAGE itself; run it in a subshell.
  if sh -c "${NUDGE_CMD}"; then
    echo "nudge.sh: sent via NUDGE_CMD"
  else
    echo "nudge.sh: NUDGE_CMD failed (non-fatal)" >&2
  fi
  exit 0
fi

# Fallback: signal-cli, if from/to are configured and the binary exists.
if [[ -n "${SIGNAL_FROM:-}" && -n "${SIGNAL_TO:-}" ]] && command -v signal-cli >/dev/null 2>&1; then
  if signal-cli -a "${SIGNAL_FROM}" send "${SIGNAL_TO}" -m "${MESSAGE}" >/dev/null 2>&1; then
    echo "nudge.sh: sent via signal-cli"
  else
    echo "nudge.sh: signal-cli send failed (non-fatal)" >&2
  fi
  exit 0
fi

# Unconfigured: safe no-op. Log the intended message so scheduling can be verified.
echo "nudge.sh: not configured (no NUDGE_CMD or SIGNAL_FROM/SIGNAL_TO) — would have sent:"
echo "  ${MESSAGE}"
exit 0
