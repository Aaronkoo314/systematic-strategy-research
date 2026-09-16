"""Ex-ante power gate on the 20-year DAILY sample, beside the 8-year intraday one.

selection_criteria.md appendix A.5(a). Runs before any daily candidate is proposed, so
its answer cannot be adjusted to suit a result.

The question this answers is narrow and checkable: how much lower is the wall on 20 years
than on 8? Tracking error is a property of the asset and the overlay, not of the sample
length, so only the sqrt(T) term moves.

Usage: python tools/run_power_gate_daily.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.validation.power import (  # noqa: E402
    effective_sample_size, power_gate, tracking_error_of_overlay,
)


def daily_returns_from_daily_file():
    d = pd.read_csv(os.path.join(ROOT, "data", "raw", "US_QQQ_daily.csv"))
    # raw prices: the same basis the engine trades on
    c = d["close_raw"].to_numpy(float)
    dates = d["time_key"].str[:10].to_numpy()
    return np.diff(c) / c[:-1], dates


def daily_returns_from_intraday_file():
    d = pd.read_csv(os.path.join(ROOT, "data", "raw", "US_QQQ_5min_raw.csv"))
    d["date"] = d["time_key"].str[:10]
    c = d.groupby("date")["close"].last()
    return c.pct_change().dropna().to_numpy(), c.index.to_numpy()


SAMPLES = {}
r, dts = daily_returns_from_daily_file()
SAMPLES["daily 2006-09 (20y)"] = (r, len(r) + 1, str(dts[0]), str(dts[-1]))
r, dts = daily_returns_from_intraday_file()
SAMPLES["intraday-derived 2018-09 (8y)"] = (r, len(r) + 1, str(dts[0]), str(dts[-1]))

print("=" * 96)
print("EX-ANTE POWER GATE - 20-year daily sample against the 8-year one")
print("=" * 96)

meta = {}
for name, (ret, sessions, lo, hi) in SAMPLES.items():
    years = sessions / 252.0
    vol = float(np.std(ret, ddof=1) * np.sqrt(252))
    ess = effective_sample_size(ret)
    meta[name] = dict(ret=ret, years=years, vol=vol, ess=ess, sessions=sessions)
    print(f"\n  {name}")
    print(f"    {lo} .. {hi}   {sessions} sessions   {years:.2f} years")
    print(f"    annualised volatility {vol:.2%}   effective sample {ess:,.0f}")

print("\n" + "=" * 96)
print("Minimum detectable annualised excess return, 80 % power")
print("=" * 96)
print(f"{'exposure':>9} {'track err':>11} | {'8y MDA':>9} {'8y n=24':>9} | "
      f"{'20y MDA':>9} {'20y n=24':>10} | {'wall drops by':>14}")
print("-" * 96)

rows = []
d8 = meta["intraday-derived 2018-09 (8y)"]
d20 = meta["daily 2006-09 (20y)"]
for p in (0.25, 0.50, 0.75, 0.90, 0.95):
    te8 = tracking_error_of_overlay(d8["ret"], p)
    te20 = tracking_error_of_overlay(d20["ret"], p)
    m8 = power_gate(te8, d8["years"], n_configs=1).min_detectable_alpha_80pct_power
    m8c = power_gate(te8, d8["years"], n_configs=24).min_detectable_alpha_80pct_power
    m20 = power_gate(te20, d20["years"], n_configs=1).min_detectable_alpha_80pct_power
    m20c = power_gate(te20, d20["years"], n_configs=24).min_detectable_alpha_80pct_power
    print(f"{p:>9.0%} {te20:>11.2%} | {m8:>9.2%} {m8c:>9.2%} | "
          f"{m20:>9.2%} {m20c:>10.2%} | {1 - m20c / m8c:>13.0%}")
    rows.append({"exposure": p, "te_20y": te20, "te_8y": te8,
                 "mda_8y_n1": m8, "mda_8y_n24": m8c,
                 "mda_20y_n1": m20, "mda_20y_n24": m20c})

print("\n" + "=" * 96)
print("Years required to detect a given alpha - 20-year daily sample")
print("=" * 96)
print(f"{'alpha':>7} | {'@50% exp, n=24':>16} {'@90% exp, n=24':>16} "
      f"{'@90% exp, n=6':>15} {'@90% exp, n=1':>15}")
print("-" * 96)
te50 = tracking_error_of_overlay(d20["ret"], 0.50)
te90 = tracking_error_of_overlay(d20["ret"], 0.90)
need = []
for a in (0.02, 0.03, 0.05, 0.08, 0.10):
    y1 = power_gate(te50, d20["years"], n_configs=24, target_alpha=a).years_needed_for_target
    y2 = power_gate(te90, d20["years"], n_configs=24, target_alpha=a).years_needed_for_target
    y3 = power_gate(te90, d20["years"], n_configs=6, target_alpha=a).years_needed_for_target
    y4 = power_gate(te90, d20["years"], n_configs=1, target_alpha=a).years_needed_for_target
    def mk(y):
        return f"{y:>8.1f} {'PASS' if y <= d20['years'] else 'FAIL'}"
    print(f"{a:>7.0%} | {mk(y1):>16} {mk(y2):>16} {mk(y3):>15} {mk(y4):>15}")
    need.append({"alpha": a, "y_50_24": y1, "y_90_24": y2, "y_90_6": y3, "y_90_1": y4})

print(f"\n  available: {d20['years']:.2f} years")
print("\n  The lever is not sample length alone - it is tracking error. A rule that stays")
print("  mostly invested deviates less from the benchmark, so a smaller edge becomes")
print("  measurable. Keeping the search budget small does the same thing, for free.")

out = {"generated_for": "selection_criteria.md appendix A.5(a), daily sample",
       "samples": {k: {"years": round(v["years"], 3), "sessions": v["sessions"],
                       "ann_vol": round(v["vol"], 6),
                       "effective_sample": round(float(v["ess"]), 1)}
                   for k, v in meta.items()},
       "by_exposure": rows, "years_needed": need,
       "te_20y_at_50pct": round(float(te50), 6),
       "te_20y_at_90pct": round(float(te90), 6)}
with open(os.path.join(ROOT, "reports", "power_gate_daily.json"), "w",
          encoding="utf-8") as fh:
    json.dump(out, fh, indent=2)
print("\nwritten: reports/power_gate_daily.json")
