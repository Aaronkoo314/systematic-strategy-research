"""The same guarantees, checked against the real 156,324-bar QQQ file.

Synthetic tests prove the logic is self-consistent. Only the real file proves the
logic matches the data we will actually trade on. Skipped when the data has not
been pulled, so a clean checkout still runs the suite.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data.bars import (  # noqa: E402
    load_5min, REGULAR_BARS, HALF_DAY_BARS, FIRST_BAR_HM, LAST_BAR_HM, HALF_DAY_LAST_HM,
)

DATA = ROOT / "data" / "raw" / "US_QQQ_5min_raw.csv"
MANIFEST = ROOT / "data" / "intraday_manifest.json"
CALENDAR = ROOT / "data" / "us_trading_calendar.csv"

pytestmark = pytest.mark.skipif(
    not DATA.exists(), reason="run `python tools/pull_intraday.py` first")


@pytest.fixture(scope="module")
def bars():
    return load_5min(str(DATA))


def test_real_file_passes_validation(bars):
    """Constructing with validate=True already ran every check; this asserts the shape."""
    assert len(bars) == 156_324
    assert len(bars.sessions) == 2_012


def test_matches_the_pinned_manifest(bars):
    """Guards against the file being silently replaced or re-pulled with different bounds."""
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert m["bars"] == len(bars)
    assert m["sessions"] == len(bars.sessions)
    assert m["first_bar"] == bars.time_key[0]
    assert m["last_bar"] == bars.time_key[-1]
    assert m["autype"].startswith("NONE")


def test_every_session_opens_at_0935(bars):
    assert {bars.hm[s.start] for s in bars.sessions} == {FIRST_BAR_HM}


def test_session_lengths_are_only_78_or_42(bars):
    counts = {}
    for s in bars.sessions:
        counts[s.n_bars] = counts.get(s.n_bars, 0) + 1
    assert counts == {REGULAR_BARS: 1_995, HALF_DAY_BARS: 17}


def test_half_days_close_at_1300_and_full_days_at_1600(bars):
    """The defect this catches: hard-coding 16:00 as the close would hold a position
    three hours past the bell on the 17 half-days."""
    for s in bars.sessions:
        want = HALF_DAY_LAST_HM if s.is_half_day else LAST_BAR_HM
        assert bars.hm[s.end] == want, f"{s.date} ends at {bars.hm[s.end]}, expected {want}"


def test_no_session_is_missing_against_the_calendar(bars):
    res = bars.check_calendar(str(CALENDAR))
    assert res["missing"] == [], f"missing sessions: {res['missing'][:5]}"
    assert res["extra"] == [], f"sessions not in calendar: {res['extra'][:5]}"


def test_prices_are_raw_not_adjusted(bars):
    """Adjusted 2018 prices read ~172; the real level was ~185. Raw must be the latter.

    Sizing is floor(cash / price), so an adjusted series yields wrong share counts,
    wrong notionals and wrong per-share fees for the whole history.
    """
    assert 175.0 < float(bars.close[0]) < 200.0


def test_execution_never_precedes_or_equals_its_signal(bars):
    """Swept across the whole real series, not a sample."""
    n = len(bars)
    for i in range(n):
        nxt = bars.next_executable_index(i)
        if nxt is not None:
            assert nxt == i + 1
            assert bars.date[nxt] == bars.date[i]


def test_last_bar_of_every_session_has_no_executable_successor(bars):
    """No signal may fill across the overnight gap."""
    for s in bars.sessions:
        assert bars.next_executable_index(s.end) is None


def test_forced_exit_is_always_within_the_same_session(bars):
    for s in bars.sessions:
        for i in (s.start, (s.start + s.end) // 2, s.end):
            assert bars.forced_exit_index(i) == s.end
            assert bars.date[bars.forced_exit_index(i)] == s.date


def test_history_never_leaks_a_future_timestamp(bars):
    """Spot-checked at session boundaries and midpoints across the full series."""
    probes = []
    for s in bars.sessions[::200]:
        probes += [s.start, (s.start + s.end) // 2, s.end]
    for i in probes:
        h = bars.history_upto(i)
        assert h["n"] == i + 1
        assert h["time_key"][-1] == bars.time_key[i]
        if i + 1 < len(bars):
            assert bars.time_key[i + 1] not in set(h["time_key"][-3:])
