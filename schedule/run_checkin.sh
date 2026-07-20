#!/usr/bin/env bash
#
# run_checkin.sh — the scheduled half of a check-in.
#
# A launchd job runs this at the cadence boundary. It does the DETERMINISTIC prep (runs the
# relevant glance/horizon/review to refresh the durable note), then sends ONE skippable
# Signal invitation. It does NOT run the interactive check-in — that happens when Adam
# engages (ignoring the nudge is the zero-consequence skip).
#
# Usage:  run_checkin.sh <daily|weekly|monthly>
# Env:    DRY_RUN=1  -> do the prep + compose the nudge, but log it instead of sending.

set -euo pipefail

# launchd starts with a bare PATH; make the tools we need resolvable.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

CADENCE="${1:-}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${REPO}/data/logs"
mkdir -p "${LOG_DIR}"
LOG="${LOG_DIR}/checkin-${CADENCE:-unknown}.log"

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >>"${LOG}"; }

# Map cadence -> prep script and the invitation wording.
case "${CADENCE}" in
  daily)
    PREP="skills/checkin-daily/glance.py"
    INVITE="☀️ Morning. Want to look at today? A quiet glance is ready — reply 'today' to start, or ignore. No pressure."
    ;;
  weekly)
    PREP="skills/checkin-weekly/horizon.py"
    INVITE="🗓️ New week. Fancy a step back? The fortnight ahead is mapped — reply 'week' to look, or skip. Whenever suits."
    ;;
  monthly)
    PREP="skills/checkin-monthly/review.py"
    INVITE="🌙 Month's turning. Up for a gentle review of how it went? Reply 'month' to start, or leave it. Entirely optional."
    ;;
  *)
    echo "usage: $0 <daily|weekly|monthly>" >&2
    exit 2
    ;;
esac

log "start ${CADENCE} check-in"

# Prep: refresh the durable note. Non-fatal on failure — still send the invitation.
if python3 "${REPO}/${PREP}" >>"${LOG}" 2>&1; then
  log "prep ok (${PREP})"
else
  log "prep failed (${PREP}) — sending invitation anyway"
fi

# Daily also refreshes the phone-synced "PA Today" Apple Note (passive glance on the phone).
if [[ "${CADENCE}" == "daily" ]]; then
  if python3 "${REPO}/skills/checkin-daily/push_today.py" >>"${LOG}" 2>&1; then
    log "PA Today note refreshed"
  else
    log "PA Today refresh failed (non-fatal)"
  fi
fi

# Send (or, in DRY_RUN, just log) the skippable invitation.
if [[ "${DRY_RUN:-0}" == "1" ]]; then
  log "DRY_RUN — would nudge: ${INVITE}"
  echo "DRY_RUN nudge: ${INVITE}"
else
  "${REPO}/schedule/nudge.sh" "${INVITE}" >>"${LOG}" 2>&1 || log "nudge non-fatal error"
  log "nudge dispatched"
fi

log "done ${CADENCE} check-in"
