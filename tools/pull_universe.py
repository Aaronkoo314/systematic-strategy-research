"""Pull 5-minute RAW bars for the V4 universe, in the order frozen by the preregistration.

The universe and its ORDER come from docs/preregistration_v4.md section 2 and are
reproduced here verbatim. Symbols are pulled front to back. If the history-candle quota
runs out, whatever remains is dropped from the END of that fixed order - never by what the
data turns out to show. A truncated pull is recorded as truncated in the manifest so the
result can never be read as if the whole universe had been covered.

RAW, not adjusted, for the reason given in tools/pull_intraday.py: forward adjustment
rescales the price level, and position sizing is floor(cash / price), so adjusted prices
produce historically wrong share counts, notionals and per-share fees.

Because the V4 rule HOLDS OVERNIGHT and therefore across ex-dividend dates, raw prices
alone are not sufficient to measure the rule against buy-and-hold: the holder receives
distributions and the raw series does not show them. Distributions are pulled separately
by tools/pull_dividends.py and must be applied as cash events on ex-dates. This script
pulls prices only and says so; it does not silently leave the gap unmarked.

Read-only. Costs history-candle quota per symbol not fetched recently.
Usage: python tools/pull_universe.py [--dry-run]
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import moomoo as mm
import pandas as pd

HOST, PORT = "127.0.0.1", 11111
START, END = "2018-09-10", "2026-09-12"
KTYPE, KNAME = mm.KLType.K_5M, "5min"

# docs/preregistration_v4.md section 2, frozen order. Dropping happens from the END only.
UNIVERSE = [
    # equity sectors - SPDR Select Sector family, all eleven
    "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY",
    # broad and international equity
    "SPY", "IWM", "DIA", "EFA", "EEM",
    # non-equity
    "TLT", "IEF", "LQD", "HYG", "GLD", "SLV", "USO",
]
EQUITY_BLOCK = set(UNIVERSE[:16])

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
MANIFEST = os.path.join(ROOT, "data", "universe_manifest.json")

DRY = "--dry-run" in sys.argv


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pull_one(q, code):
    """All 5-minute bars for one symbol. Returns (DataFrame, error_or_None)."""
    frames, key, pages = [], None, 0
    while True:
        ret, df, key = q.request_history_kline(
            code, start=START, end=END, ktype=KTYPE, autype=mm.AuType.NONE,
            max_count=1000, page_req_key=key)
        if ret != mm.RET_OK:
            return (pd.concat(frames, ignore_index=True) if frames else None), str(df)
        frames.append(df)
        pages += 1
        if key is None:
            break
    if not frames:
        return None, "no data returned"
    bars = pd.concat(frames, ignore_index=True)
    return bars, None


q = mm.OpenQuoteContext(host=HOST, port=PORT)

ret, quota = q.get_history_kl_quota(get_detail=False)
print("=" * 92)
print("V4 UNIVERSE PULL - 5-minute RAW bars, frozen order from preregistration section 2")
print(f"{START} .. {END}   {len(UNIVERSE)} symbols")
print("=" * 92)
print(f"history-candle quota: {quota if ret == mm.RET_OK else 'UNAVAILABLE - ' + str(quota)}")
print()

if DRY:
    print("--dry-run: quota checked, nothing pulled.")
    q.close()
    sys.exit(0)

os.makedirs(RAW, exist_ok=True)
records, failed = [], []

for i, sym in enumerate(UNIVERSE):
    code = f"US.{sym}"
    bars, err = pull_one(q, code)
    if err is not None or bars is None or not len(bars):
        print(f"  [{i + 1:>2}/{len(UNIVERSE)}] {sym:<5} FAILED  {str(err)[:60]}")
        failed.append({"symbol": sym, "error": str(err)[:200],
                       "position_in_frozen_order": i})
        # A failure mid-list is NOT a reason to reorder or substitute. Continue, and let
        # the manifest record exactly which frozen positions are missing.
        continue

    bars = bars[["time_key", "open", "high", "low", "close", "volume", "turnover"]].copy()
    bars["date"] = bars["time_key"].str[:10]
    bars = (bars.drop_duplicates(subset="time_key")
                .sort_values("time_key").reset_index(drop=True))
    per_day = bars.groupby("date").size()

    path = os.path.join(RAW, f"US_{sym}_{KNAME}_raw.csv")
    bars.to_csv(path, index=False)

    rec = {
        "symbol": sym,
        "block": "equity" if sym in EQUITY_BLOCK else "non-equity",
        "position_in_frozen_order": i,
        "bars": len(bars),
        "sessions": int(per_day.size),
        "first_bar": str(bars["time_key"].iloc[0]),
        "last_bar": str(bars["time_key"].iloc[-1]),
        "first_close_raw": float(bars["close"].iloc[0]),
        "last_close_raw": float(bars["close"].iloc[-1]),
        "median_bars_per_session": int(per_day.median()),
        "file": f"data/raw/US_{sym}_{KNAME}_raw.csv",
        "sha256": sha256_file(path),
        "size_mb": round(os.path.getsize(path) / 1024 / 1024, 1),
    }
    records.append(rec)
    print(f"  [{i + 1:>2}/{len(UNIVERSE)}] {sym:<5} {len(bars):>7,} bars  "
          f"{per_day.size:>5} sessions  {rec['first_bar'][:10]} .. {rec['last_bar'][:10]}  "
          f"{rec['size_mb']:>4.1f} MB")

q.close()

# A symbol whose history starts materially after the common start is NOT comparable on the
# training segment. Flag it here rather than discovering it inside a result.
if records:
    latest_start = max(r["first_bar"][:10] for r in records)
    short = [r["symbol"] for r in records if r["first_bar"][:10] > START]
else:
    latest_start, short = None, []

manifest = {
    "generated_utc": datetime.now(timezone.utc).isoformat(),
    "preregistration": "docs/preregistration_v4.md section 2",
    "frozen_universe": UNIVERSE,
    "universe_size_requested": len(UNIVERSE),
    "universe_size_pulled": len(records),
    "truncated": len(records) < len(UNIVERSE),
    "failed": failed,
    "autype": "NONE (raw, unadjusted)",
    "ktype": KNAME,
    "requested_window": [START, END],
    "timestamp_convention": "time_key is the bar CLOSE; first session bar 09:35 covers 09:30-09:35",
    "latest_first_bar": latest_start,
    "symbols_starting_after_common_start": short,
    "DISTRIBUTIONS_NOT_INCLUDED": (
        "Prices are raw. The V4 rule holds overnight and across ex-dates, and the "
        "buy-and-hold benchmark receives distributions these files do not show. "
        "Dividends must be applied as cash events before any rule-vs-hold comparison."
    ),
    "symbols": records,
}
with open(MANIFEST, "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2, default=str)

print()
print(f"pulled    : {len(records)}/{len(UNIVERSE)}"
      f"{'  TRUNCATED' if manifest['truncated'] else ''}")
if failed:
    print(f"failed    : {', '.join(f['symbol'] for f in failed)}")
if short:
    print(f"late start: {', '.join(short)}  (history begins after {START})")
print(f"manifest  : data/universe_manifest.json")
print()
print("  Prices only. Distributions are NOT in these files and the benchmark receives")
print("  them - run tools/pull_dividends.py before comparing the rule to buy-and-hold.")
