"""How much 5-minute history does moomoo actually hold for QQQ?

Intraday history is usually far shorter than daily history, and the answer decides
the entire research design: the number of independent regime events available, and
whether any out-of-sample split is even possible.

Also establishes:
  - whether extended-hours bars are included (78 bars/day = regular session only)
  - session coverage against the derived trading calendar
  - the current price, so the cost arithmetic uses a real number

Read-only. Costs history-candle quota only for symbols not fetched in the last 7 days.
Usage: python tools/probe_intraday.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import moomoo as mm
import pandas as pd

HOST, PORT = "127.0.0.1", 11111
CODE = "US.QQQ"
END = "2026-09-12"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "reports", "intraday_availability.json")

REPORT = {"utc": datetime.now(timezone.utc).isoformat(), "code": CODE}


def try_window(q, ktype, start, label):
    """Ask for the first few bars from `start`; returns the earliest bar actually served."""
    ret, df, _ = q.request_history_kline(
        CODE, start=start, end=END, ktype=ktype, autype=mm.AuType.QFQ, max_count=3)
    if ret != mm.RET_OK:
        print(f"  {label:<24} ERROR: {str(df)[:70]}")
        return None
    if not len(df):
        print(f"  {label:<24} empty")
        return None
    print(f"  {label:<24} earliest served: {df['time_key'].iloc[0]}")
    return str(df["time_key"].iloc[0])


q = mm.OpenQuoteContext(host=HOST, port=PORT)
ret, quota0 = q.get_history_kl_quota(get_detail=False)
print(f"history quota before: {quota0}\n")

# --- 1. probe the intraday horizon by asking from progressively earlier dates ---
print("=== 5-minute horizon probe ===")
earliest = {}
for start in ["2006-09-01", "2015-01-01", "2020-01-01", "2023-01-01",
              "2025-01-01", "2026-01-01", "2026-06-01"]:
    earliest[start] = try_window(q, mm.KLType.K_5M, start, f"K_5M from {start}")

print("\n=== other intraday granularities (from 2006) ===")
for kt, name in ((mm.KLType.K_1M, "K_1M"), (mm.KLType.K_15M, "K_15M"),
                 (mm.KLType.K_30M, "K_30M"), (mm.KLType.K_60M, "K_60M")):
    earliest[name] = try_window(q, kt, "2006-09-01", f"{name} from 2006-09-01")

REPORT["earliest_served"] = earliest

# --- 2. pull the full 5-minute series that is actually available ---
true_start = earliest.get("2006-09-01") or earliest.get("2015-01-01") or "2024-01-01"
print(f"\n=== pulling full 5-minute series from {true_start[:10]} ===")
frames, key, pages = [], None, 0
while True:
    ret, df, key = q.request_history_kline(
        CODE, start=true_start[:10], end=END, ktype=mm.KLType.K_5M,
        autype=mm.AuType.QFQ, max_count=1000, page_req_key=key)
    if ret != mm.RET_OK:
        print(f"  page {pages}: ERROR {str(df)[:70]}")
        break
    frames.append(df)
    pages += 1
    if pages % 20 == 0:
        print(f"  ... {pages} pages, {sum(len(f) for f in frames)} bars")
    if key is None:
        break

if frames:
    bars = pd.concat(frames, ignore_index=True)
    bars["date"] = bars["time_key"].str[:10]
    bars["hm"] = bars["time_key"].str[11:16]
    per_day = bars.groupby("date").size()

    REPORT["five_min"] = {
        "total_bars": len(bars),
        "first_bar": str(bars["time_key"].iloc[0]),
        "last_bar": str(bars["time_key"].iloc[-1]),
        "sessions": int(per_day.size),
        "years": round((pd.to_datetime(bars["date"].iloc[-1])
                        - pd.to_datetime(bars["date"].iloc[0])).days / 365.25, 2),
        "bars_per_day_median": int(per_day.median()),
        "bars_per_day_min": int(per_day.min()),
        "bars_per_day_max": int(per_day.max()),
        "first_bar_time_of_day": sorted(bars["hm"].unique())[:3],
        "last_bar_time_of_day": sorted(bars["hm"].unique())[-3:],
        "extended_hours_included": bool(per_day.median() > 80),
    }
    print(f"\n  total bars      : {len(bars)}")
    print(f"  span            : {bars['time_key'].iloc[0]} .. {bars['time_key'].iloc[-1]}")
    print(f"  sessions        : {per_day.size}  ({REPORT['five_min']['years']} years)")
    print(f"  bars/day        : median {per_day.median():.0f}, "
          f"min {per_day.min()}, max {per_day.max()}")
    print(f"  session window  : {sorted(bars['hm'].unique())[0]} .. "
          f"{sorted(bars['hm'].unique())[-1]}")
    print(f"  extended hours  : "
          f"{'YES' if REPORT['five_min']['extended_hours_included'] else 'NO (regular session only)'}")

    # session coverage against the derived calendar
    cal_path = os.path.join(ROOT, "data", "us_trading_calendar.csv")
    if os.path.exists(cal_path):
        cal = set(pd.read_csv(cal_path)["date"].astype(str))
        have = set(bars["date"])
        expected = {d for d in cal if bars["date"].iloc[0] <= d <= bars["date"].iloc[-1]}
        missing = sorted(expected - have)
        REPORT["five_min"]["calendar_expected"] = len(expected)
        REPORT["five_min"]["calendar_missing"] = len(missing)
        REPORT["five_min"]["calendar_missing_examples"] = missing[:5]
        print(f"  calendar        : {len(missing)} missing of {len(expected)} expected")

    raw_dir = os.path.join(ROOT, "data", "raw")
    os.makedirs(raw_dir, exist_ok=True)
    path = os.path.join(raw_dir, "US_QQQ_5min.csv")
    bars.to_csv(path, index=False)
    print(f"  saved           : data/raw/US_QQQ_5min.csv")
    REPORT["five_min"]["file"] = "data/raw/US_QQQ_5min.csv"

# --- 3. current price, for honest cost arithmetic ---
q.subscribe([CODE], [mm.SubType.QUOTE], subscribe_push=False)
ret, snap = q.get_stock_quote([CODE])
if ret == mm.RET_OK and len(snap):
    px = float(snap["last_price"].iloc[0])
    REPORT["last_price"] = px
    shares = int(10000 // px)
    plat = 0.99 * 1.09
    notional = shares * px
    buy = plat + shares * 0.003 + shares * 0.000003
    sell = plat + shares * 0.003 + max(0.01, notional * 0.0000206) \
        + max(0.01, shares * 0.000195) + shares * 0.000003
    rt = buy + sell
    REPORT["cost_arithmetic"] = {
        "last_price": px, "whole_shares_at_TP_10000": shares,
        "notional": round(notional, 2),
        "idle_cash": round(10000 - notional, 2),
        "round_trip_usd": round(rt, 4),
        "round_trip_pct_of_TP": round(rt / 10000 * 100, 4),
        "annual_pct_at_24_rt": round(rt * 24 / 10000 * 100, 3),
        "annual_pct_at_52_rt": round(rt * 52 / 10000 * 100, 3),
        "annual_pct_at_252_rt": round(rt * 252 / 10000 * 100, 3),
    }
    print(f"\n=== cost arithmetic at the live price ===")
    print(f"  QQQ last {px}  ->  {shares} whole shares = ${notional:,.2f}"
          f"  (idle ${10000 - notional:,.2f})")
    print(f"  round trip = ${rt:.4f} = {rt / 10000 * 100:.4f}% of TP")
    for n, lbl in ((24, "24 rt/yr (2/mo)"), (52, "52 rt/yr (1/wk)"), (252, "252 rt/yr (1/day)")):
        print(f"    {lbl:<18} -> ${rt * n:7.2f}/yr = {rt * n / 10000 * 100:5.2f}% of TP")

ret, quota1 = q.get_history_kl_quota(get_detail=False)
REPORT["quota_before"], REPORT["quota_after"] = str(quota0), str(quota1)
print(f"\nhistory quota after: {quota1}")
q.close()

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(REPORT, fh, indent=2, default=str)
print("written: reports/intraday_availability.json")
