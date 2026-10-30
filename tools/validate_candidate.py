"""End-to-end validation of a candidate rule: Optuna on each training window,
frozen run on the following test window, buy-and-hold alongside, then a bootstrap
of the out-of-sample trades.

This is the second-phase VALIDATION pipeline applied to a first-phase style rule. It
is deliberately not a preregistered experiment: it has no frozen abandon conditions
and no once-only final test, so nothing it prints is evidence a rule works. It is the
screen that decides whether a rule is worth preregistering at all.

The candidate is the dip-buying rule from preregistration V2 (two parameters, k and l).
That rule was rejected; it is used here because it is small, already in the
repository, and its parameters are genuinely searchable.

Usage:
    python tools/validate_candidate.py                 # daily QQQ, data/raw/US_QQQ_daily.csv
    python tools/validate_candidate.py --synthetic     # random walk, no data needed
    python tools/validate_candidate.py --trials 40 --train 1000 --test 250

Outputs reports/validation_demo/{folds.csv, stitched.csv, summary.json}.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.backtest.engine import Backtester, ExecutionModel  # noqa: E402
from src.costs.fees import FeeSchedule  # noqa: E402
from src.data.bars import BarSeries, FREQ_DAILY, load_daily  # noqa: E402
from src.strategy.dip_buy import DipBuy  # noqa: E402
from src.validation import monte_carlo, tuning  # noqa: E402
from src.validation.walk_forward import build_folds, walk_forward  # noqa: E402

OUT = os.path.join(ROOT, "reports", "validation_demo")


def synthetic(n: int, seed: int) -> BarSeries:
    """A random walk with drift. Any edge found on it is, by construction, noise."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0004, 0.012, n)
    close = 100.0 * np.cumprod(1.0 + r)
    open_ = np.r_[100.0, close[:-1]] * (1.0 + rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0, 0.004, n)))
    low = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0, 0.004, n)))
    dates = pd.bdate_range("2006-09-01", periods=n)
    df = pd.DataFrame({"time_key": [f"{d:%Y-%m-%d} 16:00:00" for d in dates],
                       "open": open_, "high": high, "low": low, "close": close,
                       "volume": np.full(n, 5e7)})
    return BarSeries(df, frequency=FREQ_DAILY)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--trials", type=int, default=30)
    ap.add_argument("--train", type=int, default=1000, help="training sessions per fold")
    ap.add_argument("--test", type=int, default=250, help="test sessions per fold")
    ap.add_argument("--window", choices=("rolling", "expanding"), default="rolling")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--paths", type=int, default=1000)
    args = ap.parse_args()

    if args.synthetic:
        bars = synthetic(3000, args.seed)
        source = "synthetic random walk"
    else:
        path = os.path.join(ROOT, "data", "raw", "US_QQQ_daily.csv")
        if not os.path.exists(path):
            sys.exit(f"{path} not found; run tools/audit_data.py or pass --synthetic")
        bars = load_daily(path)
        source = path

    def make_bt():
        # Halts are bypassed on purpose and the engine records that in its summary:
        # a drawdown halt never resumes inside a backtest (docs/halt_contamination.md),
        # so leaving it on measures the halt, not the rule.
        return Backtester(bars, initial_cash=10_000.0, execution=ExecutionModel(),
                          fees=FeeSchedule(), bypass_risk_controls=True)

    space = {"k": tuning.Float(0.5, 8.0), "l": tuning.Int(5, 120)}

    def select(train, fold):
        def objective(p):
            rule = DipBuy(k=p["k"], l=p["l"])
            bt = Backtester(train, initial_cash=10_000.0, execution=ExecutionModel(),
                            fees=FeeSchedule(), bypass_risk_controls=True,
                            lookback=rule.lookback)
            res = bt.run(rule, warmup=rule.warmup)
            m = tuning.metrics_from_result(res.equity, res.summary)
            return tuning.score(m), m
        cmp = tuning.compare_samplers(objective, space, n_trials=args.trials,
                                      seed=args.seed + fold.number)
        best = cmp["tpe"]["best_params"]
        rule = DipBuy(k=best["k"], l=best["l"])
        return rule, f"dip_buy(k={best['k']:.2f}, l={best['l']})", cmp

    folds = build_folds(bars, train_sessions=args.train, test_sessions=args.test,
                        window=args.window)
    if not folds:
        sys.exit("not enough sessions for one fold")
    print(f"{source}: {len(bars)} sessions, {len(folds)} folds "
          f"({args.window}, train {args.train}, test {args.test})")

    wf = walk_forward(bars, select, folds, make_backtester=make_bt, warmup=130)
    tab = wf.table()
    cols = ["fold", "strategy", "oos_return", "hold_return", "excess_vs_hold",
            "oos_max_drawdown", "n_fills", "fees"]
    print(tab[cols].to_string(index=False, float_format=lambda x: f"{x:+.4f}"))
    print("\nout-of-sample, stitched:")
    for k, v in wf.summary.items():
        print(f"  {k:>22}: {v}")

    gaps = [fr.selection["tpe_minus_random"] for fr in wf.folds]
    print(f"\nTPE minus random, best training score per fold: "
          f"{np.round(gaps, 3).tolist()}")

    # Returns on NAV are computed per fold against that fold's own equity frame, then
    # chained: the fold runs overlap on their warmup bars, so their equity frames
    # cannot simply be concatenated.
    r_oos = np.concatenate([monte_carlo.returns_on_nav(fr.test.trades, fr.test.equity)
                            for fr in wf.folds if len(fr.test.trades)]) \
        if any(len(fr.test.trades) for fr in wf.folds) else np.array([])
    mc = {}
    if len(r_oos):
        for block in (1, 5):
            b = min(block, len(r_oos))
            paths = monte_carlo.bootstrap(r_oos, n_paths=args.paths, seed=args.seed, block=b)
            s = monte_carlo.summarise(r_oos, paths, block=b)
            mc[f"block_{block}"] = s.as_dict()
            print(f"\nbootstrap, block {block}: P(loss) {s.probability_of_loss:.2f}, "
                  f"terminal p05 {s.terminal_return_p05:+.3f}, "
                  f"maxDD p05 {s.max_drawdown_p05:+.3f}, "
                  f"historical sits at the {s.historical_percentile:.0%} percentile")
    else:
        print("\nno round trips out of sample; nothing to resample")

    os.makedirs(OUT, exist_ok=True)
    tab.to_csv(os.path.join(OUT, "folds.csv"), index=False)
    wf.stitched.to_csv(os.path.join(OUT, "stitched.csv"), index=False)
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump({"source": source, "args": vars(args), "summary": wf.summary,
                   "selection": [fr.selection for fr in wf.folds],
                   "monte_carlo": mc}, fh, indent=2, default=str)
    print(f"\nwritten: {OUT}")


if __name__ == "__main__":
    main()
