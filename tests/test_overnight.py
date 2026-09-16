"""Overnight mode, chosen by the operator on 2026-09-16.

The flat-at-close rule was not a detail - it confined the strategy to the intraday
segment, which carried 5.92 %/yr of QQQ's 18.63 %/yr drift over 2018-2026. Allowing
overnight restores the other 12.00 %/yr and introduces gap risk and distributions.

These tests pin the two modes apart so neither can leak into the other silently.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data.bars import BarSeries, REGULAR_BARS  # noqa: E402

HM = [f"{9 + (35 + 5 * k) // 60:02d}:{(35 + 5 * k) % 60:02d}" for k in range(REGULAR_BARS)]


def make(n_days: int = 3, allow_overnight: bool = False) -> BarSeries:
    frames = []
    for d in range(n_days):
        date = f"2024-01-{2 + d:02d}"
        px = 100.0 + d * 10 + np.arange(REGULAR_BARS, dtype=float) * 0.1
        frames.append(pd.DataFrame({
            "time_key": [f"{date} {h}:00" for h in HM],
            "open": px, "close": px + 0.05, "high": px + 0.2, "low": px - 0.2,
            "volume": np.full(REGULAR_BARS, 1000.0),
        }))
    return BarSeries(pd.concat(frames, ignore_index=True), allow_overnight=allow_overnight)


def test_default_is_still_flat_at_close():
    """The safer mode stays the default; overnight must be asked for explicitly."""
    assert make().allow_overnight is False


def test_flat_mode_drops_a_signal_on_the_last_bar():
    s = make(allow_overnight=False)
    assert s.next_executable_index(s.sessions[0].end) is None


def test_overnight_mode_fills_on_the_next_session_open():
    s = make(allow_overnight=True)
    last = s.sessions[0].end
    nxt = s.next_executable_index(last)
    assert nxt == last + 1
    assert s.date[nxt] != s.date[last]
    assert s.fill_price(nxt) == pytest.approx(s.open[nxt])


def test_overnight_fill_is_flagged_as_such():
    """A gap fill must be visible to the engine, not indistinguishable from a 5-min fill."""
    s = make(allow_overnight=True)
    last = s.sessions[0].end
    assert s.is_overnight_fill(last, last + 1) is True
    mid = s.sessions[0].start + 10
    assert s.is_overnight_fill(mid, mid + 1) is False


def test_end_of_series_still_returns_none_in_both_modes():
    for flag in (False, True):
        s = make(allow_overnight=flag)
        assert s.next_executable_index(len(s) - 1) is None


def test_execution_is_still_strictly_after_the_signal_in_overnight_mode():
    """Relaxing the session boundary must not relax the look-ahead rule."""
    s = make(allow_overnight=True)
    for i in range(len(s) - 1):
        nxt = s.next_executable_index(i)
        assert nxt is None or nxt == i + 1


def test_flat_at_close_helpers_raise_in_overnight_mode():
    """They encode a rule that no longer applies; returning a number would be a
    silently wrong answer rather than an error."""
    s = make(allow_overnight=True)
    with pytest.raises(RuntimeError, match="allow_overnight"):
        s.forced_exit_index(0)
    with pytest.raises(RuntimeError, match="allow_overnight"):
        s.last_entry_signal_index(0)


def test_flat_at_close_helpers_still_work_in_flat_mode():
    s = make(allow_overnight=False)
    assert s.forced_exit_index(0) == s.sessions[0].end
    assert s.last_entry_signal_index(0) == s.sessions[0].end - 1


def test_look_ahead_guarantee_holds_in_overnight_mode():
    """The memory-ownership fix must not be mode-dependent."""
    s = make(allow_overnight=True)
    h = s.history_upto(50)
    for f in ("time_key", "open", "high", "low", "close", "volume"):
        assert h[f].base is None
        assert h[f].flags.owndata
    assert len(h["close"]) == 51
