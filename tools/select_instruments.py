"""Pick instruments whose broker-side dividend record actually covers the test window.

SPY fails this test: its adjusted series reverses no dividend before 2014-06-20,
leaving 7.8 years of the window unadjusted. Using it as the equity benchmark would
understate the benchmark and flatter any strategy compared against it.

For each candidate this reports:
  - first available daily bar
  - first dividend on record, and the UNCOVERED SPAN between the two
  - whether the affine adjustment P_adj = P*A + B reproduces the API's own series
  - a usable verdict

Also derives the US trading calendar from the bar series itself, because
request_trading_days silently truncates to ten years.

Read-only.  Usage: python tools/select_instruments.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import moomoo as mm
import numpy as np
import pandas as pd

HOST, PORT = "127.0.0.1", 11111
WINDOW_START, END = "2006-09-01", "2026-09-12"

CANDIDATES = {
    "equity_sp500": ["US.IVV", "US.VOO", "US.SPLG"],       # SPY replacements
    "equity_nasdaq": ["US.QQQ", "US.QQQM"],                # operator's choice + cheaper twin
    "cash_leg": ["US.BIL", "US.SHV", "US.SGOV", "US.SHY"],
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "reports", "instrument_selection.json")
CAL = os.path.join(ROOT, "data", "us_trading_calendar.csv")

REPORT = {
    "utc": datetime.now(timezone.utc).isoformat(),
    "window_requested": [WINDOW_START, END],
    "criterion": ("dividend record must cover the test window; uncovered span means the "
                  "adjusted series silently omits distributions"),
    "candidates": {},
}


def fetch_all(q, code, autype):
    frames, key = [], None
    while True:
        ret, df, key = q.request_history_kline(
            code, start=WINDOW_START, end=END, ktype=mm.KLType.K_DAY,
            autype=autype, max_count=1000, page_req_key=key)
        if ret != mm.RET_OK:
            return None, str(df)
        frames.append(df)
        if key is None:
            return pd.concat(frames, ignore_index=True), None


def affine_residual(m, ex_dates) -> float:
    """Worst relative residual of qfq = A*raw + B, fitted per inter-ex-date segment."""
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
ret, quota0 = q.get_history_kl_quota(get_detail=False)
print(f"history quota before: {quota0}\n")

calendar_source = None

for group, codes in CANDIDATES.items():
    print(f"\n########## {group} ##########")
    for code in codes:
        raw, err = fetch_all(q, code, mm.AuType.NONE)
        if raw is None:
            print(f"  {code:<10} UNAVAILABLE  ({err[:60]})")
            REPORT["candidates"][code] = {"group": group, "available": False, "error": err[:200]}
            continue
        adj, _ = fetch_all(q, code, mm.AuType.QFQ)
        ret_r, rehab = q.get_rehab(code)

        m = raw[["time_key", "close"]].merge(
            adj[["time_key", "close"]], on="time_key", suffixes=("_raw", "_qfq"))
        m["date"] = pd.to_datetime(m["time_key"].str[:10])

        ex = sorted(pd.to_datetime(str(d)[:10]) for d in rehab["ex_div_date"]) if ret_r == mm.RET_OK else []
        ex_in = [d for d in ex if m["date"].iloc[0] <= d <= m["date"].iloc[-1]]

        first_bar = m["date"].iloc[0]
        uncovered = ((ex_in[0] - first_bar).days / 365.25) if ex_in else None
        resid = affine_residual(m, ex_in)

        # Verdict: the dividend record must start within ~4 months of the first bar.
        if not ex_in:
            verdict = "NO_DIVIDEND_RECORD"
        elif uncovered > 0.34:
            verdict = f"UNUSABLE_FOR_TOTAL_RETURN ({uncovered:.2f}y unadjusted)"
        elif resid > 1e-5:
            verdict = "ADJUSTMENT_NOT_REPRODUCIBLE"
        else:
            verdict = "USABLE"

        info = {
            "group": group, "available": True, "bars": len(m),
            "first_bar": str(first_bar.date()), "last_bar": str(m["date"].iloc[-1].date()),
            "years": round((m["date"].iloc[-1] - first_bar).days / 365.25, 2),
            "first_dividend_on_record": str(ex_in[0].date()) if ex_in else None,
            "n_dividends_in_window": len(ex_in),
            "uncovered_span_years": round(uncovered, 3) if uncovered is not None else None,
            "affine_worst_rel_residual": resid,
            "verdict": verdict,
        }
        REPORT["candidates"][code] = info
        print(f"  {code:<10} bars={len(m):<5} {info['first_bar']} .. {info['last_bar']}"
              f"  div_from={info['first_dividend_on_record']}"
              f"  uncovered={info['uncovered_span_years']}y  -> {verdict}")

        if code == "US.QQQ":
            calendar_source = m[["date"]].copy()

ret, quota1 = q.get_history_kl_quota(get_detail=False)
print(f"\nhistory quota after: {quota1}")
REPORT["quota_before"], REPORT["quota_after"] = str(quota0), str(quota1)
q.close()

# ---- trading calendar derived from bars, not from the truncating API ----
if calendar_source is not None:
    cal = calendar_source.drop_duplicates().sort_values("date")
    cal["date"] = cal["date"].dt.strftime("%Y-%m-%d")
    os.makedirs(os.path.dirname(CAL), exist_ok=True)
    cal.to_csv(CAL, index=False)
    REPORT["calendar"] = {
        "file": "data/us_trading_calendar.csv",
        "sessions": len(cal),
        "first": cal["date"].iloc[0], "last": cal["date"].iloc[-1],
        "derived_from": "US.QQQ daily bars",
        "why": "request_trading_days silently truncates to ~10 years",
    }
    print(f"\ncalendar: {len(cal)} sessions {cal['date'].iloc[0]} .. {cal['date'].iloc[-1]}"
          f"  -> data/us_trading_calendar.csv")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(REPORT, fh, indent=2, default=str)
print(f"written: reports/instrument_selection.json")
