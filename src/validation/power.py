"""Ex-ante statistical power. The gate that runs BEFORE any backtest.

selection_criteria.md appendix A.5(a): a candidate must submit a power calculation with
its proposal, and if the sample length required exceeds the sample length available, it
is rejected without a backtest.

The gate exists because of a specific, common way to waste months: run a backtest, get a
number, and never ask whether a number of that size could have been distinguished from
luck on the data available. If the answer is no, the backtest was decoration.

Nothing here uses the outcome of any strategy. It uses only the volatility of the
instrument and the structure of the proposed overlay, both knowable in advance.

Method:
  A timing overlay holds the asset on some fraction of bars and cash otherwise. Its
  return difference against buy-and-hold has a standard deviation - the tracking error -
  that does not depend on whether the timing is any good. The minimum alpha detectable
  over T years is then a function of that tracking error alone.

  se(annualised difference) = tracking_error / sqrt(T)
  detectable at 95 % two-sided, 50 % power : |alpha| > 1.96 * se
  detectable at 95 % two-sided, 80 % power : |alpha| > 2.80 * se

  With N configurations searched, the best of N is inflated by selection. The Bonferroni
  bound raises the critical value to z(1 - 0.05 / (2N)), which is conservative but has
  the merit of being impossible to argue down after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats as _stats  # noqa: F401  (optional; falls back below)

SESSIONS_PER_YEAR = 252


def _z(p: float) -> float:
    """Two-sided critical value without requiring scipy at runtime."""
    try:
        from scipy.stats import norm
        return float(norm.ppf(1.0 - p / 2.0))
    except Exception:
        # Acklam's rational approximation is plenty for a gate that reports orders of
        # magnitude, and keeps this module importable without scipy.
        import math
        q = 1.0 - p / 2.0
        a = [-39.69683028665376, 220.9460984245205, -275.9285104469687,
             138.3577518672690, -30.66479806614716, 2.506628277459239]
        b = [-54.47609879822406, 161.5858368580409, -155.6989798598866,
             66.80131188771972, -13.28068155288572]
        c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838,
             -2.549732539343734, 4.374664141464968, 2.938163982698783]
        d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996,
             3.754408661907416]
        pl, ph = 0.02425, 1 - 0.02425
        if q < pl:
            t = math.sqrt(-2 * math.log(q))
            return (((((c[0]*t+c[1])*t+c[2])*t+c[3])*t+c[4])*t+c[5]) / \
                   ((((d[0]*t+d[1])*t+d[2])*t+d[3])*t+1)
        if q > ph:
            t = math.sqrt(-2 * math.log(1 - q))
            return -(((((c[0]*t+c[1])*t+c[2])*t+c[3])*t+c[4])*t+c[5]) / \
                    ((((d[0]*t+d[1])*t+d[2])*t+d[3])*t+1)
        t = q - 0.5
        r = t * t
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*t / \
               (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


@dataclass(frozen=True)
class PowerResult:
    tracking_error: float
    years_available: int | float
    n_configs: int
    z_critical: float
    se_annual: float
    min_detectable_alpha_50pct_power: float
    min_detectable_alpha_80pct_power: float
    years_needed_for_target: float | None
    target_alpha: float | None
    passes: bool
    verdict: str


def tracking_error_of_overlay(daily_returns: np.ndarray, exposure_fraction: float,
                              n_draws: int = 400, seed: int = 0) -> float:
    """Annualised tracking error of a timing overlay against buy-and-hold.

    Estimated by drawing random in/out masks at the given exposure. Randomness is the
    point: this is the tracking error a timing rule carries REGARDLESS of skill, which
    is what sets the detection threshold. A skilful rule has the same denominator as a
    worthless one; only the numerator differs.
    """
    r = np.asarray(daily_returns, dtype=float)
    r = r[np.isfinite(r)]
    if not 0.0 <= exposure_fraction <= 1.0:
        raise ValueError("exposure_fraction must be in [0, 1]")
    if exposure_fraction in (0.0, 1.0):
        # fully out or fully in: the difference is deterministic given the path
        mask = np.full(len(r), exposure_fraction)
        return float(np.std((mask - 1.0) * r, ddof=1) * np.sqrt(SESSIONS_PER_YEAR))

    rng = np.random.default_rng(seed)
    k = int(round(exposure_fraction * len(r)))
    tes = []
    for _ in range(n_draws):
        mask = np.zeros(len(r))
        mask[rng.choice(len(r), size=k, replace=False)] = 1.0
        diff = mask * r - r          # overlay minus buy-and-hold
        tes.append(np.std(diff, ddof=1))
    return float(np.mean(tes) * np.sqrt(SESSIONS_PER_YEAR))


def power_gate(tracking_error: float, years_available: float, *,
               n_configs: int = 1, target_alpha: float | None = None,
               alpha_level: float = 0.05) -> PowerResult:
    """Run the gate. `target_alpha` is the annualised excess the candidate claims."""
    if tracking_error <= 0:
        raise ValueError("tracking_error must be positive")
    if years_available <= 0:
        raise ValueError("years_available must be positive")
    if n_configs < 1:
        raise ValueError("n_configs must be at least 1")

    z = _z(alpha_level / n_configs)          # Bonferroni over the search
    se = tracking_error / np.sqrt(years_available)
    mda50 = z * se
    mda80 = (z + 0.8416) * se

    years_needed = None
    passes = False
    if target_alpha is not None:
        if target_alpha <= 0:
            raise ValueError("target_alpha must be positive")
        years_needed = float(((z + 0.8416) * tracking_error / target_alpha) ** 2)
        passes = years_needed <= years_available

    if target_alpha is None:
        verdict = (f"sample supports detecting an annualised excess of "
                   f"{mda80:.1%} or more at 80 % power, {n_configs} configuration(s) searched")
    elif passes:
        verdict = (f"PASS: detecting {target_alpha:.1%}/yr needs {years_needed:.1f} years; "
                   f"{years_available:.1f} available")
    else:
        verdict = (f"FAIL: detecting {target_alpha:.1%}/yr needs {years_needed:.1f} years "
                   f"but only {years_available:.1f} are available. Rejected without a "
                   f"backtest per selection_criteria.md appendix A.5(a).")

    return PowerResult(
        tracking_error=float(tracking_error), years_available=float(years_available),
        n_configs=int(n_configs), z_critical=float(z), se_annual=float(se),
        min_detectable_alpha_50pct_power=float(mda50),
        min_detectable_alpha_80pct_power=float(mda80),
        years_needed_for_target=years_needed, target_alpha=target_alpha,
        passes=bool(passes), verdict=verdict)


def effective_sample_size(daily_returns: np.ndarray, max_lag: int = 20) -> float:
    """Independent-equivalent observations, deflated for autocorrelation.

    156,324 bars is a large number and a small sample. This returns what the series is
    worth in independent observations, which is the number that belongs next to any
    claim about significance.
    """
    r = np.asarray(daily_returns, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    if n < 3:
        return float(n)
    r = r - r.mean()
    denom = float(np.dot(r, r))
    if denom == 0:
        return float(n)
    s = 0.0
    for lag in range(1, min(max_lag, n - 1) + 1):
        rho = float(np.dot(r[:-lag], r[lag:]) / denom)
        s += (1.0 - lag / n) * rho
    factor = 1.0 + 2.0 * s
    return float(n / factor) if factor > 0 else float(n)
