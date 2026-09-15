"""Dividend-coverage check for the remaining instruments, plus the trading calendar.

Follow-up to select_instruments.py: QQQ timed out there and the bond leg was not
covered. Same criterion - the broker's dividend record must start within about
four months of the first available bar, otherwise the adjusted series silently
omits distributions and any total-return figure built on it is wrong.

Read-only. Retries on timeout.  Usage: python tools/check_coverage.py
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

import moomoo as mm
import numpy as np
import pandas as pd

HOST, PORT = "127.0.0.1", 11111
WINDOW_START, END = "2006-09-01", "2026-09-12"
CODES = ["US.QQQ", "US.IEF", "US.TLT", "US.AGG", "US.SPY"]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "reports", "coverage_check.json")
CAL = os.path.join(ROOT, "data", "us_trading_calendar.csv")

REPORT = {"utc": datetime.now(timezone.utc).isoformat(), "instruments": {}}


def fetch_all(q, code, autype, retries=3):
    for attempt in range(retries):
        frames, key, failed = [], None, False
        while True:
            ret, df, key = q.request_history_kline(
                code, start=WINDOW_START, end=END, ktype=mm.KLType.K_DAY,
                autype=autype, max_count=1000, page_req_key=key)
            if ret != mm.RET_OK:
                print(f"    retry {attempt + 1}/{retries} for {code}: {str(df)[:60]}")
                failed = True
                time.sleep(3)
                break
            frames.append(df)
            if key is None:
                return pd.concat(frames, ignore_index=True)
        if not failed:
            break
    return None


def affine_residual(m, ex_dates) -> float:
    bounds = [m["date"].iloc[0]] + ex_dates + [m["date"].iloc[-1] + pd.Timedelta(days=1)]
    worst = 0.0
    for i in range(len(bounds) - 1):
        s = m[(m["date"] >= bounds[i]) & (m["date"] < bounds[i + 1])]
        if len(s) < 3:
            continue
        A, B = np.polyfit(s["close_raw"].to_numpy(float), s["close_qfq"].to_numpy(float), 1)
        pred = s["close_raw"].to_numpy(float) * A + B
        worst = max(worst, float(np.max(np.abs(pred - s["close_qfq"].to_numpy(float))
                                        / s["close_qfq"].to_numpy(float))))
    return worst


q = mm.OpenQuoteContext(host=HOST, port=PORT)
calendar_src = None

for code in CODES:
    raw = fetch_all(q, code, mm.AuType.NONE)
    adj = fetch_all(q, code, mm.AuType.QFQ)
    ret_r, rehab = q.get_rehab(code)
    if raw is None or adj is None:
        print(f"  {code:<8} FETCH FAILED after retries")
        REPORT["instruments"][code] = {"error": "fetch failed after retries"}
        continue

    m = raw[["time_key", "close"]].merge(
        adj[["time_key", "close"]], on="time_key", suffixes=("_raw", "_qfq"))
    m["date"] = pd.to_datetime(m["time_key"].str[:10])

    ex = sorted(pd.to_datetime(str(d)[:10]) for d in rehab["ex_div_date"]) if ret_r == mm.RET_OK else []
    ex_in = [d for d in ex if m["date"].iloc[0] <= d <= m["date"].iloc[-1]]
    first_bar = m["date"].iloc[0]
    unc = ((ex_in[0] - first_bar).days / 365.25) if ex_in else None
    resid = affine_residual(m, ex_in)

    verdict = ("NO_DIVIDEND_RECORD" if not ex_in
               else f"UNUSABLE ({unc:.2f}y unadjusted)" if unc > 0.34
               else "ADJUSTMENT_NOT_REPRODUCIBLE" if resid > 1e-5
               else "USABLE")

    REPORT["instruments"][code] = {
        "bars": len(m), "first_bar": str(first_bar.date()),
        "last_bar": str(m["date"].iloc[-1].date()),
        "first_dividend_on_record": str(ex_in[0].date()) if ex_in else None,
        "n_dividends_in_window": len(ex_in),
        "uncovered_span_years": round(unc, 3) if unc is not None else None,
        "affine_worst_rel_residual": resid,
        "verdict": verdict,
    }
    print(f"  {code:<8} bars={len(m):<5} {first_bar.date()} .. {m['date'].iloc[-1].date()}"
          f"  div_from={REPORT['instruments'][code]['first_dividend_on_record']}"
          f"  n_div={len(ex_in):<3} uncovered={REPORT['instruments'][code]['uncovered_span_years']}y"
          f"  -> {verdict}")

    if code == "US.QQQ":
        calendar_src = m[["date"]].copy()

q.close()

if calendar_src is not None:
    cal = calendar_src.drop_duplicates().sort_values("date")
    cal["date"] = cal["date"].dt.strftime("%Y-%m-%d")
    os.makedirs(os.path.dirname(CAL), exist_ok=True)
    cal.to_csv(CAL, index=False)
    REPORT["calendar"] = {
        "file": "data/us_trading_calendar.csv", "sessions": len(cal),
        "first": cal["date"].iloc[0], "last": cal["date"].iloc[-1],
        "derived_from": "US.QQQ daily bars",
        "why": "request_trading_days silently truncates to ~10 years",
    }
    print(f"\ncalendar: {len(cal)} sessions {cal['date'].iloc[0]} .. {cal['date'].iloc[-1]}"
          f" -> data/us_trading_calendar.csv")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(REPORT, fh, indent=2, default=str)
print("written: reports/coverage_check.json")
