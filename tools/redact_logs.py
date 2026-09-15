"""Produce committable, redacted copies of the read-only probe logs.

The raw probe logs contain account balances, open positions and masked account
identifiers. Those are the operator's private financial data and are excluded from
version control (see .gitignore). This script keeps only the evidence the project
actually needs — that the API works, what it supports, and what its limits are —
and removes everything that describes the operator's portfolio.

Usage:  python tools/redact_logs.py
Input:  logs/probe_*.json            (git-ignored, local only)
Output: logs/redacted/probe_*.json   (committed)
"""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"
OUT = LOGS / "redacted"

REDACTED = "[REDACTED]"

# Numeric account fields: replaced wholesale, never rounded or bucketed
# (a bucket still leaks net worth).
MONEY_FIELDS = {
    "power", "max_power_short", "net_cash_power", "total_assets", "cash",
    "market_val", "long_mv", "short_mv", "frozen_cash", "avl_withdrawal_cash",
    "initial_margin", "maintenance_margin", "margin_call_margin", "qty",
    "can_sell_qty", "cost_price", "available_funds", "risk_level", "risk_status",
}

# Identity fields.
ID_FIELDS = {"acc_id", "card_num", "uni_card_num"}

# Capability fields that are safe and genuinely needed by the project.
KEEP_ACCOUNT_FIELDS = {
    "firm", "filter_market", "trd_env", "acc_type", "security_firm",
    "sim_acc_type", "trdmarket_auth",
}

# Checks whose *detail* describes the portfolio or the operator's research history.
PORTFOLIO_CHECKS = re.compile(
    r"^(accinfo_query|position_list_query|order_list_query)", re.I
)
# get_history_kl_quota(get_detail=True) lists every symbol recently researched.
QUOTA_DETAIL_CHECK = re.compile(r"^get_history_kl_quota \(after use\)", re.I)


def scrub(node):
    """Recursively redact money/identity fields anywhere in the structure."""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k in ID_FIELDS or k in MONEY_FIELDS:
                out[k] = REDACTED
            else:
                out[k] = scrub(v)
        return out
    if isinstance(node, list):
        return [scrub(x) for x in node]
    return node


def redact_check(check: dict) -> dict:
    name = str(check.get("check", ""))

    if PORTFOLIO_CHECKS.match(name):
        # Keep the fact that the call succeeded; drop everything it returned.
        return {
            "check": re.sub(r"acc=\S+", "acc=[REDACTED]", name),
            "ok": check.get("ok"),
            "detail": f"{REDACTED} — call succeeded; account balances and positions "
                      f"are intentionally not committed to version control",
        }

    if QUOTA_DETAIL_CHECK.match(name):
        detail = check.get("detail")
        used = remain = REDACTED
        if isinstance(detail, (list, tuple)) and len(detail) >= 2:
            used, remain = detail[0], detail[1]
        # Keep the quota numbers; drop the per-symbol research history.
        return {
            "check": name,
            "ok": check.get("ok"),
            "detail": {
                "used": used,
                "remaining": remain,
                "symbol_detail": f"{REDACTED} — reveals which instruments were researched",
            },
        }

    return scrub(check)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sources = sorted(p for p in LOGS.glob("probe_*.json") if p.is_file())
    if not sources:
        print("no raw probe logs found in logs/ — nothing to redact")
        return 1

    for src in sources:
        data = json.loads(src.read_text(encoding="utf-8"))
        data["checks"] = [redact_check(c) for c in data.get("checks", [])]

        if "accounts_found" in data:
            data["accounts_found"] = [
                {k: v for k, v in scrub(a).items() if k in KEEP_ACCOUNT_FIELDS}
                for a in data["accounts_found"]
            ]

        data["_redaction"] = (
            "Account identifiers, balances, positions and researched-symbol history "
            "removed. Raw logs are retained locally and are git-ignored."
        )

        # Shorten: the raw timestamped names blow past Windows' 260-char path limit
        # once the workspace prefix is added.
        short = re.sub(r"T\d+\+\d+", "", src.stem) + ".json"
        dst = OUT / short
        data["_source_log"] = src.name
        dst.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{src.name} -> logs/redacted/{short}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
