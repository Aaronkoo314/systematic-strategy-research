"""Session-aware 5-minute bar series with structural look-ahead prevention.

The central design decision: a strategy is never handed the full price array. It is
handed `history_upto(i)`, an OWNED read-only COPY ending at bar i, so the future is
not reachable from the object it receives.

This was originally implemented with numpy slices, which was wrong and is worth
recording. A slice shares its parent's buffer, so `arr[:j].base` exposed the entire
156,324-bar block - and `as_strided` read straight past the slice end into real future
prices. An adversarial review built an oracle strategy on that hole and produced a
631x annual return while passing all 49 tests, because the tests only checked that the
returned timestamps did not intersect the future and never touched `.base`.

The lesson: `writeable=False` prevents accidental writes. It was never a look-ahead
boundary, and treating it as one gave false assurance. Ownership is the boundary -
every array handed out must satisfy `base is None` and `flags.owndata`.

Verified conventions (docs/intraday_data.md):
  - time_key is the bar CLOSE. The first session bar is 09:35 and covers 09:30-09:35.
  - Regular session only, 09:35-16:00 ET. 78 bars normally, 42 on holiday half-days.
  - Prices are raw (AuType.NONE), so share counts and order prices are real.

Execution rule, enforced here rather than left to the strategy:
  a signal computed from bar i may fill no earlier than bar i+1, at that bar's OPEN.

Whether a fill may cross a session boundary is a REGIME decision, not a detail:
  allow_overnight=False - flat at the close. A signal on the last bar of a session is
    dropped; nothing is carried overnight. Confines the strategy to the intraday
    segment, which over 2018-2026 carried 5.92 %/yr of QQQ's 18.63 %/yr total drift.
  allow_overnight=True  - positions may be held across the close. The fill on the next
    session's first bar IS an overnight gap fill, and is reported as such, because the
    17-hour information gap and the gap risk are real and must not be invisible.
    Operator chose this on 2026-09-16. Consequence: a position held across an ex-date
    receives a distribution, which must be booked as a cash event - see
    tools/pull_dividends.py. The flat-at-close helpers raise in this mode rather than
    silently returning a number that no longer means anything.
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

    def __init__(self, df: pd.DataFrame, *, validate: bool = True,
                 allow_overnight: bool = False):
        self.allow_overnight = bool(allow_overnight)
        need = {"time_key", "open", "high", "low", "close", "volume"}
        missing = need - set(df.columns)
        if missing:
            raise ValueError(f"missing columns: {sorted(missing)}")

        df = df.sort_values("time_key").reset_index(drop=True)

        # copy=True is load-bearing, not defensive style. to_numpy() does NOT copy when
        # the dtype already matches, so these would otherwise be views into one pandas
        # block and `self.close.base` would be the whole (6, N) array.
        self.time_key = np.array(df["time_key"].to_numpy(dtype=object), dtype=object, copy=True)
        self.date = np.array([t[:10] for t in self.time_key], dtype=object)
        self.hm = np.array([t[11:16] for t in self.time_key], dtype=object)
        self.open = np.array(df["open"].to_numpy(dtype=float), dtype=float, copy=True)
        self.high = np.array(df["high"].to_numpy(dtype=float), dtype=float, copy=True)
        self.low = np.array(df["low"].to_numpy(dtype=float), dtype=float, copy=True)
        self.close = np.array(df["close"].to_numpy(dtype=float), dtype=float, copy=True)
        self.volume = np.array(df["volume"].to_numpy(dtype=float), dtype=float, copy=True)

        for name, a in self._arrays().items():
            if a.base is not None:
                raise RuntimeError(
                    f"{name} does not own its memory - it would leak the full series")
            a.flags.writeable = False

        self._sessions: list[Session] = []
        self._session_of = np.empty(len(self.time_key), dtype=int)
        self._build_sessions()
        self._session_of.flags.writeable = False   # was mutable; writing it corrupted lookups

        if validate:
            self.validate()

    def _arrays(self) -> dict:
        """Every array handed out or held. time_key/date/hm were originally left
        writeable, which let a strategy write through a 'read-only' view into the
        master series."""
        return {"time_key": self.time_key, "date": self.date, "hm": self.hm,
                "open": self.open, "high": self.high, "low": self.low,
                "close": self.close, "volume": self.volume}

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

        Returns OWNED read-only copies ending at i inclusive. Copies, not slices: a
        slice shares the parent buffer, so `.base` and `as_strided` both reach real
        future prices. Each returned array satisfies `base is None` and `owndata`,
        which is what actually makes the future unreachable.

        The copy costs O(i) per call. That is the price of the guarantee; a caller that
        needs speed should hold its own incremental state rather than be handed a view.
        """
        self._check_index(i)
        j = i + 1
        out = {}
        for name, a in self._arrays().items():
            c = a[:j].copy()
            assert c.base is None and c.flags.owndata, f"{name} copy still shares memory"
            c.flags.writeable = False
            out[name] = c
        out["n"] = j
        return out

    def next_executable_index(self, signal_i: int) -> int | None:
        """Earliest bar a signal from `signal_i` may fill on. Always signal_i + 1.

        When allow_overnight is False a signal on a session's last bar returns None -
        it is dropped rather than carried. When True the next session's first bar is
        returned, and `is_overnight_fill` reports that the fill crosses the gap.
        Returns None at the end of the series in either mode.
        """
        self._check_index(signal_i)
        nxt = signal_i + 1
        if nxt >= len(self.time_key):
            return None
        if not self.allow_overnight and self._session_of[nxt] != self._session_of[signal_i]:
            return None
        return nxt

    def is_overnight_fill(self, signal_i: int, exec_i: int) -> bool:
        """True when a fill crosses the close. Such fills carry gap risk and 17-hour-old
        information; the engine must charge gap slippage and report them separately
        rather than treating them as ordinary five-minute fills."""
        self._check_index(signal_i)
        self._check_index(exec_i)
        return bool(self._session_of[exec_i] != self._session_of[signal_i])

    def fill_price(self, exec_i: int) -> float:
        """A fill happens at the OPEN of the execution bar, never its close.

        Filling at a bar's close means using the whole bar's information to trade at
        the end of it - the single easiest way to manufacture an intraday edge.
        """
        self._check_index(exec_i)
        return float(self.open[exec_i])

    # ---------------- flat-at-close ----------------

    def _require_flat_overnight(self, what: str) -> None:
        if self.allow_overnight:
            raise RuntimeError(
                f"{what} encodes the flat-at-close rule and is meaningless when "
                f"allow_overnight=True; the engine must manage exits explicitly")

    def forced_exit_index(self, i: int) -> int:
        """Bar on which an open position must be closed, in flat-at-close mode only.

        The exit fills at the OPEN of the session's final bar (15:55 on a normal day),
        so the position is closed before the closing auction rather than at it - we
        cannot place market-on-close orders under the NORMAL/MARKET-only constraint.
        """
        self._require_flat_overnight("forced_exit_index")
        return self.session_of(i).end

    def is_forced_exit_bar(self, i: int) -> bool:
        return i == self.forced_exit_index(i)

    def last_entry_signal_index(self, i: int) -> int:
        """Last bar in i's session on which a NEW entry signal may still be acted on.

        An entry from bar k fills at k+1 and must be exited at the session's final bar,
        so k+1 <= end, i.e. k <= end - 1. Signals after that are dropped rather than
        silently carried overnight.
        """
        self._require_flat_overnight("last_entry_signal_index")
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


def load_5min(path: str, *, validate: bool = True,
              allow_overnight: bool = False) -> BarSeries:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found - run `python tools/pull_intraday.py` first")
    return BarSeries(pd.read_csv(path), validate=validate, allow_overnight=allow_overnight)
