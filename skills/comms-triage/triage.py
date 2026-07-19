#!/usr/bin/env python3
"""comms-triage — a prioritised, per-account inbox shortlist with message ids.

The read-only data layer for the `comms-triage` skill. It gathers recent mail for both
accounts (via the shared lib), hides obvious noise, and prints a shortlist that INCLUDES
the himalaya envelope id + account for each item — so the skill can then read a specific
body (`himalaya message read <id> -a <acct>`) and propose a draft reply.

Read-only: this script never reads bodies, drafts, or sends. Accounts stay separate.

Usage: python3 skills/comms-triage/triage.py [--per-account 10] [--account personal|fairres]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lib.comms import ACCOUNTS, fetch_inbox, partition_inbox  # noqa: E402


def build_triage(per_account: int, only: str | None) -> str:
    """Assemble the per-account triage shortlist as markdown."""
    lines = ["# Inbox triage", ""]
    accounts = [a for a in ACCOUNTS if not only or a["id"] == only]
    for acct in accounts:
        worth, noise = partition_inbox(fetch_inbox(acct["mail"], limit=max(per_account * 3, 25)))
        shown = worth[:per_account]
        lines.append(f"## {acct['id']} — {acct['cal']}")
        if not shown:
            lines.append(f"_Nothing standing out ({noise} newsletters/receipts hidden)._\n")
            continue
        for m in shown:
            dot = "•" if m["unread"] else "◦"
            # id + account label make each line actionable by the skill.
            lines.append(f"- {dot} `[{acct['id']} #{m['id']}]` **{m['from']}** — "
                         f"{m['subject'][:80]}  _{m['date']}_")
        extra = len(worth) - len(shown)
        note = f"_{noise} noise hidden"
        note += f", +{extra} more worth a look_" if extra else "_"
        lines.append(note + "\n")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prioritised inbox shortlist for triage.")
    p.add_argument("--per-account", type=int, default=10, help="max items shown per account")
    p.add_argument("--account", default=None, choices=[a["id"] for a in ACCOUNTS],
                   help="restrict to one account")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    print(build_triage(args.per_account, args.account))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
