"""Look-ahead prevention, session handling and flat-at-close, on synthetic bars.

Synthetic data is used deliberately: it lets a session be malformed on purpose to
confirm validation actually rejects it. Tests against the real file live in
test_bars_real.py and are skipped when the data has not been pulled.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.data.bars import (  # noqa: E402
    BarSeries, Session, REGULAR_BARS, HALF_DAY_BARS,
    FIRST_BAR_HM, LAST_BAR_HM, HALF_DAY_LAST_HM,
)

HM = [f"{9 + (35 + 5 * k) // 60:02d}:{(35 + 5 * k) % 60:02d}" for k in range(REGULAR_BARS)]
assert HM[0] == "09:35" and HM[-1] == "16:00"


def make_session(date: str, n_bars: int = REGULAR_BARS, base: float = 100.0) -> pd.DataFrame:
    # Half-days run 09:35..13:00, i.e. the FIRST 42 slots, not the last.
    hm = HM[:n_bars]
    px = base + np.arange(n_bars, dtype=float) * 0.1
    return pd.DataFrame({
        "time_key": [f"{date} {h}:00" for h in hm],
        "open": px, "close": px + 0.05,
        "high": px + 0.2, "low": px - 0.2,
        "volume": np.full(n_bars, 1000.0),
    })


def make_series(dates=("2024-01-02", "2024-01-03"), half_days=()) -> BarSeries:
    frames = [make_session(d, HALF_DAY_BARS if d in half_days else REGULAR_BARS,
                           base=100.0 + 10 * i)
              for i, d in enumerate(dates)]
    return BarSeries(pd.concat(frames, ignore_index=True))


# ---------------- structure ----------------

def test_sessions_are_detected():
    s = make_series()
    assert len(s.sessions) == 2
    assert [x.n_bars for x in s.sessions] == [REGULAR_BARS, REGULAR_BARS]
    assert s.sessions[0].start == 0 and s.sessions[0].end == REGULAR_BARS - 1


def test_half_day_session_accepted_and_flagged():
    s = make_series(dates=("2024-11-29",), half_days=("2024-11-29",))
    assert s.sessions[0].n_bars == HALF_DAY_BARS
    assert s.sessions[0].is_half_day is True
    assert s.hm[s.sessions[0].start] == FIRST_BAR_HM
    assert s.hm[s.sessions[0].end] == HALF_DAY_LAST_HM


def test_half_day_ending_at_the_regular_close_is_rejected():
    """42 bars running 12:35..16:00 are missing bars, not an early close.

    The start check fires first here ("starts at 12:35"), which is an equally valid
    reason to reject. What matters is that a malformed session cannot be loaded.
    """
    df = make_session("2024-11-29", REGULAR_BARS)
    df = df.iloc[REGULAR_BARS - HALF_DAY_BARS:].reset_index(drop=True)  # 12:35..16:00
    with pytest.raises(ValueError, match="09:35|13:00"):
        BarSeries(df)


def test_half_day_with_a_late_final_bar_is_rejected():
    """42 bars ending at 16:00 is a FULL day with bars missing, not an early close.

    Half-day status is now decided by the closing time rather than the bar count, so
    this is correctly reported as "closes at 16:00 but has 42 bars, expected 78".
    Counting bars could not tell a genuine early close from an afternoon data outage,
    and getting that wrong moves the close by three hours."""
    df = make_session("2024-11-29", HALF_DAY_BARS)
    df.loc[HALF_DAY_BARS - 1, "time_key"] = "2024-11-29 16:00:00"
    with pytest.raises(ValueError, match="expected 78|expected 13:00"):
        BarSeries(df)


def test_unexpected_bar_count_rejected():
    """A session with a wrong number of bars is a data defect, not something to smooth over."""
    bad = make_session("2024-01-02", REGULAR_BARS).iloc[:50]
    with pytest.raises(ValueError, match="expected 78|ends at"):
        BarSeries(bad)


def test_duplicate_timestamps_rejected():
    df = pd.concat([make_session("2024-01-02")] * 2, ignore_index=True)
    with pytest.raises(ValueError):
        BarSeries(df)


def test_bar_outside_session_window_rejected():
    df = make_session("2024-01-02")
    df.loc[0, "time_key"] = "2024-01-02 08:00:00"   # pre-market
    with pytest.raises(ValueError):
        BarSeries(df)


def test_inconsistent_ohlc_rejected():
    df = make_session("2024-01-02")
    df.loc[10, "high"] = df.loc[10, "low"] - 1.0
    with pytest.raises(ValueError):
        BarSeries(df)


# ---------------- look-ahead prevention ----------------

def test_history_upto_ends_at_i():
    s = make_series()
    for i in (0, 5, 77, 100):
        h = s.history_upto(i)
        assert h["n"] == i + 1
        assert len(h["close"]) == i + 1
        assert h["time_key"][-1] == s.time_key[i]


def test_history_upto_contains_no_future_bar():
    """The decisive property: the future is absent from the object, not merely unused."""
    s = make_series()
    i = 40
    h = s.history_upto(i)
    future = set(s.time_key[i + 1:])
    assert not (set(h["time_key"]) & future)


def test_history_is_read_only():
    """A strategy must not be able to mutate the price series it was handed."""
    s = make_series()
    h = s.history_upto(30)
    with pytest.raises(ValueError):
        h["close"][0] = 1e9


def test_cheating_strategy_cannot_see_the_bar_it_trades_on():
    """Simulates the classic fake edge: look at bar i+1's close, then 'predict' it.

    With history_upto there is no i+1 to look at, so the cheat cannot even be written.
    """
    s = make_series()
    i = 20
    h = s.history_upto(i)
    exec_i = s.next_executable_index(i)
    assert exec_i == i + 1
    assert len(h["close"]) == i + 1          # cannot index h['close'][exec_i]
    with pytest.raises(IndexError):
        _ = h["close"][exec_i]


def test_execution_is_strictly_after_signal():
    s = make_series()
    for i in range(0, len(s) - 1):
        nxt = s.next_executable_index(i)
        if nxt is not None:
            assert nxt > i


def test_no_fill_across_session_boundary():
    """A signal on the last bar of a session must not fill on the next morning."""
    s = make_series()
    last = s.sessions[0].end
    assert s.next_executable_index(last) is None


def test_fill_price_is_the_open_not_the_close():
    s = make_series()
    i = 12
    exec_i = s.next_executable_index(i)
    assert s.fill_price(i, exec_i) == pytest.approx(s.open[exec_i])
    assert s.fill_price(i, exec_i) != pytest.approx(s.close[exec_i])


def test_fill_price_rejects_an_index_that_is_not_the_legal_successor():
    """fill_price previously took one index and was uncoupled from the execution rule,
    so enforced-in-code was only a comment."""
    from src.data.bars import LookAheadError
    s = make_series()
    i = 12
    for bad in (i, i + 5, i - 1):
        with pytest.raises(LookAheadError):
            s.fill_price(i, bad)


def test_fill_price_refuses_a_signal_with_no_legal_successor():
    from src.data.bars import LookAheadError
    s = make_series()
    last = s.sessions[0].end
    with pytest.raises(LookAheadError):
        s.fill_price(last, last + 1)


def test_zero_volume_bar_is_not_fillable():
    """Seven such bars exist in the real series, all March 2020 halts."""
    from src.data.bars import NotFillableError
    df = make_session("2024-01-02")
    df.loc[13, "volume"] = 0.0
    s = BarSeries(df)
    assert s.is_fillable(13) is False
    assert s.is_fillable(12) is True
    with pytest.raises(NotFillableError):
        s.fill_price(12, 13)


# ---------------- flat at close ----------------

def test_forced_exit_is_last_bar_of_session():
    s = make_series()
    for sess in s.sessions:
        assert s.forced_exit_index(sess.start) == sess.end
        assert s.is_forced_exit_bar(sess.end) is True
        assert s.is_forced_exit_bar(sess.start) is False


def test_last_entry_signal_leaves_room_to_exit():
    """An entry must fill at k+1 and still be exitable at the session's final bar."""
    s = make_series()
    sess = s.sessions[0]
    k = s.last_entry_signal_index(sess.start)
    assert k == sess.end - 1
    fill = s.next_executable_index(k)
    assert fill == sess.end                  # fills on the final bar...
    assert s.forced_exit_index(fill) == sess.end   # ...where it is also forced flat


def test_forced_exit_on_half_day_uses_that_session_end():
    s = make_series(dates=("2024-11-29", "2024-11-30"), half_days=("2024-11-29",))
    half = s.sessions[0]
    assert half.n_bars == HALF_DAY_BARS
    assert s.forced_exit_index(half.start) == half.end
    assert s.next_executable_index(half.end) is None


# ---------------- index hygiene ----------------

def test_bad_index_types_and_ranges_rejected():
    s = make_series()
    for bad in (-1, len(s), len(s) + 10):
        with pytest.raises(IndexError):
            s.history_upto(bad)
    for bad in (1.0, "3", True):
        with pytest.raises(TypeError):
            s.history_upto(bad)


def test_session_membership():
    s = make_series()
    sess = s.sessions[0]
    assert sess.start in sess
    assert sess.end in sess
    assert (sess.end + 1) not in sess
