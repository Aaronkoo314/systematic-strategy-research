"""Session-aware 5-minute bar series with structural look-ahead prevention.

The central design decision: a strategy is never handed the full price array. It is
handed `history_upto(i)`, a read-only view ending at bar i. It cannot peek forward
because the future is not in the object it receives. Tests confirm the property, but
the property does not depend on the tests.

Verified conventions (docs/intraday_data.md):
  - time_key is the bar CLOSE. The first session bar is 09:35 and covers 09:30-09:35.
  - Regular session only, 09:35-16:00 ET. 78 bars normally, 42 on holiday half-days.
  - Prices are raw (AuType.NONE), so share counts and order prices are real.

Execution rule, enforced here rather than left to the strategy:
  a signal computed from bar i may fill no earlier than bar i+1, at that bar's OPEN,
  and never across a session boundary.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

REGULAR_BARS = 78          # 6.5h / 5min
HALF_DAY_BARS = 42
FIRST_BAR_HM = "09:35"
LAST_BAR_HM = "16:00"
HALF_DAY_LAST_HM = "13:00"   # US holiday early close, verified on all 17 such sessions


class LookAheadError(RuntimeError):
    """Raised when code asks for data it cannot legitimately have at decision time."""


@dataclass(frozen=True)
class Session:
    date: str
    start: int          # index of first bar, inclusive
    end: int            # index of last bar, INCLUSIVE
    n_bars: int
    is_half_day: bool

    def __contains__(self, i: int) -> bool:
        return self.start <= i <= self.end


class BarSeries:
    """Immutable 5-minute bars, indexed by session.

    Arrays are set read-only at construction; a strategy that tries to write to the
    data it was given will raise rather than silently corrupt the backtest.
    """

    def __init__(self, df: pd.DataFrame, *, validate: bool = True):
        need = {"time_key", "open", "high", "low", "close", "volume"}
        missing = need - set(df.columns)
        if missing:
            raise ValueError(f"missing columns: {sorted(missing)}")

        df = df.sort_values("time_key").reset_index(drop=True)
        self.time_key = df["time_key"].to_numpy(dtype=object)
        self.date = np.array([t[:10] for t in self.time_key], dtype=object)
        self.hm = np.array([t[11:16] for t in self.time_key], dtype=object)
        self.open = df["open"].to_numpy(dtype=float)
        self.high = df["high"].to_numpy(dtype=float)
        self.low = df["low"].to_numpy(dtype=float)
        self.close = df["close"].to_numpy(dtype=float)
        self.volume = df["volume"].to_numpy(dtype=float)

        for a in (self.open, self.high, self.low, self.close, self.volume):
            a.flags.writeable = False

        self._sessions: list[Session] = []
        self._session_of = np.empty(len(self.time_key), dtype=int)
        self._build_sessions()

        if validate:
            self.validate()

    def __len__(self) -> int:
        return len(self.time_key)

    # ---------------- sessions ----------------

    def _build_sessions(self) -> None:
        if not len(self.date):
            return
        start = 0
        for i in range(1, len(self.date) + 1):
            if i == len(self.date) or self.date[i] != self.date[start]:
                n = i - start
                s = Session(date=str(self.date[start]), start=start, end=i - 1,
                            n_bars=n, is_half_day=(n == HALF_DAY_BARS))
                self._sessions.append(s)
                self._session_of[start:i] = len(self._sessions) - 1
                start = i

    @property
    def sessions(self) -> list[Session]:
        return list(self._sessions)

    def session_of(self, i: int) -> Session:
        self._check_index(i)
        return self._sessions[int(self._session_of[i])]

    # ---------------- look-ahead-safe access ----------------

    def _check_index(self, i: int) -> None:
        if not isinstance(i, (int, np.integer)) or isinstance(i, bool):
            raise TypeError(f"index must be an int, got {type(i).__name__}")
        if i < 0 or i >= len(self.time_key):
            raise IndexError(f"index {i} out of range 0..{len(self.time_key) - 1}")

    def history_upto(self, i: int) -> dict:
        """Everything knowable at the close of bar i - and nothing else.

        Returns read-only views ending at i inclusive. There is no path from this
        object to bar i+1, which is what makes look-ahead structurally impossible
        rather than merely discouraged.
        """
        self._check_index(i)
        j = i + 1
        return {
            "time_key": self.time_key[:j],
            "open": self.open[:j],
            "high": self.high[:j],
            "low": self.low[:j],
            "close": self.close[:j],
            "volume": self.volume[:j],
            "n": j,
        }

    def next_executable_index(self, signal_i: int) -> int | None:
        """Earliest bar a signal from `signal_i` may fill on.

        Always signal_i + 1, and never across a session boundary - an intraday
        strategy that is flat overnight cannot fill a signal on the next morning's
        open, because the information is 17 hours stale and the gap is unmodelled.
        Returns None when the signal lands on the last bar of a session.
        """
        self._check_index(signal_i)
        nxt = signal_i + 1
        if nxt >= len(self.time_key):
            return None
        if self._session_of[nxt] != self._session_of[signal_i]:
            return None
        return nxt

    def fill_price(self, exec_i: int) -> float:
        """A fill happens at the OPEN of the execution bar, never its close.

        Filling at a bar's close means using the whole bar's information to trade at
        the end of it - the single easiest way to manufacture an intraday edge.
        """
        self._check_index(exec_i)
        return float(self.open[exec_i])

    # ---------------- flat-at-close ----------------

    def forced_exit_index(self, i: int) -> int:
        """Bar on which an open position must be closed. Operator chose flat overnight.

        The exit fills at the OPEN of the session's final bar (15:55 on a normal day),
        so the position is closed before the closing auction rather than at it - we
        cannot place market-on-close orders under the NORMAL/MARKET-only constraint.
        """
        return self.session_of(i).end

    def is_forced_exit_bar(self, i: int) -> bool:
        return i == self.forced_exit_index(i)

    def last_entry_signal_index(self, i: int) -> int:
        """Last bar in i's session on which a NEW entry signal may still be acted on.

        An entry from bar k fills at k+1 and must be exited at the session's final bar,
        so k+1 <= end, i.e. k <= end - 1. Signals after that are dropped rather than
        silently carried overnight.
        """
        return self.session_of(i).end - 1

    # ---------------- validation ----------------

    def validate(self) -> None:
        t = self.time_key
        if len(set(t)) != len(t):
            raise ValueError("duplicate timestamps")
        if not all(t[i] < t[i + 1] for i in range(len(t) - 1)):
            raise ValueError("timestamps are not strictly increasing")

        bad_hm = sorted({h for h in self.hm if not (FIRST_BAR_HM <= h <= LAST_BAR_HM)})
        if bad_hm:
            raise ValueError(f"bars outside the regular session: {bad_hm[:5]}")

        counts = {s.n_bars for s in self._sessions}
        unexpected = counts - {REGULAR_BARS, HALF_DAY_BARS}
        if unexpected:
            offenders = [(s.date, s.n_bars) for s in self._sessions
                         if s.n_bars in unexpected][:5]
            raise ValueError(f"unexpected bars-per-session {sorted(unexpected)}: {offenders}")

        for s in self._sessions:
            if self.hm[s.start] != FIRST_BAR_HM:
                raise ValueError(f"{s.date} starts at {self.hm[s.start]}, not {FIRST_BAR_HM}")
            # Half-days close early. Verified on the real series: all 2012 sessions open
            # at 09:35; 1995 close at 16:00 and 17 at 13:00. Hard-coding 16:00 as the
            # close would leave a position open for three hours past the bell on those
            # 17 days - which is exactly why forced_exit_index is index-based, not
            # clock-based.
            want_close = HALF_DAY_LAST_HM if s.is_half_day else LAST_BAR_HM
            if self.hm[s.end] != want_close:
                raise ValueError(
                    f"{s.date} has {s.n_bars} bars and ends at {self.hm[s.end]}, "
                    f"expected {want_close}")

        if np.any(self.high < self.low):
            raise ValueError("high < low on some bars")
        if np.any((self.open > self.high) | (self.open < self.low)):
            raise ValueError("open outside [low, high] on some bars")
        if np.any((self.close > self.high) | (self.close < self.low)):
            raise ValueError("close outside [low, high] on some bars")
        if np.any(self.close <= 0) or np.any(self.open <= 0):
            raise ValueError("non-positive prices")

    def check_calendar(self, calendar_csv: str) -> dict:
        """Compare session dates against the derived trading calendar."""
        cal = set(pd.read_csv(calendar_csv)["date"].astype(str))
        have = {s.date for s in self._sessions}
        lo, hi = min(have), max(have)
        expected = {d for d in cal if lo <= d <= hi}
        return {"expected": len(expected), "have": len(have),
                "missing": sorted(expected - have), "extra": sorted(have - cal)}


def load_5min(path: str, *, validate: bool = True) -> BarSeries:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found - run `python tools/pull_intraday.py` first")
    return BarSeries(pd.read_csv(path), validate=validate)
