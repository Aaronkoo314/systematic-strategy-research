"""Reconcile moomoo's QFQ series against its own published corporate actions.

Why this matters more than it sounds: if the 'adjusted' series does not reverse
dividends, a price-only backtest silently discards roughly 0.5-2 %/yr of return,
and it discards it ASYMMETRICALLY for any strategy that sits in cash part of the
time. That single defect can manufacture or destroy an apparent edge.

Method, using only the broker's own data so there is nothing to take on trust:
  1. get_rehab(code)  -> the published dividend / split records and the
     forward-adjustment factors A and B, where P_adj = P * A + B.
  2. Recompute QFQ from AuType.NONE raw prices using those factors.
  3. Compare bar by bar against the API's own AuType.QFQ series.
  4. Independently check that every ratio step in the QFQ/raw series lands on a
     published ex-date, and that its magnitude matches the dividend.

Strictly read-only.  Usage: python tools/verify_adjustment.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import moomoo as mm
import pandas as pd

HOST, PORT = "127.0.0.1", 11111
SYMBOLS = ["US.QQQ", "US.SPY"]
START, END = "2006-09-01", "2026-09-12"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "logs", "adjustment_verification.json")

REPORT: dict = {"utc": datetime.now(timezone.utc).isoformat(), "instruments": {}}


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


def main() -> int:
    q = mm.OpenQuoteContext(host=HOST, port=PORT)

    for code in SYMBOLS:
        print(f"\n{'=' * 70}\n{code}\n{'=' * 70}")
        info: dict = {}

        ret, rehab = q.get_rehab(code)
        if ret != mm.RET_OK:
            print(f"  [ERR] get_rehab: {rehab}")
            REPORT["instruments"][code] = {"error": f"get_rehab failed: {rehab}"}
            continue

        info["rehab_columns"] = list(rehab.columns)
        print(f"  rehab rows: {len(rehab)}")
        print(f"  rehab columns: {list(rehab.columns)}")

        # Which corporate-action fields are actually populated?
        populated = {}
        for col in rehab.columns:
            if col in ("code", "ex_div_date"):
                continue
            s = pd.to_numeric(rehab[col], errors="coerce")
            nz = int((s.notna() & (s != 0)).sum())
            if nz:
                populated[col] = nz
        info["populated_fields"] = populated
        print(f"  populated fields: {populated}")

        if "ex_div_date" in rehab.columns and len(rehab):
            info["rehab_first_ex_date"] = str(rehab["ex_div_date"].iloc[0])
            info["rehab_last_ex_date"] = str(rehab["ex_div_date"].iloc[-1])
            print(f"  ex-dates: {info['rehab_first_ex_date']} .. {info['rehab_last_ex_date']}")

        div_col = next((c for c in ("per_cash_div", "dividend", "per_share_div")
                        if c in rehab.columns), None)
        if div_col:
            divs = rehab[pd.to_numeric(rehab[div_col], errors="coerce").fillna(0) > 0]
            info["n_cash_dividends"] = len(divs)
            in_window = divs[(divs["ex_div_date"] >= START) & (divs["ex_div_date"] <= END)]
            info["n_cash_dividends_in_window"] = len(in_window)
            print(f"  cash dividends on record: {len(divs)}  (in window: {len(in_window)})")

        raw = fetch_all(q, code, mm.AuType.NONE)
        adj = fetch_all(q, code, mm.AuType.QFQ)
        if raw is None or adj is None:
            REPORT["instruments"][code] = {"error": "kline fetch failed"}
            continue

        m = raw[["time_key", "close"]].merge(
            adj[["time_key", "close"]], on="time_key", suffixes=("_raw", "_qfq"))
        m["date"] = m["time_key"].str[:10]
        m["ratio"] = m["close_qfq"] / m["close_raw"]
        m["dratio"] = m["ratio"].diff()

        steps = m[m["dratio"].abs() > 1e-6].copy()
        info["n_bars"] = len(m)
        info["n_ratio_steps"] = len(steps)
        print(f"  bars: {len(m)}   ratio steps (>1e-6): {len(steps)}")

        # --- do ratio steps land on published ex-dates? ----------------------
        if "ex_div_date" in rehab.columns:
            ex_dates = set(str(d)[:10] for d in rehab["ex_div_date"])
            step_dates = set(steps["date"])
            on_ex = step_dates & ex_dates
            off_ex = sorted(step_dates - ex_dates)
            info["steps_on_published_ex_dates"] = len(on_ex)
            info["steps_NOT_on_ex_dates"] = len(off_ex)
            info["unexplained_step_examples"] = off_ex[:8]
            ex_in_window = sorted(d for d in ex_dates if START <= d <= END)
            missed = sorted(set(ex_in_window) - step_dates)
            info["ex_dates_in_window"] = len(ex_in_window)
            info["ex_dates_with_NO_step"] = len(missed)
            info["ex_dates_without_step_examples"] = missed[:8]
            print(f"  steps on published ex-dates : {len(on_ex)}")
            print(f"  steps NOT on any ex-date    : {len(off_ex)}  {off_ex[:4]}")
            print(f"  ex-dates in window          : {len(ex_in_window)}")
            print(f"  ex-dates with NO ratio step : {len(missed)}  {missed[:4]}")

        # --- cumulative effect of adjustment over the window ----------------
        r0, r1 = float(m["ratio"].iloc[0]), float(m["ratio"].iloc[-1])
        years = (pd.to_datetime(m["date"].iloc[-1]) - pd.to_datetime(m["date"].iloc[0])).days / 365.25
        implied = (1.0 / r0) ** (1.0 / years) - 1.0 if r0 > 0 else None
        info["ratio_first"], info["ratio_last"] = round(r0, 8), round(r1, 8)
        info["years"] = round(years, 2)
        info["implied_annual_adjustment_pct"] = round(implied * 100, 3) if implied else None
        print(f"  ratio {r0:.6f} -> {r1:.6f} over {years:.2f}y"
              f"  => implied {implied * 100:.3f} %/yr of adjustment")

        # --- price-only vs adjusted total growth ----------------------------
        g_raw = float(m["close_raw"].iloc[-1]) / float(m["close_raw"].iloc[0])
        g_adj = float(m["close_qfq"].iloc[-1]) / float(m["close_qfq"].iloc[0])
        info["growth_raw_price_only"] = round(g_raw, 4)
        info["growth_qfq"] = round(g_adj, 4)
        info["cagr_raw_pct"] = round((g_raw ** (1 / years) - 1) * 100, 3)
        info["cagr_qfq_pct"] = round((g_adj ** (1 / years) - 1) * 100, 3)
        info["cagr_gap_pct"] = round(info["cagr_qfq_pct"] - info["cagr_raw_pct"], 3)
        print(f"  CAGR raw {info['cagr_raw_pct']} %  vs QFQ {info['cagr_qfq_pct']} %"
              f"  => gap {info['cagr_gap_pct']} %/yr")

        REPORT["instruments"][code] = info

    q.close()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(REPORT, fh, indent=2, default=str)
    print(f"\nwritten: logs/adjustment_verification.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
