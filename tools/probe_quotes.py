"""Stage A read-only probe #2: US market-data entitlements and account snapshot.

Strictly read-only. No order/unlock/modify calls.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import moomoo as mm

HOST, PORT = "127.0.0.1", 11111
OUT: dict = {"utc": datetime.now(timezone.utc).isoformat(), "checks": []}


def rec(name: str, ok: bool, detail: object) -> None:
    OUT["checks"].append({"check": name, "ok": ok, "detail": detail})
    print(f"[{'OK ' if ok else 'ERR'}] {name}: {detail}")


def mask(v: object) -> str:
    s = str(v)
    return s if len(s) <= 4 else f"{s[:2]}{'*' * (len(s) - 4)}{s[-2:]}"


q = mm.OpenQuoteContext(host=HOST, port=PORT)

# --- entitlement: does a real-time subscription succeed, and is the tick live? ---
codes = ["US.SPY", "US.IEF", "US.BIL"]
ret, data = q.subscribe(codes, [mm.SubType.QUOTE], subscribe_push=False)
rec("subscribe QUOTE (US ETFs)", ret == mm.RET_OK, data)

if ret == mm.RET_OK:
    ret2, snap = q.get_stock_quote(codes)
    if ret2 == mm.RET_OK:
        want = ["code", "data_date", "data_time", "last_price", "prev_close_price",
                "volume", "update_time"]
        cols = [c for c in want if c in snap.columns]
        rec("get_stock_quote", True, snap[cols].to_dict("records"))
        rec("get_stock_quote columns", True, list(snap.columns))
    else:
        rec("get_stock_quote", False, snap)

ret, data = q.query_subscription()
rec("query_subscription (quota)", ret == mm.RET_OK, data)

# --- order book / broker queue require LV2; probe to see entitlement level ---
ret, data = q.subscribe(["US.SPY"], [mm.SubType.ORDER_BOOK], subscribe_push=False)
rec("subscribe ORDER_BOOK US.SPY (LV2 probe)", ret == mm.RET_OK, str(data)[:300])

# --- intraday bar availability (for execution timing decisions) ---
for kt, label in ((mm.KLType.K_1M, "1min"), (mm.KLType.K_5M, "5min")):
    ret, data, _ = q.request_history_kline(
        "US.SPY", start="2026-09-10", end="2026-09-12", ktype=kt,
        autype=mm.AuType.QFQ, max_count=3)
    rec(f"request_history_kline SPY {label}", ret == mm.RET_OK,
        data.to_dict("records") if ret == mm.RET_OK else str(data)[:300])

# --- trading calendar & static info (needed for universe + timing) ---
ret, data = q.request_trading_days(market=mm.TradeDateMarket.US,
                                   start="2026-09-01", end="2026-09-30")
rec("request_trading_days US", ret == mm.RET_OK, str(data)[:300])

ret, data = q.get_stock_basicinfo(mm.Market.US, mm.SecurityType.ETF, ["US.SPY", "US.IEF"])
rec("get_stock_basicinfo ETF", ret == mm.RET_OK,
    data.to_dict("records") if ret == mm.RET_OK else str(data)[:300])

q.close()

# --- account snapshot, read-only, REAL SG account + SIMULATE account ---
for env_name, firm_name in (("REAL", "FUTUSG"), ("SIMULATE", "FUTUSG")):
    env = getattr(mm.TrdEnv, env_name)
    firm = getattr(mm.SecurityFirm, firm_name)
    t = mm.OpenSecTradeContext(filter_trdmarket=mm.TrdMarket.US, host=HOST, port=PORT,
                               security_firm=firm)
    ret, accs = t.get_acc_list()
    if ret != mm.RET_OK:
        rec(f"acc_list {env_name}", False, accs)
        t.close()
        continue
    sel = accs[accs["trd_env"] == env_name]
    if not len(sel):
        rec(f"acc_list {env_name}", False, "no account for this env")
        t.close()
        continue
    acc_id = int(sel.iloc[0]["acc_id"])

    ret, info = t.accinfo_query(trd_env=env, acc_id=acc_id, currency=mm.Currency.USD)
    if ret == mm.RET_OK:
        cols = [c for c in ["power", "max_power_short", "net_cash_power", "total_assets",
                            "cash", "market_val", "long_mv", "short_mv", "frozen_cash",
                            "avl_withdrawal_cash", "currency", "available_funds",
                            "initial_margin", "maintenance_margin", "risk_level",
                            "risk_status", "margin_call_margin"] if c in info.columns]
        rec(f"accinfo_query {env_name} acc={mask(acc_id)}", True,
            info[cols].to_dict("records"))
    else:
        rec(f"accinfo_query {env_name} acc={mask(acc_id)}", False, info)

    ret, pos = t.position_list_query(trd_env=env, acc_id=acc_id)
    if ret == mm.RET_OK:
        cols = [c for c in ["code", "stock_name", "qty", "can_sell_qty", "cost_price",
                            "market_val", "currency", "position_side"] if c in pos.columns]
        rec(f"position_list_query {env_name}", True,
            pos[cols].to_dict("records") if len(pos) else "no open positions")
    else:
        rec(f"position_list_query {env_name}", False, pos)

    ret, od = t.order_list_query(trd_env=env, acc_id=acc_id)
    rec(f"order_list_query {env_name}", ret == mm.RET_OK,
        f"{len(od)} orders today" if ret == mm.RET_OK else str(od)[:200])
    t.close()

out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(out_dir, exist_ok=True)
stamp = OUT["utc"].replace(":", "").replace("-", "").replace(".", "")
p = os.path.join(out_dir, f"probe_quotes_{stamp}.json")
with open(p, "w", encoding="utf-8") as fh:
    json.dump(OUT, fh, indent=2, default=str)
print(f"\nJSON summary written to {p}")
