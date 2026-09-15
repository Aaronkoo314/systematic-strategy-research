"""Pull QQQ 5-minute bars at RAW (unadjusted) prices, which is what an intraday
strategy must be backtested on.

Why raw, not QFQ. Forward adjustment rescales the whole historical price level to
reverse future dividends. Intraday returns are unaffected because the factor is
constant within a day - but share counts are not. Position sizing is
floor(cash / price), so adjusted prices produce historically wrong share counts,
wrong notionals and wrong per-share fees. It also violates the rule against using
adjusted research prices as executable order prices. A strategy that is flat
overnight never receives a distribution, so there is nothing to adjust for.

If a variant ever holds overnight, dividends must be handled explicitly as cash
events on ex-dates, not by swapping in an adjusted series.

Timestamp convention, verified: time_key is the bar's CLOSE. The first bar of a
session is 09:35 and covers 09:30-09:35. A signal from the bar stamped 09:35
therefore may not be executed before 09:35.

Read-only.  Usage: python tools/pull_intraday.py
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

import moomoo as mm
import pandas as pd

HOST, PORT = "127.0.0.1", 11111
CODE = "US.QQQ"
START, END = "2018-09-10", "2026-09-12"
KTYPE, KNAME = mm.KLType.K_5M, "5min"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
MANIFEST = os.path.join(ROOT, "data", "intraday_manifest.json")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


q = mm.OpenQuoteContext(host=HOST, port=PORT)
frames, key, pages = [], None, 0
while True:
    ret, df, key = q.request_history_kline(
        CODE, start=START, end=END, ktype=KTYPE, autype=mm.AuType.NONE,
        max_count=1000, page_req_key=key)
    if ret != mm.RET_OK:
        print(f"ERROR on page {pages}: {df}")
        break
    frames.append(df)
    pages += 1
    if pages % 40 == 0:
        print(f"  {pages} pages, {sum(len(f) for f in frames)} bars")
    if key is None:
        break
q.close()

bars = pd.concat(frames, ignore_index=True)
bars = bars[["time_key", "open", "high", "low", "close", "volume", "turnover"]].copy()
bars["date"] = bars["time_key"].str[:10]
bars = bars.drop_duplicates(subset="time_key").sort_values("time_key").reset_index(drop=True)

per_day = bars.groupby("date").size()
os.makedirs(RAW, exist_ok=True)
path = os.path.join(RAW, f"US_QQQ_{KNAME}_raw.csv")
bars.to_csv(path, index=False)

# sanity: raw price level should match the real market, not a rescaled one
first_close = float(bars["close"].iloc[0])
last_close = float(bars["close"].iloc[-1])

manifest = {
    "generated_utc": datetime.now(timezone.utc).isoformat(),
    "code": CODE,
    "ktype": KNAME,
    "autype": "NONE (raw, unadjusted) - required for correct share counts and order prices",
    "timestamp_convention": "time_key is the bar CLOSE; first session bar 09:35 covers 09:30-09:35",
    "session_coverage": "regular session only, 09:35-16:00 ET; no pre/post market bars",
    "bars": len(bars),
    "sessions": int(per_day.size),
    "first_bar": str(bars["time_key"].iloc[0]),
    "last_bar": str(bars["time_key"].iloc[-1]),
    "years": round((pd.to_datetime(bars["date"].iloc[-1])
                    - pd.to_datetime(bars["date"].iloc[0])).days / 365.25, 2),
    "bars_per_day": {str(k): int(v) for k, v in per_day.value_counts().items()},
    "first_close_raw": first_close,
    "last_close_raw": last_close,
    "file": f"data/raw/US_QQQ_{KNAME}_raw.csv",
    "sha256": sha256_file(path),
    "size_mb": round(os.path.getsize(path) / 1024 / 1024, 1),
}

with open(MANIFEST, "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2, default=str)

print(f"\nbars      : {len(bars)}")
print(f"sessions  : {per_day.size}  ({manifest['years']} years)")
print(f"span      : {manifest['first_bar']} .. {manifest['last_bar']}")
print(f"bars/day  : {manifest['bars_per_day']}")
print(f"raw close : {first_close} (first) .. {last_close} (last)")
print(f"saved     : {manifest['file']}  ({manifest['size_mb']} MB)")
print(f"sha256    : {manifest['sha256'][:32]}...")
print("manifest  : data/intraday_manifest.json")
