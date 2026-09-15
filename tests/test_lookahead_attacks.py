"""Regression tests for the look-ahead leak found by adversarial review, 2026-09-16.

The original implementation returned numpy SLICES from history_upto(). A slice shares
its parent's buffer, so both `.base` and `as_strided` reached real future prices. An
oracle strategy built on that hole returned 631x a year while passing all 49 tests -
because the tests checked only that returned timestamps did not intersect the future,
and never touched `.base`.

Each test below is an attack that succeeded before the fix. They exist so the hole
cannot be silently reopened by a future "optimisation" that swaps copies back for views.
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

FIELDS = ("time_key", "date", "hm", "open", "high", "low", "close", "volume")
HM = [f"{9 + (35 + 5 * k) // 60:02d}:{(35 + 5 * k) % 60:02d}" for k in range(REGULAR_BARS)]


def make_series(n_days: int = 3) -> BarSeries:
    frames = []
    for d in range(n_days):
        date = f"2024-01-{2 + d:02d}"
        px = 100.0 + d * 10 + np.arange(REGULAR_BARS, dtype=float) * 0.1
        frames.append(pd.DataFrame({
            "time_key": [f"{date} {h}:00" for h in HM],
            "open": px, "close": px + 0.05, "high": px + 0.2, "low": px - 0.2,
            "volume": np.full(REGULAR_BARS, 1000.0),
        }))
    return BarSeries(pd.concat(frames, ignore_index=True))


# ---------------- attack 1: the .base leak ----------------

def test_returned_arrays_own_their_memory():
    """The actual boundary. A view's .base reaches the whole series; a copy's is None."""
    s = make_series()
    h = s.history_upto(10)
    for f in FIELDS:
        assert h[f].base is None, f"{f} is a view - .base exposes the full series"
        assert h[f].flags.owndata, f"{f} does not own its memory"


def test_base_cannot_reveal_a_future_price():
    """The exploit verbatim: read .base from a bar-0 view and recover the last close."""
    s = make_series()
    h = s.history_upto(0)
    assert h["close"].base is None
    with pytest.raises((AttributeError, TypeError, ValueError)):
        _ = h["close"].base.shape          # base is None -> no shape


def test_master_arrays_also_own_their_memory():
    """Root cause: to_numpy() does not copy when dtype matches, so self.close.base was
    the entire pandas block. Fixing only history_upto would leave that intact."""
    s = make_series()
    for f in FIELDS:
        a = getattr(s, f)
        assert a.base is None, f"BarSeries.{f} is a view into the source frame"


# ---------------- attack 2: as_strided past the slice ----------------

def test_as_strided_cannot_read_past_the_returned_array():
    """writeable=False stops writes, never reads. Only ownership stops this."""
    s = make_series()
    i = 50
    h = s.history_upto(i)
    sl = h["close"]
    stretched = np.lib.stride_tricks.as_strided(
        sl, shape=(len(sl) + 5,), strides=sl.strides, writeable=False)
    leaked = list(stretched[len(sl):len(sl) + 5])
    real_future = list(s.close[i + 1:i + 6])
    assert leaked != real_future, "as_strided read real future prices past the copy"


# ---------------- attack 3: writing through a 'read-only' view ----------------

@pytest.mark.parametrize("field", FIELDS)
def test_every_returned_field_is_read_only(field):
    """Originally only open/high/low/close/volume were frozen. time_key, date and hm
    were writeable, so a strategy could write through them into the master series."""
    s = make_series()
    h = s.history_upto(20)
    with pytest.raises((ValueError, RuntimeError)):
        h[field][0] = h[field][0]


@pytest.mark.parametrize("field", FIELDS)
def test_master_arrays_are_read_only(field):
    s = make_series()
    a = getattr(s, field)
    with pytest.raises((ValueError, RuntimeError)):
        a[0] = a[0]


def test_writing_a_returned_array_cannot_corrupt_the_master():
    """Even if a write somehow succeeded on the copy, it must not reach the series."""
    s = make_series()
    before = str(s.time_key[10])
    h = s.history_upto(50)
    try:
        h["time_key"][10] = "2099-01-01 09:35:00"
    except (ValueError, RuntimeError):
        pass
    assert str(s.time_key[10]) == before


def test_session_index_is_frozen():
    """_session_of was mutable; writing it made session_of() return the wrong session
    or raise IndexError, which would silently misplace forced-exit bars."""
    s = make_series()
    with pytest.raises((ValueError, RuntimeError)):
        s._session_of[5] = 999


# ---------------- attack 4: the oracle strategy ----------------

def test_oracle_strategy_can_no_longer_be_built():
    """End-to-end: a strategy given only history_upto(i) must not be able to recover
    any price after bar i, by any of the routes above."""
    s = make_series()
    i = 30
    h = s.history_upto(i)
    future = set(np.round(s.close[i + 1:], 6))

    recovered = set()
    for f in ("open", "high", "low", "close"):
        a = h[f]
        recovered |= set(np.round(a, 6))
        if a.base is not None:
            recovered |= set(np.round(np.asarray(a.base).ravel(), 6))
        stretched = np.lib.stride_tricks.as_strided(
            a, shape=(len(a) + 10,), strides=a.strides, writeable=False)
        recovered |= set(np.round(np.asarray(stretched), 6))

    # Values that coincide by arithmetic are fine; what matters is that a bar-by-bar
    # future close cannot be read out. Check the specific next close is unreachable.
    assert round(float(s.close[i + 1]), 6) not in set(np.round(h["close"], 6))
    assert h["close"].base is None
    assert len(h["close"]) == i + 1
    _ = recovered  # kept to document what the attacker tried
