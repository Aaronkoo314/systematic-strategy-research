"""Cash distributions and splits for the V4 universe, as CASH EVENTS on ex-dates.

Why this is not optional, and why it may decide V4 outright.

The V4 rule is long/flat: it holds a full position some of the time and cash the rest.
Buy-and-hold holds the position all of the time. A holder receives every distribution;
the rule receives only those whose ex-date falls while it is IN. Measuring both on raw
prices therefore hands the rule a free advantage exactly equal to

    (distribution yield) x (fraction of time the rule is OUT)

For the equity sectors that is a few tenths of a percent a year. For HYG and LQD, whose
total return is mostly coupon, it can exceed two percent a year - comfortably larger than
any edge this test could plausibly detect. An unmodelled distribution would not bias the
answer slightly; it would manufacture the answer.

Distributions are booked as CASH on the ex-date, never by swapping in an adjusted price
series. An adjusted series encodes all FUTURE distributions into historical prices, which
is look-ahead of exactly the kind this project has already been burned by.

Withholding: 30% US withholding for a Singapore resident with no treaty relief, verified
in docs/feasibility.md section 8. The benchmark holder pays it too, so it applies to both
sides - but it must apply to both sides EXPLICITLY rather than by being left out of both.

Splits are pulled in the same call because a split inside a raw price series is a
discontinuity that would fire a percentage barrier spuriously. Any split found inside the
sample window is reported loudly; it has to be handled before any barrier is computed.

Read-only.  Usage: python tools/pull_universe_dividends.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import moomoo as mm
import pandas as pd

HOST, PORT = "127.0.0.1", 11111
WINDOW_START, WINDOW_END = "2018-01-01", "2026-09-12"
SAMPLE_START = "2018-09-10"          # first bar of the 5-minute series
WITHHOLDING = 0.30                   # Singapore resident, no US treaty

UNIVERSE = [
    "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY",
    "SPY", "IWM", "DIA", "EFA", "EEM",
    "TLT", "IEF", "LQD", "HYG", "GLD", "SLV", "USO",
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_CSV = os.path.join(ROOT, "data", "universe_dividends.csv")
OUT_JSON = os.path.join(ROOT, "data", "universe_dividends_manifest.json")


def main() -> int:
    q = mm.OpenQuoteContext(host=HOST, port=PORT)

    rows, splits, failed = [], [], []
    for sym in UNIVERSE:
        ret, rehab = q.get_rehab(f"US.{sym}")
        if ret != mm.RET_OK:
            failed.append({"symbol": sym, "error": str(rehab)[:200]})
            print(f"  {sym:<5} FAILED  {str(rehab)[:60]}")
            continue
        if rehab is None or not len(rehab):
            print(f"  {sym:<5} no distribution record")
            continue

        df = rehab.copy()
        df["ex_div_date"] = df["ex_div_date"].astype(str).str[:10]
        cash = pd.to_numeric(df.get("per_cash_div"), errors="coerce").fillna(0.0)
        special = pd.to_numeric(df.get("special_dividend"), errors="coerce").fillna(0.0)
        ratio = pd.to_numeric(df.get("split_ratio"), errors="coerce").fillna(0.0)

        gross = cash + special
        keep = (df["ex_div_date"] >= WINDOW_START) & (df["ex_div_date"] <= WINDOW_END)

        n_sym = 0
        for i in df.index[keep]:
            ex = df.at[i, "ex_div_date"]
            g = float(gross.at[i])
            if g > 0:
                rows.append({"symbol": sym, "ex_date": ex,
                             "gross_per_share": round(g, 6),
                             "net_per_share": round(g * (1 - WITHHOLDING), 6),
                             "in_sample": ex >= SAMPLE_START})
                n_sym += 1
            r = float(ratio.at[i])
            # split_ratio is 0 or 1 when there is no split; anything else is a real one
            if r not in (0.0, 1.0):
                splits.append({"symbol": sym, "ex_date": ex, "split_ratio": r,
                               "in_sample": ex >= SAMPLE_START})

        in_s = sum(1 for r in rows if r["symbol"] == sym and r["in_sample"])
        print(f"  {sym:<5} {n_sym:>3} distributions in window, {in_s:>3} inside the sample")

    q.close()

    if not rows:
        print("\nNo distributions found at all - that is itself suspicious; stop and check.")
        return 1

    d = pd.DataFrame(rows).sort_values(["symbol", "ex_date"]).reset_index(drop=True)
    d.to_csv(OUT_CSV, index=False)

    # Per-symbol annualised drag, so the size of the problem is visible before any backtest.
    ins = d[d["in_sample"]]
    years = (pd.to_datetime("2026-09-11") - pd.to_datetime(SAMPLE_START)).days / 365.25
    summary = []
    for sym, g in ins.groupby("symbol"):
        summary.append({"symbol": sym, "n_ex_dates": int(len(g)),
                        "gross_total_per_share": round(float(g["gross_per_share"].sum()), 4),
                        "net_total_per_share": round(float(g["net_per_share"].sum()), 4)})

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "withholding_rate": WITHHOLDING,
        "withholding_basis": "Singapore resident, no US treaty - docs/feasibility.md section 8",
        "window": [WINDOW_START, WINDOW_END],
        "sample_start": SAMPLE_START,
        "sample_years": round(years, 2),
        "treatment": ("CASH EVENT on the ex-date, credited only to a position actually "
                      "held on that date. Never applied by swapping in an adjusted price "
                      "series, which would be look-ahead."),
        "applies_to": ("BOTH the rule and the buy-and-hold benchmark. The benchmark "
                       "receives every distribution; the rule receives only those whose "
                       "ex-date falls while it is IN."),
        "splits_in_sample": [s for s in splits if s["in_sample"]],
        "splits_all": splits,
        "failed": failed,
        "per_symbol": summary,
        "file": "data/universe_dividends.csv",
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, default=str)

    print()
    print("=" * 84)
    print("IN-SAMPLE DISTRIBUTIONS PER SYMBOL")
    print("=" * 84)
    print(f"{'symbol':>7} {'ex-dates':>9} {'gross/share':>12} {'net/share':>11}")
    print("-" * 84)
    for s in sorted(summary, key=lambda x: -x["gross_total_per_share"]):
        print(f"{s['symbol']:>7} {s['n_ex_dates']:>9} "
              f"{s['gross_total_per_share']:>12.4f} {s['net_total_per_share']:>11.4f}")

    in_sample_splits = [s for s in splits if s["in_sample"]]
    print()
    if in_sample_splits:
        print(f"  SPLITS INSIDE THE SAMPLE - {len(in_sample_splits)}. Each is a price")
        print("  discontinuity in a RAW series and will fire a percentage barrier")
        print("  spuriously. These must be handled before any barrier is computed:")
        for s in in_sample_splits:
            print(f"    {s['symbol']:<5} {s['ex_date']}  ratio {s['split_ratio']}")
    else:
        print("  No splits inside the sample window.")

    print()
    print(f"  written: {manifest['file']} ({len(d)} rows) and the manifest")
    print("  Per-share totals above are NOT yields - they are absolute cash per share over")
    print("  the sample and must be divided by the entry price to become a rate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
