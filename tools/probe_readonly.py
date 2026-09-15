"""Stage A read-only feasibility probe against a locally running moomoo OpenD.

SAFETY: this script is strictly read-only. It never calls place_order, modify_order,
unlock_trade, or any write API. Grep check in tests/test_probe_is_readonly.py.

Usage:  python tools/probe_readonly.py [--host 127.0.0.1] [--port 11111]
Output: human-readable log to stdout; JSON summary to logs/probe_<UTC>.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from datetime import datetime, timezone

FORBIDDEN = (
    "place_order",
    "modify_order",
    "unlock_trade",
    "cancel_all",
    "set_",
)

RESULT: dict = {"checks": []}


def mask(value: object) -> str:
    """Mask account identifiers so logs can be shared."""
    s = str(value)
    return s if len(s) <= 4 else f"{s[:2]}{'*' * (len(s) - 4)}{s[-2:]}"


def record(name: str, ok: bool, detail: object) -> None:
    RESULT["checks"].append({"check": name, "ok": ok, "detail": detail})
    flag = "OK " if ok else "ERR"
    print(f"[{flag}] {name}: {detail}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=11111)
    args = ap.parse_args()

    RESULT["utc"] = datetime.now(timezone.utc).isoformat()
    RESULT["host"] = args.host
    RESULT["port"] = args.port
    RESULT["python"] = sys.version.split()[0]
    RESULT["platform"] = platform.platform()

    try:
        import moomoo as mm
    except ImportError as exc:  # pragma: no cover
        record("import moomoo", False, repr(exc))
        return 2

    RESULT["sdk_version"] = getattr(mm, "__version__", "unknown")
    record("sdk version", True, RESULT["sdk_version"])

    # ---------------- quote side ----------------
    quote = None
    try:
        quote = mm.OpenQuoteContext(host=args.host, port=args.port)
        record("OpenQuoteContext", True, f"connected to {args.host}:{args.port}")
    except Exception as exc:
        record("OpenQuoteContext", False, repr(exc))
        return 3

    try:
        ret, data = quote.get_global_state()
        record("get_global_state", ret == mm.RET_OK, data)
    except Exception as exc:
        record("get_global_state", False, repr(exc))

    try:
        ret, data = quote.get_history_kl_quota(get_detail=False)
        record("get_history_kl_quota", ret == mm.RET_OK, data)
    except Exception as exc:
        record("get_history_kl_quota", False, repr(exc))

    # Market state for a couple of liquid, non-leveraged US ETFs we may use later.
    for code in ("US.SPY", "US.AGG", "US.BIL"):
        try:
            ret, data = quote.get_market_state([code])
            record(f"get_market_state {code}", ret == mm.RET_OK,
                   data.to_dict("records") if ret == mm.RET_OK else data)
        except Exception as exc:
            record(f"get_market_state {code}", False, repr(exc))

    # Daily history availability + how far back data actually goes.
    for code in ("US.SPY", "US.AGG"):
        try:
            ret, data, _ = quote.request_history_kline(
                code, start="1993-01-01", end="2026-09-12",
                ktype=mm.KLType.K_DAY, autype=mm.AuType.QFQ, max_count=5)
            if ret == mm.RET_OK:
                record(f"request_history_kline {code} (first rows)", True,
                       {"rows_returned": len(data),
                        "earliest": data["time_key"].iloc[0] if len(data) else None,
                        "columns": list(data.columns)})
            else:
                record(f"request_history_kline {code}", False, data)
        except Exception as exc:
            record(f"request_history_kline {code}", False, repr(exc))

    try:
        ret, data = quote.get_history_kl_quota(get_detail=True)
        record("get_history_kl_quota (after use)", ret == mm.RET_OK, data)
    except Exception as exc:
        record("get_history_kl_quota (after use)", False, repr(exc))

    quote.close()

    # ---------------- trade side (read-only) ----------------
    firms = ["FUTUSECURITIES", "FUTUINC", "FUTUSG", "FUTUAU", "FUTUJP", "FUTUMY", "FUTUCA"]
    markets = ["US", "HK", "SG"]
    accounts: list[dict] = []

    for firm_name in firms:
        firm = getattr(mm.SecurityFirm, firm_name)
        for market_name in markets:
            market = getattr(mm.TrdMarket, market_name)
            ctx = None
            try:
                ctx = mm.OpenSecTradeContext(
                    filter_trdmarket=market, host=args.host, port=args.port,
                    security_firm=firm)
                ret, data = ctx.get_acc_list()
                if ret == mm.RET_OK and len(data):
                    rows = []
                    for _, r in data.iterrows():
                        rows.append({
                            "firm": firm_name,
                            "filter_market": market_name,
                            "acc_id": mask(r.get("acc_id")),
                            "trd_env": r.get("trd_env"),
                            "acc_type": r.get("acc_type"),
                            "card_num": mask(r.get("card_num")),
                            "security_firm": r.get("security_firm"),
                            "sim_acc_type": r.get("sim_acc_type"),
                            "trdmarket_auth": r.get("trdmarket_auth"),
                            "uni_card_num": mask(r.get("uni_card_num")),
                        })
                    accounts.extend(rows)
                    record(f"get_acc_list {firm_name}/{market_name}", True, rows)
            except Exception as exc:
                msg = repr(exc)
                if "not exist" not in msg.lower():
                    record(f"get_acc_list {firm_name}/{market_name}", False, msg[:200])
            finally:
                if ctx is not None:
                    try:
                        ctx.close()
                    except Exception:
                        pass

    RESULT["accounts_found"] = accounts
    if not accounts:
        record("account discovery", False, "no trading accounts visible via API")

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    os.makedirs(out_dir, exist_ok=True)
    stamp = RESULT["utc"].replace(":", "").replace("-", "").replace(".", "")
    path = os.path.join(out_dir, f"probe_{stamp}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(RESULT, fh, indent=2, default=str)
    print(f"\nJSON summary written to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
