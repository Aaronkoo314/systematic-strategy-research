"""Optuna search: the score is hand-checkable, invalid parameter sets fail the trial
rather than the search, and the search finds a known optimum on a smooth surface."""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.validation.tuning import (  # noqa: E402
    Choice, Float, Int, ScoreConfig, compare_samplers, daily_returns,
    metrics_from_result, neighbourhood, score, tune,
)

optuna = pytest.importorskip("optuna")


# ---------------- score ----------------

def test_score_is_sharpe_plus_quarter_calmar_when_nothing_is_penalised():
    m = {"sharpe": 1.2, "calmar": 0.8, "n_fills": 50, "max_drawdown": -0.10}
    assert score(m) == pytest.approx(1.2 + 0.25 * 0.8)


def test_score_penalises_too_few_fills_and_excess_drawdown():
    cfg = ScoreConfig(min_fills=20, max_drawdown_limit=0.20)
    m = {"sharpe": 1.0, "calmar": 0.0, "n_fills": 10, "max_drawdown": -0.30}
    # shortfall 10/20 = 0.5 * 3 = 1.5 ; excess dd 0.10 * 2 = 0.2
    assert score(m, cfg) == pytest.approx(1.0 - 1.5 - 0.2)


def test_score_clips_unstable_ratios():
    m = {"sharpe": 40.0, "calmar": -40.0, "n_fills": 50, "max_drawdown": -0.05}
    assert score(m) == pytest.approx(5.0 + 0.25 * -5.0)


def test_daily_returns_use_session_close_nav():
    eq = pd.DataFrame({"date": ["d1", "d1", "d2", "d2", "d3"],
                       "nav": [100, 105, 103, 110, 99]})
    assert daily_returns(eq) == pytest.approx([110 / 105 - 1, 99 / 110 - 1])


def test_metrics_from_result_computes_calmar_from_summary():
    eq = pd.DataFrame({"date": ["d1", "d2", "d3"], "nav": [100.0, 101.0, 102.0]})
    m = metrics_from_result(eq, {"cagr": 0.10, "max_drawdown": -0.05, "n_fills": 3,
                                 "total_fees": 1.0})
    assert m["calmar"] == pytest.approx(2.0)
    assert m["sharpe"] > 0


# ---------------- search ----------------

def _bowl(params):
    """Maximum at x=3, y=-1. Score known exactly."""
    x, y = params["x"], params["y"]
    s = 10.0 - (x - 3.0) ** 2 - (y + 1.0) ** 2
    return s, {"x": x, "y": y}


SPACE = {"x": Float(-5.0, 5.0), "y": Float(-5.0, 5.0)}


def test_tpe_finds_the_bowl_maximum():
    r = tune(_bowl, SPACE, n_trials=80, seed=0, sampler="tpe")
    assert r.best_score is not None and r.best_score > 9.0
    assert abs(r.best_params["x"] - 3.0) < 1.0
    assert abs(r.best_params["y"] + 1.0) < 1.0
    assert len(r.trials) == 80
    assert (r.trials["state"] == "COMPLETE").all()


def test_same_seed_reproduces_the_search():
    a = tune(_bowl, SPACE, n_trials=15, seed=4, sampler="random")
    b = tune(_bowl, SPACE, n_trials=15, seed=4, sampler="random")
    assert a.trials["score"].tolist() == b.trials["score"].tolist()


def test_value_error_fails_the_trial_not_the_search():
    def obj(p):
        if p["k"] % 2 == 0:
            raise ValueError("even k is not allowed")
        return float(p["k"]), {}
    r = tune(obj, {"k": Int(1, 10)}, n_trials=20, seed=1, sampler="random")
    states = set(r.trials["state"])
    assert "FAIL" in states and "COMPLETE" in states
    assert r.best_params["k"] % 2 == 1


def test_other_exceptions_propagate():
    def obj(p):
        raise RuntimeError("a crash, not a bad parameter")
    with pytest.raises(RuntimeError):
        tune(obj, {"k": Int(1, 3)}, n_trials=2, seed=0)


def test_categorical_and_int_spaces():
    def obj(p):
        return (1.0 if p["mode"] == "b" else 0.0) + p["n"] / 100.0, {}
    r = tune(obj, {"mode": Choice(("a", "b")), "n": Int(1, 5)}, n_trials=30, seed=0)
    assert r.best_params["mode"] == "b"
    assert r.best_params["n"] == 5


def test_compare_samplers_reports_both():
    out = compare_samplers(_bowl, SPACE, n_trials=20, seed=0)
    assert set(out) == {"tpe", "random", "tpe_minus_random"}
    assert out["tpe"]["n_completed"] == 20


def test_invalid_arguments():
    with pytest.raises(ValueError):
        tune(_bowl, SPACE, n_trials=0)
    with pytest.raises(ValueError):
        tune(_bowl, SPACE, n_trials=1, sampler="grid")


# ---------------- plateau ----------------

def test_neighbourhood_enumerates_three_to_the_k_points():
    pts = neighbourhood({"k": 2.0, "l": 20, "fixed": "x"}, {"k": 0.5, "l": 5})
    assert len(pts) == 9
    assert {p["k"] for p in pts} == {1.5, 2.0, 2.5}
    assert {p["l"] for p in pts} == {15, 20, 25}
    assert all(p["fixed"] == "x" for p in pts)
