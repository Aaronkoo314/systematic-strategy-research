"""Quantify the two anomalies found by verify_adjustment.py.

A1  SPY: get_rehab returns no dividend record before 2014-06-20, yet SPY has paid
    quarterly distributions since 1993. Is the QFQ series flat (i.e. unadjusted)
    before that date? If so, a total-return series built from it understates SPY
    for 2006-2014, which would flatter any strategy measured against it.

A2  QQQ: thousands of ratio changes do not land on any published ex-date. Are they
    rounding noise, or real unexplained adjustment? Magnitude decides.

Read-only.  Usage: python tools/diagnose_qfq.py
"""

from __future__ import annotations

import os

import moomoo as mm
import numpy as np
import pandas as pd

HOST, PORT = "127.0.0.1", 11111
START, END = "2006-09-01", "2026-09-12"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fetch_all(q, code, autype):
    frames, key = [], None
    while True:
        ret, df, key = q.request_history_kline(
            code, start=START, end=END, ktype=mm.KLType.K_DAY,
            autype=autype, max_count=1000, page_req_key=key)
        if ret != mm.RET_OK:
            return None
        frames.append(df)
        if key is None:
            return pd.concat(frames, ignore_index=True)


q = mm.OpenQuoteContext(host=HOST, port=PORT)

for code in ("US.SPY", "US.QQQ"):
    print(f"\n{'=' * 72}\n{code}\n{'=' * 72}")
    raw = fetch_all(q, code, mm.AuType.NONE)
    adj = fetch_all(q, code, mm.AuType.QFQ)
    ret, rehab = q.get_rehab(code)

    m = raw[["time_key", "close"]].merge(
        adj[["time_key", "close"]], on="time_key", suffixes=("_raw", "_qfq"))
    m["date"] = m["time_key"].str[:10]
    m["ratio"] = m["close_qfq"] / m["close_raw"]
    m["dratio"] = m["ratio"].diff()

    ex = sorted(str(d)[:10] for d in rehab["ex_div_date"]) if ret == mm.RET_OK else []
    ex_set = set(ex)
    ex_in = [d for d in ex if START <= d <= END]
    print(f"  rehab ex-dates in window: {len(ex_in)}"
          f"  first={ex_in[0] if ex_in else None}  last={ex_in[-1] if ex_in else None}")

    # ---- A1: is the ratio flat before the first recorded ex-date? ----
    if ex_in:
        cut = ex_in[0]
        before = m[m["date"] < cut]
        after = m[m["date"] >= cut]
        if len(before) > 1:
            print(f"  BEFORE first ex-date ({cut}): {len(before)} bars, "
                  f"ratio min={before['ratio'].min():.8f} max={before['ratio'].max():.8f} "
                  f"unique={before['ratio'].nunique()}")
            flat = before["ratio"].nunique() <= 2
            print(f"  -> ratio is {'FLAT (NO dividend adjustment applied)' if flat else 'varying'}"
                  f" over that span")
            if flat:
                yrs = (pd.to_datetime(cut) - pd.to_datetime(before['date'].iloc[0])).days / 365.25
                print(f"  -> UNADJUSTED SPAN: {before['date'].iloc[0]} .. {cut} "
                      f"({yrs:.2f} years, {len(before)} bars)")
        print(f"  AFTER  first ex-date: {len(after)} bars, "
              f"ratio min={after['ratio'].min():.8f} max={after['ratio'].max():.8f}")

    # ---- A2: magnitude of ratio moves that are not on an ex-date ----
    off = m[(m["dratio"].abs() > 0) & (~m["date"].isin(ex_set))]
    on = m[(m["dratio"].abs() > 0) & (m["date"].isin(ex_set))]
    if len(off):
        a = off["dratio"].abs()
        print(f"\n  off-ex-date ratio moves: n={len(a)}")
        for p in (50, 90, 99, 100):
            print(f"    p{p:<3} = {np.percentile(a, p):.3e}")
        print(f"    share > 1e-4 (1bp): {(a > 1e-4).mean() * 100:.1f}%  "
              f"count={int((a > 1e-4).sum())}")
        print(f"    share > 1e-3      : {(a > 1e-3).mean() * 100:.1f}%  "
              f"count={int((a > 1e-3).sum())}")
    if len(on):
        b = on["dratio"].abs()
        print(f"  on-ex-date ratio moves : n={len(b)}  median={np.median(b):.3e}"
              f"  max={b.max():.3e}")

    # price decimals - does rounding explain the noise?
    dec_raw = m["close_raw"].astype(str).str.split(".").str[-1].str.len().max()
    dec_qfq = m["close_qfq"].astype(str).str.split(".").str[-1].str.len().max()
    px = float(m["close_raw"].median())
    print(f"  max decimals raw={dec_raw} qfq={dec_qfq}; median price={px:.2f}"
          f"  -> rounding noise floor ~{0.5 * 10.0 ** (-int(dec_qfq)) / px:.2e}")

q.close()
