"""Run preregistered candidate V3: QQQ plus Treasuries. Spec: docs/preregistration_v3.md.

Order enforced by the script: grid on training, select by the frozen rule (highest CAGR
among configurations whose drawdown stays inside 20%), validate, check A1-A6, run the
final test once only if validation cleared, then stress. Every run goes to the log.

Usage: python tools/run_experiment_v3.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.backtest.engine import ExecutionModel  # noqa: E402
from src.backtest.portfolio import PortfolioBacktester  # noqa: E402
from src.costs.fees import FeeSchedule  # noqa: E402
from src.data.bars import load_daily  # noqa: E402
from src.risk.controls import RiskLimits, RiskManager  # noqa: E402

SPLITS = {"train": ("2006-09-01", "2014-12-31"),
          "validation": ("2015-01-01", "2020-12-31"),
          "test": ("2021-01-01", "2026-09-11")}
GRID_W = (0.35, 0.50, 0.65)
GRID_BOND = ("IEF", "TLT")
N_CONFIGS = len(GRID_W) * len(GRID_BOND)

LOG = os.path.join(ROOT, "logs", "experiment_log.jsonl")
REPORTS = os.path.join(ROOT, "reports")

SYMS = ("QQQ", "IEF", "TLT")
series = {s: load_daily(os.path.join(ROOT, "data", "raw", f"US_{s}_daily.csv"))
          for s in SYMS}
dates = np.array([str(d) for d in series["QQQ"].date])

divs = {}
for s in SYMS:
    p = os.path.join(ROOT, "data", f"US_{s}_dividends_daily.csv")
    divs[s] = pd.read_csv(p) if os.path.exists(p) else pd.DataFrame()
    if not len(divs[s]):
        print(f"  WARNING: no dividend file for {s} - its yield is NOT modelled")


def bounds(split, lo_override=None):
    lo, hi = SPLITS[split]
    if lo_override:
        lo = lo_override
    idx = np.where((dates >= lo) & (dates <= hi))[0]
    return int(idx[0]), int(idx[-1]) + 1


def log_run(rec):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    rec["utc"] = datetime.now(timezone.utc).isoformat()
    rec["candidate"] = "V3 stock_bond"
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, default=str) + "\n")


def run(weights, split, *, label, fees=None, execution=None, month=1,
        lo_override=None, div_override=None):
    start, end = bounds(split, lo_override)
    bt = PortfolioBacktester(
        series, initial_cash=10_000.0,
        execution=execution or ExecutionModel(), fees=fees or FeeSchedule(),
        dividends=div_override if div_override is not None else divs,
        risk=RiskManager(RiskLimits(max_weight=1.0)), rebalance_month=month)
    res = bt.run(weights, start=start, end=end)
    s = res.summary
    m = {"label": label, "split": split, "weights": weights,
         "total_return": s["total_return"], "cagr": s["cagr"],
         "max_drawdown": s["max_drawdown"],
         "return_over_maxdd": s["return_over_maxdd"],
         "breached_20pct": s["breached_20pct"], "n_fills": s["n_fills"],
         "fees_pct_per_year": s["fees_pct_per_year"],
         "dividends": s["dividends_received"], "final_nav": s["final_nav"],
         "years": s["years"]}
    return res, m


def fmt(m):
    return (f"ret {m['total_return']:+9.1%}  cagr {(m['cagr'] or 0):+6.2%}  "
            f"maxDD {m['max_drawdown']:7.2%}  fills {m['n_fills']:4d}  "
            f"fees {m['fees_pct_per_year']:5.3f}%/yr  NAV {m['final_nav']:>9,.0f}"
            f"  {'BREACHED 20%' if m['breached_20pct'] else ''}")


print("=" * 118)
print("PREREGISTERED EXPERIMENT V3 - docs/preregistration_v3.md")
print("QQQ plus Treasuries, annual rebalance. No prediction, no signal.")
print("Training holds 2008 (the case FOR bonds); the final test holds 2022 (the case AGAINST).")
print("=" * 118)

print(f"\n### STEP 1 - grid on TRAINING {SPLITS['train'][0]} .. {SPLITS['train'][1]}"
      f"  (contains 2008)   {N_CONFIGS} configurations\n")
grid = []
for w in GRID_W:
    for b in GRID_BOND:
        weights = {"QQQ": w, b: round(1.0 - w, 4)}
        _, m = run(weights, "train", label=f"QQQ {w:.0%} / {b} {1-w:.0%}")
        m["w_eq"], m["bond"] = w, b
        grid.append(m)
        log_run({"phase": "train_grid", **m})
        print(f"  QQQ {w:.0%} / {b:<3} {1-w:.0%}   {fmt(m)}")

print("\n  comparators on the same period:")
comps_train = {}
for nm, weights in (("35% QQQ + cash  [INCUMBENT]", {"QQQ": 0.35}),
                    ("50% QQQ + cash", {"QQQ": 0.50}),
                    ("100% QQQ", {"QQQ": 1.0}),
                    ("100% IEF", {"IEF": 1.0}),
                    ("100% TLT", {"TLT": 1.0})):
    _, m = run(weights, "train", label=nm)
    comps_train[nm] = m
    log_run({"phase": "train_comparator", **m})
    print(f"  {nm:>28}   {fmt(m)}")

inside = [g for g in grid if not g["breached_20pct"]]
print(f"\n### STEP 2 - selection: highest CAGR among those inside a 20% drawdown")
if not inside:
    print("  A1 TRIPPED: no configuration stayed inside 20% on training.")
    best = None
else:
    best = max(inside, key=lambda g: g["cagr"])
    print(f"  {len(inside)}/{N_CONFIGS} configurations stayed inside 20%")
    print(f"  SELECTED: QQQ {best['w_eq']:.0%} / {best['bond']} {1-best['w_eq']:.0%}")
    print(f"  {fmt(best)}")
log_run({"phase": "selection",
         "selected": None if best is None else {"w_eq": best["w_eq"], "bond": best["bond"]},
         "n_inside_20pct": len(inside), "n_configs_searched": N_CONFIGS})

if best is None:
    print("\nCandidate rejected on training by A1. Stopping.")
    sys.exit(0)

print(f"\n### STEP 3 - VALIDATION {SPLITS['validation'][0]} .. {SPLITS['validation'][1]}\n")
sel_w = {"QQQ": best["w_eq"], best["bond"]: round(1.0 - best["w_eq"], 4)}
val_res, val = run(sel_w, "validation", label="V3 SELECTED")
log_run({"phase": "validation", **val})
print(f"  {'candidate':>28}   {fmt(val)}")
comps_val = {}
for nm, weights in (("35% QQQ + cash  [INCUMBENT]", {"QQQ": 0.35}),
                    ("50% QQQ + cash", {"QQQ": 0.50}),
                    ("100% QQQ", {"QQQ": 1.0}),
                    (f"100% {best['bond']}", {best["bond"]: 1.0})):
    _, m = run(weights, "validation", label=nm)
    comps_val[nm] = m
    log_run({"phase": "validation_comparator", **m})
    print(f"  {nm:>28}   {fmt(m)}")

print(f"\n### STEP 4 - abandon conditions on validation\n")
inc = comps_val["35% QQQ + cash  [INCUMBENT]"]
checks = {
    "A2 selected breaches 20% on validation": bool(val["breached_20pct"]),
    "A3 CAGR does not exceed the incumbent": val["cagr"] <= inc["cagr"],
    "A4 turnover breaches the 10%/yr fee ceiling": val["fees_pct_per_year"] > 10.0,
}
for k, t in checks.items():
    print(f"  [{'TRIPPED' if t else '  ok   '}]  {k}")
any_tripped = any(checks.values())
log_run({"phase": "abandon_checks", "checks": {k: bool(v) for k, v in checks.items()},
         "any_tripped": bool(any_tripped)})

print(f"\n### STEP 5 - FINAL TEST {SPLITS['test'][0]} .. {SPLITS['test'][1]}"
      f"  (contains 2022 - the case AGAINST bonds)\n")
if any_tripped:
    print("  Validation tripped an abandon condition; running to complete the process.")
    print("  Per the preregistration this is NOT out-of-sample evidence.")
test_res, test = run(sel_w, "test", label="V3 SELECTED")
log_run({"phase": "final_test", "validation_had_tripped": bool(any_tripped), **test})
print(f"  {'candidate':>28}   {fmt(test)}")
for nm, weights in (("35% QQQ + cash  [INCUMBENT]", {"QQQ": 0.35}),
                    ("50% QQQ + cash", {"QQQ": 0.50}),
                    ("100% QQQ", {"QQQ": 1.0}),
                    (f"100% {best['bond']}", {best["bond"]: 1.0})):
    _, m = run(weights, "test", label=nm)
    log_run({"phase": "final_test_comparator", **m})
    print(f"  {nm:>28}   {fmt(m)}")

print(f"\n### STEP 6 - stress variants\n")
stress = {}
for nm, kw, split in (
        ("S0 baseline (validation)", dict(), "validation"),
        ("S1 costs x2.0", dict(fees=FeeSchedule(platform_fee=1.98,
                                                settlement_per_share=0.006)), "validation"),
        ("S3 rebalance in July", dict(month=7), "validation"),
        ("S4 train from 2010 (no 2008)", dict(lo_override="2010-01-01"), "train"),
        ("S5 full sample, one pass", dict(lo_override="2006-09-01"), "test"),
):
    _, m = run(sel_w, split, label=f"V3 {nm}", **kw)
    stress[nm] = m
    log_run({"phase": "stress", "variant": nm, **m})
    print(f"  {nm:>30}   {fmt(m)}")

_, s2 = run(sel_w, "validation", label="V3 S2 withholding 0%",
            div_override={k: (v.assign(per_share_net=v["per_share_gross"])
                              if len(v) else v) for k, v in divs.items()})
stress["S2 withholding 0%"] = s2
log_run({"phase": "stress", "variant": "S2 withholding 0%", **s2})
print(f"  {'S2 withholding 0%':>30}   {fmt(s2)}")

os.makedirs(REPORTS, exist_ok=True)
pd.DataFrame(grid).to_csv(os.path.join(REPORTS, "v3_train_grid.csv"), index=False)
for nm, res in (("validation", val_res), ("test", test_res)):
    res.equity.to_csv(os.path.join(REPORTS, f"v3_equity_{nm}.csv"), index=False)
    res.fills.to_csv(os.path.join(REPORTS, f"v3_fills_{nm}.csv"), index=False)
with open(os.path.join(REPORTS, "v3_summary.json"), "w", encoding="utf-8") as fh:
    json.dump({"preregistration": "docs/preregistration_v3.md",
               "n_configs": N_CONFIGS,
               "selected": {"w_eq": best["w_eq"], "bond": best["bond"]},
               "train": {"grid": grid, "comparators": comps_train},
               "validation": {"candidate": val, "comparators": comps_val},
               "abandon_checks": {k: bool(v) for k, v in checks.items()},
               "any_tripped": bool(any_tripped),
               "final_test": {"candidate": test},
               "stress": stress}, fh, indent=2, default=str)
print("\nwritten: reports/v3_summary.json, v3_train_grid.csv, v3_equity_/fills_")
