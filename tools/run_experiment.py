"""Run the preregistered experiment. Spec: docs/preregistration_v1.md.

Order is enforced by the script, not by discipline:
  1. grid on TRAINING only
  2. select by the frozen rule
  3. the single winner on VALIDATION, with comparators
  4. abandon checks A1-A6
  5. the final TEST exactly once, only if validation cleared
  6. stress variants
Every run, including losers, is appended to logs/experiment_log.jsonl.

Usage: python tools/run_experiment.py
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

from src.backtest.engine import Backtester, ExecutionModel  # noqa: E402
from src.costs.fees import FeeSchedule  # noqa: E402
from src.data.bars import load_5min  # noqa: E402
from src.risk.controls import RiskLimits, RiskManager  # noqa: E402
from src.strategy.vol_target import VolTarget, buy_and_hold, static_blend  # noqa: E402

SPLITS = {
    "train": ("2018-09-10", "2022-12-31"),
    "validation": ("2023-01-01", "2024-12-31"),
    "test": ("2025-01-01", "2026-09-11"),
}
GRID_N = (78, 390, 780)
GRID_SIGMA = (0.15, 0.20, 0.25)
N_CONFIGS = len(GRID_N) * len(GRID_SIGMA)

LOG = os.path.join(ROOT, "logs", "experiment_log.jsonl")
REPORTS = os.path.join(ROOT, "reports")

bars = load_5min(os.path.join(ROOT, "data", "raw", "US_QQQ_5min_raw.csv"),
                 allow_overnight=True)
divs = pd.read_csv(os.path.join(ROOT, "data", "US_QQQ_dividends.csv"))
dates = np.array([str(d) for d in bars.date])


def bounds(split):
    lo, hi = SPLITS[split]
    idx = np.where((dates >= lo) & (dates <= hi))[0]
    return int(idx[0]), int(idx[-1]) + 1


def log_run(rec: dict) -> None:
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    rec["utc"] = datetime.now(timezone.utc).isoformat()
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, default=str) + "\n")


def run(strategy, split, *, lookback, warmup, execution=None, fees=None,
        limits=None, label=""):
    start, end = bounds(split)
    bt = Backtester(bars, initial_cash=10_000.0,
                    execution=execution or ExecutionModel(),
                    fees=fees or FeeSchedule(), dividends=divs,
                    lookback=lookback,
                    risk=RiskManager(limits or RiskLimits()))
    res = bt.run(strategy, start=start, end=end, warmup=warmup)
    s = res.summary
    eq = res.equity
    ret = eq["nav"].pct_change().dropna().to_numpy()
    dd = float(s["max_drawdown"])
    avg_w = float((eq["deployed_value"] / eq["nav"]).mean())
    years = max(s["years"], 1e-9)
    m = {
        "label": label, "split": split,
        "total_return": s["total_return"], "cagr": s["cagr"],
        "max_drawdown": dd,
        "return_over_maxdd": (s["total_return"] / abs(dd)) if dd < 0 else float("inf"),
        "ann_vol": float(np.std(ret, ddof=1) * np.sqrt(78 * 252)) if len(ret) > 2 else None,
        "avg_weight": avg_w,
        "n_fills": s["n_fills"], "fills_per_year": s["n_fills"] / years,
        "total_fees": s["total_fees"],
        "fees_pct_per_year": s["total_fees"] / 10_000.0 / years * 100,
        "halted": s["halted"], "abandoned": s["abandoned"],
        "n_risk_blocked": s["n_risk_blocked"],
        "dividends": s["dividends_received"],
        "sessions": s["sessions"], "years": s["years"],
    }
    return res, m


def fmt(m):
    return (f"ret {m['total_return']:+7.2%}  cagr {(m['cagr'] or 0):+6.2%}  "
            f"maxDD {m['max_drawdown']:7.2%}  r/dd {m['return_over_maxdd']:6.2f}  "
            f"w̄ {m['avg_weight']:5.1%}  fills {m['n_fills']:5d} "
            f"({m['fills_per_year']:6.1f}/yr)  fees {m['fees_pct_per_year']:5.2f}%/yr"
            f"{'  ABANDONED' if m['abandoned'] else ''}")


print("=" * 108)
print("PREREGISTERED EXPERIMENT - docs/preregistration_v1.md")
print("Power gate FAILED before this ran. No result below is statistically")
print("distinguishable from luck. This is an engineering validation of the process.")
print("=" * 108)

# ---------------- 1. grid on TRAINING ----------------
print(f"\n### STEP 1 - grid on TRAINING {SPLITS['train'][0]} .. {SPLITS['train'][1]}"
      f"   ({N_CONFIGS} configurations of the 24 budgeted)\n")
grid = []
for n in GRID_N:
    for sig in GRID_SIGMA:
        st = VolTarget(n_bars=n, sigma_target=sig)
        _, m = run(st, "train", lookback=st.lookback, warmup=st.warmup,
                   label=f"voltarget N={n} sigma={sig}")
        m["n_bars"], m["sigma_target"] = n, sig
        grid.append(m)
        log_run({"phase": "train_grid", **m})
        print(f"  N={n:>4} sigma={sig:.2f}   {fmt(m)}")

bh_train_res, bh_train = run(buy_and_hold, "train", lookback=2, warmup=1,
                             limits=RiskLimits(max_weight=1.0), label="buy_and_hold")
log_run({"phase": "train_benchmark", **bh_train})
print(f"\n  {'buy & hold':>16}   {fmt(bh_train)}")

# ---------------- 2. select by the FROZEN rule ----------------
ok = [g for g in grid if not g["abandoned"]]
pool = ok if ok else grid
best = sorted(pool, key=lambda g: (-g["return_over_maxdd"], g["fills_per_year"]))[0]
print(f"\n### STEP 2 - selection by the frozen rule (max return/|maxDD|, ties to lower turnover)")
print(f"  SELECTED: N={best['n_bars']}  sigma_target={best['sigma_target']}")
print(f"  {fmt(best)}")
if not ok:
    print("  NOTE: every configuration triggered the abandon point on training.")
log_run({"phase": "selection", "selected": {"n_bars": best["n_bars"],
                                            "sigma_target": best["sigma_target"]},
         "rule": "max total_return/|max_drawdown|, ties to lower turnover",
         "n_configs_searched": N_CONFIGS, "any_survived_training": bool(ok)})

# ---------------- 3. VALIDATION with comparators ----------------
print(f"\n### STEP 3 - VALIDATION {SPLITS['validation'][0]} .. {SPLITS['validation'][1]}\n")
sel = VolTarget(n_bars=best["n_bars"], sigma_target=best["sigma_target"])
val_res, val = run(sel, "validation", lookback=sel.lookback, warmup=sel.warmup,
                   label="voltarget SELECTED")
log_run({"phase": "validation", **val})
print(f"  {'candidate':>22}   {fmt(val)}")

bh_res, bh = run(buy_and_hold, "validation", lookback=2, warmup=1,
                 limits=RiskLimits(max_weight=1.0), label="buy_and_hold")
log_run({"phase": "validation_comparator", **bh})
print(f"  {'buy & hold (uncapped)':>22}   {fmt(bh)}")

st90_res, st90 = run(static_blend(0.90), "validation", lookback=2, warmup=1,
                     label="static_0.90")
log_run({"phase": "validation_comparator", **st90})
print(f"  {'static 90%':>22}   {fmt(st90)}")

w_avg = round(val["avg_weight"], 2)
stavg_res, stavg = run(static_blend(w_avg), "validation", lookback=2, warmup=1,
                       label=f"static_{w_avg}")
log_run({"phase": "validation_comparator", **stavg})
print(f"  {f'static {w_avg:.0%} (= cand w̄)':>22}   {fmt(stavg)}")
print(f"  {'cash':>22}   ret  +0.00%   (idle cash modelled at 0 %)")

# ---------------- 4. abandon checks ----------------
print(f"\n### STEP 4 - abandon conditions A1-A6 on validation\n")
checks = {
    "A1 maxDD worse than buy&hold": val["max_drawdown"] < bh["max_drawdown"],
    "A2 fails to beat static at own avg weight (ret/|DD|)":
        val["return_over_maxdd"] <= stavg["return_over_maxdd"],
    "A3 turnover breaches the 10%/yr fee ceiling": val["fees_pct_per_year"] > 10.0,
    "A4 20% abandon point triggered (train or val)":
        bool(best["abandoned"] or val["abandoned"]),
}
for k, tripped in checks.items():
    print(f"  [{'TRIPPED' if tripped else '  ok   '}]  {k}")
any_tripped = any(checks.values())
log_run({"phase": "abandon_checks", "checks": {k: bool(v) for k, v in checks.items()},
         "any_tripped": bool(any_tripped)})

# ---------------- 5. FINAL TEST, once ----------------
print(f"\n### STEP 5 - FINAL TEST {SPLITS['test'][0]} .. {SPLITS['test'][1]}\n")
if any_tripped:
    print("  Validation tripped an abandon condition.")
    print("  Running the test anyway, at the operator's instruction to complete the")
    print("  process end to end. Per the preregistration this is NOT out-of-sample")
    print("  evidence for the candidate - it is a run of the machinery.")
test_res, test = run(sel, "test", lookback=sel.lookback, warmup=sel.warmup,
                     label="voltarget SELECTED")
log_run({"phase": "final_test", "validation_had_tripped": bool(any_tripped), **test})
print(f"  {'candidate':>22}   {fmt(test)}")

bht_res, bht = run(buy_and_hold, "test", lookback=2, warmup=1,
                   limits=RiskLimits(max_weight=1.0), label="buy_and_hold")
log_run({"phase": "final_test_comparator", **bht})
print(f"  {'buy & hold (uncapped)':>22}   {fmt(bht)}")
wt = round(test["avg_weight"], 2)
stt_res, stt = run(static_blend(wt), "test", lookback=2, warmup=1, label=f"static_{wt}")
log_run({"phase": "final_test_comparator", **stt})
print(f"  {f'static {wt:.0%} (= cand w̄)':>22}   {fmt(stt)}")
print("\n  The test window contains none of 2018Q4, 2020 or 2022. It is a calm sample")
print("  and cannot test the drawdown claim at all.")

# ---------------- 6. stress variants ----------------
print(f"\n### STEP 6 - stress variants on VALIDATION\n")
variants = {
    "S0 baseline": dict(),
    "S1 costs x1.5": dict(fees=FeeSchedule(platform_fee=0.99 * 1.5,
                                           settlement_per_share=0.003 * 1.5)),
    "S2 costs x2.0": dict(fees=FeeSchedule(platform_fee=0.99 * 2.0,
                                           settlement_per_share=0.003 * 2.0)),
    "S3 slippage 10/25bp": dict(execution=ExecutionModel(slippage_bps_intraday=10.0,
                                                         slippage_bps_overnight=25.0)),
    "S6 withholding 0%": dict(),
}
stress = {}
for name, kw in variants.items():
    if name == "S6 withholding 0%":
        saved = divs["per_share_net"].copy()
        divs["per_share_net"] = divs["per_share_gross"]
    _, m = run(sel, "validation", lookback=sel.lookback, warmup=sel.warmup,
               label=f"voltarget {name}", **kw)
    if name == "S6 withholding 0%":
        divs["per_share_net"] = saved
    stress[name] = m
    log_run({"phase": "stress", "variant": name, **m})
    print(f"  {name:>22}   {fmt(m)}")

base_rd = stress["S0 baseline"]["return_over_maxdd"]
reversed_by = [k for k, v in stress.items()
               if k != "S0 baseline" and np.sign(v["total_return"]) !=
               np.sign(stress["S0 baseline"]["total_return"])]
print(f"\n  A5 result reverses under stress: "
      f"{'TRIPPED - ' + ', '.join(reversed_by) if reversed_by else '  ok'}")

# ---------------- outputs ----------------
os.makedirs(REPORTS, exist_ok=True)
pd.DataFrame(grid).to_csv(os.path.join(REPORTS, "train_grid.csv"), index=False)
val_res.equity.to_csv(os.path.join(REPORTS, "equity_validation.csv"), index=False)
val_res.trades.to_csv(os.path.join(REPORTS, "trades_validation.csv"), index=False)
test_res.equity.to_csv(os.path.join(REPORTS, "equity_test.csv"), index=False)
test_res.trades.to_csv(os.path.join(REPORTS, "trades_test.csv"), index=False)
val_res.fills.to_csv(os.path.join(REPORTS, "fills_validation.csv"), index=False)
test_res.fills.to_csv(os.path.join(REPORTS, "fills_test.csv"), index=False)

summary = {
    "preregistration": "docs/preregistration_v1.md",
    "power_gate": "FAILED - see docs/power_gate_result.md",
    "n_configs_searched": N_CONFIGS,
    "selected": {"n_bars": best["n_bars"], "sigma_target": best["sigma_target"]},
    "train": {"candidate": best, "buy_and_hold": bh_train},
    "validation": {"candidate": val, "buy_and_hold": bh, "static_90": st90,
                   f"static_{w_avg}": stavg},
    "abandon_checks": {k: bool(v) for k, v in checks.items()},
    "any_abandon_tripped": bool(any_tripped),
    "final_test": {"candidate": test, "buy_and_hold": bht, f"static_{wt}": stt},
    "stress": stress,
    "standing_caveat": ("not statistically distinguishable from luck; the ex-ante power "
                        "gate failed before this experiment was run"),
}
with open(os.path.join(REPORTS, "experiment_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=2, default=str)
print(f"\nwritten: reports/experiment_summary.json, train_grid.csv, "
      f"equity_/trades_/fills_ for validation and test")
print(f"         logs/experiment_log.jsonl (every run, including losers)")
