"""Parameter search on a TRAINING window, with Optuna.

Replaces the hand-written grids in tools/run_experiment*.py for the selection step
only. The rest of the preregistered procedure is unchanged: whatever this returns is
frozen, run once on validation, checked against the abandon conditions, and run once
on the final test. A search that is cleverer about the training window earns no
extra looks at the test window - the budget of configurations declared in the
preregistration counts Optuna trials exactly as it counted grid points.

Ported from the first-phase framework (optimization/optimize.py, objective.py) and
rewritten against this project's engine summary. Two things carried over on purpose:

  - the RANDOM sampler as a control. If TPE's best training score is not better than
    random search's with the same budget, the "optimisation" is fitting noise and the
    ranking it produces means nothing. `compare_samplers` runs both.
  - a risk-adjusted score rather than return. Return alone selects the most leveraged
    configuration; this score is Sharpe plus a fraction of Calmar, clipped so one
    unstable ratio cannot dominate, with penalties for too few fills (a lucky handful)
    and for drawdown beyond a limit.

Optuna is an optional import. Everything else in the package works without it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

SESSIONS_PER_YEAR = 252


# ---------------- the score ----------------

@dataclass(frozen=True)
class ScoreConfig:
    min_fills: int = 20
    max_drawdown_limit: float = 0.20      # the mandate's abandon point
    calmar_weight: float = 0.25
    low_fill_penalty: float = 3.0
    drawdown_penalty: float = 2.0
    clip: float = 5.0
    version: str = "v2_sharpe_calmar_dd_fills"


def daily_returns(equity: pd.DataFrame) -> np.ndarray:
    """Session-close NAV returns. Works for daily and intraday equity frames."""
    nav = equity.groupby("date", sort=True)["nav"].last().to_numpy(dtype=float)
    if len(nav) < 2:
        return np.array([], dtype=float)
    return nav[1:] / nav[:-1] - 1.0


def metrics_from_result(equity: pd.DataFrame, summary: dict) -> dict:
    r = daily_returns(equity)
    sd = float(np.std(r, ddof=1)) if len(r) > 1 else 0.0
    sharpe = float(np.mean(r) / sd * np.sqrt(SESSIONS_PER_YEAR)) if sd > 0 else 0.0
    cagr = summary.get("cagr")
    mdd = float(summary.get("max_drawdown", 0.0))
    calmar = float(cagr / abs(mdd)) if cagr is not None and mdd < 0 else 0.0
    return {"sharpe": sharpe, "calmar": calmar, "cagr": cagr, "max_drawdown": mdd,
            "n_fills": int(summary.get("n_fills", 0)),
            "total_fees": float(summary.get("total_fees", 0.0)),
            "halted": bool(summary.get("halted", False))}


def score(metrics: dict, cfg: ScoreConfig = ScoreConfig()) -> float:
    c = cfg.clip
    sh = float(np.clip(metrics["sharpe"], -c, c))
    ca = float(np.clip(metrics["calmar"], -c, c))
    shortfall = max(0.0, cfg.min_fills - metrics["n_fills"]) / max(cfg.min_fills, 1)
    excess_dd = max(0.0, abs(metrics["max_drawdown"]) - cfg.max_drawdown_limit)
    return float(sh + cfg.calmar_weight * ca
                 - cfg.low_fill_penalty * shortfall
                 - cfg.drawdown_penalty * excess_dd)


# ---------------- the search ----------------

@dataclass(frozen=True)
class Int:
    lo: int
    hi: int


@dataclass(frozen=True)
class Float:
    lo: float
    hi: float
    log: bool = False


@dataclass(frozen=True)
class Choice:
    options: tuple


Space = dict  # name -> Int | Float | Choice


@dataclass
class TuneResult:
    sampler: str
    n_trials: int
    seed: int
    best_params: dict | None
    best_score: float | None
    trials: pd.DataFrame = field(default_factory=pd.DataFrame)

    def as_dict(self) -> dict:
        return {"sampler": self.sampler, "n_trials": self.n_trials, "seed": self.seed,
                "best_params": self.best_params, "best_score": self.best_score,
                "n_completed": int((self.trials["state"] == "COMPLETE").sum())
                if len(self.trials) else 0}


def _suggest(trial, space: Space) -> dict:
    out = {}
    for name, spec in space.items():
        if isinstance(spec, Int):
            out[name] = trial.suggest_int(name, spec.lo, spec.hi)
        elif isinstance(spec, Float):
            out[name] = trial.suggest_float(name, spec.lo, spec.hi, log=spec.log)
        elif isinstance(spec, Choice):
            out[name] = trial.suggest_categorical(name, list(spec.options))
        else:
            raise TypeError(f"{name}: unsupported space entry {spec!r}")
    return out


def tune(objective: Callable[[dict], tuple[float, dict]], space: Space, *,
         n_trials: int, seed: int = 0, sampler: str = "tpe") -> TuneResult:
    """Maximise `objective(params) -> (score, metrics)` over `space`.

    A ValueError raised by the objective (an invalid parameter combination, a strategy
    constructor refusing its inputs) marks that trial FAILED and the search continues;
    any other exception propagates, because a crash is not a bad parameter set.
    """
    try:
        import optuna
    except ImportError as exc:                            # pragma: no cover
        raise RuntimeError("optuna is required for tuning: pip install optuna") from exc
    if n_trials < 1:
        raise ValueError("n_trials must be positive")
    if sampler not in ("tpe", "random"):
        raise ValueError("sampler must be 'tpe' or 'random'")
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    smp = (optuna.samplers.TPESampler(seed=seed) if sampler == "tpe"
           else optuna.samplers.RandomSampler(seed=seed))
    study = optuna.create_study(direction="maximize", sampler=smp)

    def _obj(trial):
        params = _suggest(trial, space)
        s, m = objective(params)
        trial.set_user_attr("params", params)
        trial.set_user_attr("metrics", m)
        return float(s)

    study.optimize(_obj, n_trials=n_trials, catch=(ValueError,))

    rows = []
    for t in study.trials:
        row = {"trial": t.number, "state": t.state.name, "score": t.value}
        row.update(t.user_attrs.get("params", {}))
        row.update({f"m_{k}": v for k, v in t.user_attrs.get("metrics", {}).items()})
        rows.append(row)
    trials = pd.DataFrame(rows)
    done = [t for t in study.trials if t.value is not None and "params" in t.user_attrs]
    if not done:
        return TuneResult(sampler, n_trials, seed, None, None, trials)
    best = max(done, key=lambda t: t.value)
    return TuneResult(sampler, n_trials, seed, dict(best.user_attrs["params"]),
                      float(best.value), trials)


def compare_samplers(objective, space: Space, *, n_trials: int, seed: int = 0) -> dict:
    """TPE against random search at the same budget. The question is not which found a
    higher training score - both are in-sample - but whether TPE's advantage is large
    enough to suggest the surface has structure rather than noise."""
    tpe = tune(objective, space, n_trials=n_trials, seed=seed, sampler="tpe")
    rnd = tune(objective, space, n_trials=n_trials, seed=seed, sampler="random")
    return {"tpe": tpe.as_dict(), "random": rnd.as_dict(),
            "tpe_minus_random": (None if tpe.best_score is None or rnd.best_score is None
                                 else float(tpe.best_score - rnd.best_score))}


def neighbourhood(params: dict, steps: dict) -> list[dict]:
    """Every combination of each parameter at value, value-step, value+step.

    For the plateau check: a chosen parameter set whose neighbours score much worse is
    a spike the search found in noise, not a region. Parameters absent from `steps`
    are held fixed.
    """
    keys = [k for k in params if k in steps]
    grids = []
    for k in keys:
        v, st = params[k], steps[k]
        grids.append(sorted({v - st, v, v + st}))
    out = []

    def rec(i, cur):
        if i == len(keys):
            out.append({**params, **cur})
            return
        for val in grids[i]:
            rec(i + 1, {**cur, keys[i]: val})
    rec(0, {})
    return out
