"""Decisive check: does P_adj = P * A + B reproduce the API's QFQ series exactly?

Background. My earlier ratio-based test flagged QQQ as anomalous - 21 % of bars
showed off-ex-date moves in close_qfq/close_raw. That test was wrong. moomoo's
adjustment is affine, P_adj = P * A + B, so whenever B != 0 the RATIO varies with
price by construction. SPY's forward_adj_factorB is empty, which is why its ratio
looked like a clean step function; QQQ's is not.

The correct test fits the affine relation inside each inter-ex-date segment and
checks the residual. If P_adj is reproducible from P to within price rounding,
the series is internally consistent and usable. It also isolates the genuine
defect found separately: SPY has no dividend record before 2014-06-20.

Read-only.  Usage: python tools/reconcile_qfq.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import moomoo as mm
import numpy as np
import pandas as pd

HOST, PORT = "127.0.0.1", 11111
START, END = "2006-09-01", "2026-09-12"
SYMBOLS = ["US.QQQ", "US.SPY"]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "logs", "qfq_reconciliation.json")
REPORT = {"utc": datetime.now(timezone.utc).isoformat(), "instruments": {}}


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

for code in SYMBOLS:
    print(f"\n{'=' * 72}\n{code}\n{'=' * 72}")
    raw = fetch_all(q, code, mm.AuType.NONE)
    adj = fetch_all(q, code, mm.AuType.QFQ)
    ret, rehab = q.get_rehab(code)

    m = raw[["time_key", "close"]].merge(
        adj[["time_key", "close"]], on="time_key", suffixes=("_raw", "_qfq"))
    m["date"] = pd.to_datetime(m["time_key"].str[:10])

    ex = sorted(pd.to_datetime(str(d)[:10]) for d in rehab["ex_div_date"]) if ret == mm.RET_OK else []
    ex_in = [d for d in ex if m["date"].iloc[0] <= d <= m["date"].iloc[-1]]

    # Segment the series at ex-dates; within a segment the affine factors are constant.
    bounds = [m["date"].iloc[0]] + ex_in + [m["date"].iloc[-1] + pd.Timedelta(days=1)]
    segs, worst = [], 0.0
    for i in range(len(bounds) - 1):
        s = m[(m["date"] >= bounds[i]) & (m["date"] < bounds[i + 1])]
        if len(s) < 3:
            continue
        # Least-squares fit of qfq = A*raw + B
        A, B = np.polyfit(s["close_raw"].to_numpy(float), s["close_qfq"].to_numpy(float), 1)
        pred = s["close_raw"].to_numpy(float) * A + B
        resid = np.abs(pred - s["close_qfq"].to_numpy(float))
        rel = float(np.max(resid / s["close_qfq"].to_numpy(float)))
        worst = max(worst, rel)
        segs.append({"start": str(s["date"].iloc[0].date()), "n": len(s),
                     "A": round(float(A), 10), "B": round(float(B), 10),
                     "max_rel_resid": rel})

    n_bad = sum(1 for s in segs if s["max_rel_resid"] > 1e-6)
    print(f"  segments fitted: {len(segs)}")
    print(f"  worst relative residual of P_adj = P*A + B : {worst:.3e}")
    print(f"  segments with residual > 1e-6 : {n_bad}")
    print(f"  -> affine relation {'HOLDS' if worst < 1e-5 else 'DOES NOT HOLD'}")

    # Is forward_adj_factorB actually non-zero for this instrument?
    if ret == mm.RET_OK and "forward_adj_factorB" in rehab.columns:
        fb = pd.to_numeric(rehab["forward_adj_factorB"], errors="coerce").fillna(0)
        fa = pd.to_numeric(rehab["forward_adj_factorA"], errors="coerce").fillna(0)
        print(f"  rehab forward_adj_factorA non-zero rows: {int((fa != 0).sum())}/{len(rehab)}")
        print(f"  rehab forward_adj_factorB non-zero rows: {int((fb != 0).sum())}/{len(rehab)}"
              f"   (B != 0 is why the qfq/raw RATIO wobbles)")

    # The genuine defect: dividend coverage versus the data window.
    first_ex = str(ex_in[0].date()) if ex_in else None
    win_start = str(m["date"].iloc[0].date())
    gap_years = ((ex_in[0] - m["date"].iloc[0]).days / 365.25) if ex_in else None
    print(f"  data window starts {win_start}; first dividend on record {first_ex}"
          f"  -> UNCOVERED SPAN {gap_years:.2f} years" if ex_in else "")

    REPORT["instruments"][code] = {
        "bars": len(m),
        "segments": len(segs),
        "worst_rel_residual": worst,
        "segments_resid_gt_1e6": n_bad,
        "affine_holds": bool(worst < 1e-5),
        "data_window_start": win_start,
        "first_dividend_on_record": first_ex,
        "uncovered_span_years": round(gap_years, 2) if ex_in else None,
        "n_ex_dates_in_window": len(ex_in),
        "segment_sample": segs[:3],
    }

q.close()
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(REPORT, fh, indent=2, default=str)
print(f"\nwritten: logs/qfq_reconciliation.json")
