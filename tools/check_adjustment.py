"""Stage C data-integrity check: does moomoo's QFQ adjustment include dividends?

This matters more than it sounds. SPY distributes roughly 1.1-1.2 % a year. If the
'adjusted' series only reverses splits, a price-only backtest silently discards the
dividend for every day a position is held -- and it discards it ASYMMETRICALLY when a
strategy is out of the market part of the time, which biases the comparison against
buy-and-hold in an uncontrolled direction.

Method (no assumption about SPY's corporate-action history):
  fetch the same window twice, AuType.NONE and AuType.QFQ, and look at the ratio
  adjusted/raw over time.
    - ratio constant at 1.0            -> no adjustment at all in this window
    - ratio with a few large steps     -> splits only
    - ratio stepping ~4x per year by ~0.3 % -> dividends are included

Strictly read-only. Costs 1 historical-candle quota per NEW symbol (repeats within
7 days are free).

Usage: python tools/check_adjustment.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import moomoo as mm
import pandas as pd

HOST, PORT = "127.0.0.1", 11111
START, END = "2015-01-01", "2026-09-12"
SYMBOLS = ["US.SPY", "US.IEF", "US.BIL"]

OUT: dict = {"utc": datetime.now(timezone.utc).isoformat(), "window": [START, END], "symbols": {}}


def fetch(q, code: str, autype) -> pd.DataFrame | None:
    ret, df, page = q.request_history_kline(
        code, start=START, end=END, ktype=mm.KLType.K_DAY, autype=autype, max_count=None
    )
    if ret != mm.RET_OK:
        print(f"  [ERR] {code} {autype}: {df}")
        return None
    return df[["time_key", "close", "volume"]].copy()


def main() -> int:
    q = mm.OpenQuoteContext(host=HOST, port=PORT)
    ret, quota = q.get_history_kl_quota(get_detail=False)
    print(f"historical-candle quota before: {quota}")

    for code in SYMBOLS:
        print(f"\n=== {code} ===")
        raw = fetch(q, code, mm.AuType.NONE)
        adj = fetch(q, code, mm.AuType.QFQ)
        if raw is None or adj is None:
            OUT["symbols"][code] = {"error": "fetch failed"}
            continue

        m = raw.merge(adj, on="time_key", suffixes=("_raw", "_adj"))
        m["ratio"] = m["close_adj"] / m["close_raw"]

        # A "step" is a day where the ratio changes by more than 1 bp.
        m["dratio"] = m["ratio"].diff().abs()
        steps = m[m["dratio"] > 1e-4]

        first, last = m.iloc[0], m.iloc[-1]
        years = (pd.to_datetime(last["time_key"]) - pd.to_datetime(first["time_key"])).days / 365.25

        info = {
            "rows": len(m),
            "first_bar": str(first["time_key"]),
            "last_bar": str(last["time_key"]),
            "years_covered": round(years, 2),
            "ratio_first": round(float(first["ratio"]), 6),
            "ratio_last": round(float(last["ratio"]), 6),
            "ratio_constant": bool(m["ratio"].nunique() == 1),
            "n_steps_gt_1bp": int(len(steps)),
            "steps_per_year": round(len(steps) / years, 2) if years > 0 else None,
            "example_steps": [
                {"date": str(r["time_key"]),
                 "raw": round(float(r["close_raw"]), 4),
                 "adj": round(float(r["close_adj"]), 4),
                 "ratio": round(float(r["ratio"]), 6)}
                for _, r in steps.head(6).iterrows()
            ],
        }

        # Interpretation, stated conservatively.
        if info["ratio_constant"] and abs(info["ratio_first"] - 1.0) < 1e-9:
            info["verdict"] = "NO_ADJUSTMENT_IN_WINDOW"
        elif info["steps_per_year"] and info["steps_per_year"] >= 3:
            info["verdict"] = "LIKELY_INCLUDES_DIVIDENDS"
        else:
            info["verdict"] = "SPLITS_ONLY_OR_UNCLEAR"

        OUT["symbols"][code] = info
        for k in ("rows", "first_bar", "last_bar", "ratio_first", "ratio_last",
                  "ratio_constant", "n_steps_gt_1bp", "steps_per_year", "verdict"):
            print(f"  {k}: {info[k]}")

    ret, quota_after = q.get_history_kl_quota(get_detail=False)
    print(f"\nhistorical-candle quota after: {quota_after}")
    OUT["quota_before"], OUT["quota_after"] = str(quota), str(quota_after)

    q.close()

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "adjustment_check.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(OUT, fh, indent=2, default=str)
    print(f"\nwritten: logs/adjustment_check.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
