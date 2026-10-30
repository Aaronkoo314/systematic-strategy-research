"""Bootstrap stress test of a trade record: how much of the result was the ORDER of
the trades?

Ported from the first-phase framework (optimization/robustness.py) with the two
limitations that version recorded now fixed rather than footnoted:

  1. The old version compounded each round trip's PRICE return at full NAV, so a trade
     taken at 50 % exposure was simulated as if taken at 100 %. Here a trade's return is
     measured ON NAV: net P&L after fees divided by the portfolio NAV at the bar the
     entry filled (`returns_on_nav`). Compounding those is faithful to what the account
     actually did.
  2. The old version resampled trades independently, which destroys volatility
     clustering - losing trades arrive in runs. `block` > 1 resamples circular blocks
     of consecutive trades, which keeps short-range dependence. Both are available; a
     result should be shown under both.

What remains optimistic, stated so it is visible:
  - resampling the trades that happened cannot produce a trade that did not. A sample
    with no 2008 yields no 2008 paths. This is a test of path-ordering luck, not a
    test of regime coverage; `power.py` is where sample length is confronted.
  - fees are inside each trade's net P&L, but a resampled sequence does not re-run the
    risk gate, so a halt that would have fired on a bad run is not simulated.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MonteCarloSummary:
    n_trades: int
    n_paths: int
    block: int
    historical_terminal_return: float
    historical_max_drawdown: float
    probability_of_loss: float
    terminal_return_p05: float
    terminal_return_p50: float
    terminal_return_p95: float
    max_drawdown_p05: float          # the 5th percentile, i.e. the BAD tail
    max_drawdown_p50: float
    historical_percentile: float     # where the actual path sits among the simulated

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__annotations__}


def returns_on_nav(trades: pd.DataFrame, equity: pd.DataFrame) -> np.ndarray:
    """Per-round-trip return on portfolio NAV at the entry bar, net of fees.

    `trades` is `BacktestResult.trades` (FIFO round trips, columns entry_bar, net_pnl);
    `equity` is `BacktestResult.equity` (one row per bar, columns bar, nav). Several
    round trips can share an entry bar when one sell closes part of a lot; each is
    divided by the same NAV, so they add up to the lot's contribution.
    """
    if trades is None or len(trades) == 0:
        return np.array([], dtype=float)
    need = {"entry_bar", "net_pnl"}
    if not need.issubset(trades.columns):
        raise ValueError(f"trades needs columns {sorted(need)}")
    if equity["bar"].duplicated().any():
        raise ValueError("equity has duplicate bars - pass one run's equity, not a "
                         "concatenation of overlapping windows")
    nav_at = pd.Series(equity["nav"].to_numpy(), index=equity["bar"].to_numpy())
    missing = set(trades["entry_bar"]) - set(nav_at.index)
    if missing:
        raise ValueError(f"no equity row for entry bars {sorted(missing)[:5]}")
    nav = nav_at.loc[trades["entry_bar"].to_numpy()].to_numpy(dtype=float)
    if np.any(nav <= 0):
        raise ValueError("NAV at entry must be positive")
    return trades["net_pnl"].to_numpy(dtype=float) / nav


def _path_stats(r: np.ndarray) -> tuple[float, float]:
    curve = np.cumprod(1.0 + r)
    hwm = np.maximum.accumulate(curve)
    return float(curve[-1] - 1.0), float(np.min(curve / hwm - 1.0))


def bootstrap(returns: np.ndarray, *, n_paths: int = 1000, seed: int = 0,
              block: int = 1) -> pd.DataFrame:
    """Resample the sequence with replacement, `n_paths` times, same length.

    block=1 is the classic i.i.d. trade bootstrap. block=k draws circular blocks of k
    consecutive trades (the sequence wraps), which preserves dependence up to lag k-1.
    With block equal to the number of trades every path is a rotation of the original
    and the terminal return is the historical one on every path.
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    if n == 0:
        return pd.DataFrame(columns=["path", "terminal_return", "max_drawdown"])
    if n_paths < 1:
        raise ValueError("n_paths must be positive")
    if block < 1 or block > n:
        raise ValueError(f"block must be in 1..{n}")
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_paths):
        if block == 1:
            s = rng.choice(r, size=n, replace=True)
        else:
            starts = rng.integers(0, n, size=int(np.ceil(n / block)))
            idx = (starts[:, None] + np.arange(block)[None, :]).ravel()[:n] % n
            s = r[idx]
        term, dd = _path_stats(s)
        rows.append({"path": p, "terminal_return": term, "max_drawdown": dd})
    return pd.DataFrame(rows)


def summarise(returns: np.ndarray, paths: pd.DataFrame, *, block: int = 1) -> MonteCarloSummary:
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) == 0 or len(paths) == 0:
        raise ValueError("nothing to summarise")
    h_term, h_dd = _path_stats(r)
    t = paths["terminal_return"].to_numpy()
    d = paths["max_drawdown"].to_numpy()
    return MonteCarloSummary(
        n_trades=int(len(r)), n_paths=int(len(paths)), block=int(block),
        historical_terminal_return=h_term, historical_max_drawdown=h_dd,
        probability_of_loss=float(np.mean(t < 0.0)),
        terminal_return_p05=float(np.quantile(t, 0.05)),
        terminal_return_p50=float(np.quantile(t, 0.50)),
        terminal_return_p95=float(np.quantile(t, 0.95)),
        max_drawdown_p05=float(np.quantile(d, 0.05)),
        max_drawdown_p50=float(np.quantile(d, 0.50)),
        historical_percentile=float(np.mean(t <= h_term)))


def run(trades: pd.DataFrame, equity: pd.DataFrame, *, n_paths: int = 1000,
        seed: int = 0, block: int = 1) -> tuple[pd.DataFrame, MonteCarloSummary]:
    """Convenience: trades + equity -> (paths, summary)."""
    r = returns_on_nav(trades, equity)
    if len(r) == 0:
        raise ValueError("no round trips to resample")
    paths = bootstrap(r, n_paths=n_paths, seed=seed, block=block)
    return paths, summarise(r, paths, block=block)
