"""Run the ex-ante power gate on the real QQQ sample. No strategy required.

selection_criteria.md appendix A.5(a). This runs BEFORE any candidate is proposed, so
its answer cannot be adjusted to suit a result.

Usage: python tools/run_power_gate.py
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

d = pd.read_csv(os.path.join(ROOT, "data", "raw", "US_QQQ_5min_raw.csv"))
d["date"] = d["time_key"].str[:10]
daily_close = d.groupby("date")["close"].last()
ret = daily_close.pct_change().dropna().to_numpy()

sessions = len(daily_close)
years = sessions / 252.0
ann_vol = float(np.std(ret, ddof=1) * np.sqrt(252))

print("=" * 80)
print("EX-ANTE POWER GATE - QQQ 5-minute sample")
print("=" * 80)
print(f"  sessions available        {sessions}")
print(f"  years available           {years:.2f}")
print(f"  annualised volatility     {ann_vol:.2%}")
ess = effective_sample_size(ret)
print(f"  effective sample size     {ess:,.0f} independent-equivalent daily observations")
print(f"                            (against {len(ret):,} raw daily observations)")

print()
print("=" * 80)
print("Minimum detectable annualised excess return vs buy-and-hold")
print("=" * 80)
print(f"{'exposure':>10} {'tracking err':>14} {'MDA 80% power':>16} {'vs fee ceiling':>16}")
print("-" * 80)

rows = []
for p in (0.25, 0.50, 0.75, 0.90):
    te = tracking_error_of_overlay(ret, p)
    res = power_gate(te, years, n_configs=1)
    mda = res.min_detectable_alpha_80pct_power
    flag = "below 10%" if mda < 0.10 else "ABOVE the 10%/yr fee ceiling"
    print(f"{p:>10.0%} {te:>14.2%} {mda:>16.2%} {flag:>30}")
    rows.append({"exposure": p, "tracking_error": te,
                 "mda_80pct": mda, "n_configs": 1})

print()
print("  Read that carefully: at 50 % exposure the sample can only distinguish an")
print("  excess return above roughly that figure from luck. The operator's fee")
print("  ceiling is 10 %/yr, so anything the sample can prove is already being")
print("  spent on fees.")

print()
print("=" * 80)
print("With the search budget applied (Bonferroni over configurations tried)")
print("=" * 80)
print(f"{'configs':>10} {'z critical':>12} {'MDA 80% @ 50% exposure':>26}")
print("-" * 80)
te50 = tracking_error_of_overlay(ret, 0.50)
for n in (1, 6, 24):
    r = power_gate(te50, years, n_configs=n)
    print(f"{n:>10} {r.z_critical:>12.3f} {r.min_detectable_alpha_80pct_power:>26.2%}")
print()
print("  24 is the training-set budget frozen in selection_criteria.md section 6.")

print()
print("=" * 80)
print("Years required to detect a given alpha, 50 % exposure, 24 configs")
print("=" * 80)
for target in (0.02, 0.05, 0.10, 0.15, 0.20):
    r = power_gate(te50, years, n_configs=24, target_alpha=target)
    mark = "PASS" if r.passes else "FAIL"
    print(f"  alpha {target:>5.0%}  ->  {r.years_needed_for_target:>8.1f} years needed   "
          f"[{mark}]  ({years:.1f} available)")

out = {
    "generated_for": "selection_criteria.md appendix A.5(a) ex-ante power gate",
    "sessions": int(sessions), "years": round(years, 3),
    "annualised_volatility": round(ann_vol, 6),
    "effective_sample_size_daily": round(float(ess), 1),
    "raw_daily_observations": int(len(ret)),
    "by_exposure": rows,
    "tracking_error_at_50pct": round(float(te50), 6),
    "mda_80pct_1_config": round(power_gate(te50, years, n_configs=1).min_detectable_alpha_80pct_power, 6),
    "mda_80pct_24_configs": round(power_gate(te50, years, n_configs=24).min_detectable_alpha_80pct_power, 6),
    "fee_ceiling": 0.10,
    "note": ("tracking error is the denominator a timing overlay carries regardless of "
             "skill; a skilful rule and a worthless one share it"),
}
os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
with open(os.path.join(ROOT, "reports", "power_gate.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2)
print("\nwritten: reports/power_gate.json")
