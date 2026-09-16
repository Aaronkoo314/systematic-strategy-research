"""Ex-ante power gate.

The gate decides whether a backtest is worth running at all, so its own arithmetic has
to be checkable by hand rather than trusted.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.validation.power import (  # noqa: E402
    SESSIONS_PER_YEAR, effective_sample_size, power_gate, tracking_error_of_overlay, _z,
)


def test_critical_values_match_the_standard_normal():
    assert _z(0.05) == pytest.approx(1.959964, abs=1e-4)
    assert _z(0.01) == pytest.approx(2.575829, abs=1e-4)


def test_standard_error_shrinks_with_the_square_root_of_time():
    a = power_gate(0.20, 4.0)
    b = power_gate(0.20, 16.0)
    assert b.se_annual == pytest.approx(a.se_annual / 2.0, rel=1e-9)


def test_minimum_detectable_alpha_is_hand_checkable():
    """te 20 %, 9 years -> se = 20/3 = 6.667 %; 80 % power -> (1.96 + 0.8416) * se."""
    r = power_gate(0.20, 9.0)
    assert r.se_annual == pytest.approx(0.0666667, abs=1e-6)
    assert r.min_detectable_alpha_50pct_power == pytest.approx(1.959964 * 0.0666667, abs=1e-6)
    assert r.min_detectable_alpha_80pct_power == pytest.approx(
        (1.959964 + 0.8416) * 0.0666667, abs=1e-5)


def test_searching_more_configurations_raises_the_bar():
    """The best of N is inflated by selection, so the critical value must rise with N."""
    one = power_gate(0.17, 8.0, n_configs=1)
    many = power_gate(0.17, 8.0, n_configs=24)
    assert many.z_critical > one.z_critical
    assert many.min_detectable_alpha_80pct_power > one.min_detectable_alpha_80pct_power


def test_years_needed_scales_with_the_inverse_square_of_alpha():
    """Halving the claimed alpha quadruples the sample needed."""
    big = power_gate(0.17, 8.0, target_alpha=0.20)
    small = power_gate(0.17, 8.0, target_alpha=0.10)
    assert small.years_needed_for_target == pytest.approx(
        4 * big.years_needed_for_target, rel=1e-9)


def test_gate_fails_when_the_required_sample_exceeds_the_available_one():
    r = power_gate(0.17, 8.0, n_configs=24, target_alpha=0.10)
    assert r.passes is False
    assert "FAIL" in r.verdict
    assert "without a backtest" in r.verdict


def test_gate_passes_when_the_claim_is_large_relative_to_the_noise():
    r = power_gate(0.05, 20.0, n_configs=1, target_alpha=0.10)
    assert r.passes is True
    assert "PASS" in r.verdict


def test_tracking_error_is_zero_for_a_full_exposure_overlay():
    """Always in the market IS buy-and-hold, so there is nothing to track."""
    rng = np.random.default_rng(0)
    r = rng.normal(0.0005, 0.012, 2000)
    assert tracking_error_of_overlay(r, 1.0) == pytest.approx(0.0, abs=1e-12)


def test_tracking_error_is_largest_at_full_divestment():
    rng = np.random.default_rng(0)
    r = rng.normal(0.0005, 0.012, 2000)
    out = tracking_error_of_overlay(r, 0.0)
    half = tracking_error_of_overlay(r, 0.5)
    assert out > half > 0


def test_tracking_error_does_not_depend_on_skill():
    """The point of the gate: a skilful rule and a worthless one share this denominator."""
    rng = np.random.default_rng(1)
    r = rng.normal(0.0005, 0.012, 3000)
    a = tracking_error_of_overlay(r, 0.5, seed=0)
    b = tracking_error_of_overlay(r, 0.5, seed=99)
    assert a == pytest.approx(b, rel=0.05)


def test_effective_sample_size_equals_n_for_independent_data():
    rng = np.random.default_rng(3)
    r = rng.normal(0.0, 0.01, 5000)
    assert effective_sample_size(r) == pytest.approx(len(r), rel=0.15)


def test_effective_sample_size_falls_with_positive_autocorrelation():
    """Correlated observations are worth less than their count - the reason bar counts
    must never be quoted as sample size."""
    rng = np.random.default_rng(4)
    e = rng.normal(0.0, 0.01, 6000)
    r = np.zeros_like(e)
    for i in range(1, len(e)):
        r[i] = 0.6 * r[i - 1] + e[i]
    assert effective_sample_size(r) < 0.5 * len(r)


def test_invalid_inputs_rejected():
    for kwargs in (dict(tracking_error=0.0, years_available=8.0),
                   dict(tracking_error=0.2, years_available=0.0)):
        with pytest.raises(ValueError):
            power_gate(**kwargs)
    with pytest.raises(ValueError):
        power_gate(0.2, 8.0, n_configs=0)
    with pytest.raises(ValueError):
        power_gate(0.2, 8.0, target_alpha=-0.05)
    with pytest.raises(ValueError):
        tracking_error_of_overlay(np.zeros(10), 1.5)
