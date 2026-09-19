"""Daily bars, RAW and QFQ, for the 23-symbol universe back to the API's retention limit.

Why now. Every research direction that survives the constraint review will be a
multi-asset or multi-year one - the intraday and single-asset directions are the ones
that closed. Those need daily history across asset classes, and daily history reaches
back ~20 years (2006-09 for symbols that existed then) where intraday stops at 2018-09.
Pulling it is design-independent: it looks at no return and biases no selection.

File format matches tools/audit_data.py exactly - raw and QFQ columns side by side plus
the QFQ/raw ratio - so src.data.bars.load_daily and the existing QFQ-verification tooling
work unchanged. Only the _raw columns are ever used for backtesting; the QFQ columns exist
so the adjustment can be reconciled against the distribution record, never as prices.

Quota. History candles are metered per symbol over a rolling window. All 23 symbols were
fetched at 5-minute resolution today, so daily pulls of the same symbols should be free.
The quota is read before and after and both numbers go in the manifest, so the assumption
is checked rather than trusted.

Read-only.  Usage: python tools/pull_universe_daily.py
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

import moomoo as mm
import pandas as pd

HOST, PORT = "127.0.0.1", 11111
PROBE_START, END = "1990-01-01", "2026-09-12"

UNIVERSE = [
    "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY",
    "SPY", "IWM", "DIA", "EFA", "EEM",
    "TLT", "IEF", "LQD", "HYG", "GLD", "SLV", "USO",
]
EQUITY_BLOCK = set(UNIVERSE[:16])

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
MANIFEST = os.path.join(ROOT, "data", "universe_daily_manifest.json")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_all(q, code, autype):
    frames, key = [], None
    while True:
        ret, df, key = q.request_history_kline(
            code, start=PROBE_START, end=END, ktype=mm.KLType.K_DAY,
            autype=autype, max_count=1000, page_req_key=key)
        if ret != mm.RET_OK:
            return None, str(df)
        frames.append(df)
        if key is None:
            break
    return (pd.concat(frames, ignore_index=True) if frames else None), None


q = mm.OpenQuoteContext(host=HOST, port=PORT)
ret, quota_before = q.get_history_kl_quota(get_detail=False)
quota_before = quota_before if ret == mm.RET_OK else str(quota_before)

print("=" * 92)
print("V4 UNIVERSE - DAILY BARS, RAW + QFQ, back to API retention")
print(f"{len(UNIVERSE)} symbols   quota before: {quota_before}")
print("=" * 92)

os.makedirs(RAW, exist_ok=True)
records, failed = [], []
for i, sym in enumerate(UNIVERSE):
    code = f"US.{sym}"
    raw, e1 = fetch_all(q, code, mm.AuType.NONE)
    adj, e2 = fetch_all(q, code, mm.AuType.QFQ)
    if raw is None or adj is None or not len(raw):
        failed.append({"symbol": sym, "error": (e1 or e2 or "empty")[:200]})
        print(f"  [{i + 1:>2}/{len(UNIVERSE)}] {sym:<5} FAILED  {(e1 or e2 or 'empty')[:60]}")
        continue

    m = raw[["time_key", "open", "high", "low", "close", "volume"]].merge(
        adj[["time_key", "open", "high", "low", "close"]],
        on="time_key", suffixes=("_raw", "_qfq"))
    m = m.drop_duplicates(subset="time_key").sort_values("time_key").reset_index(drop=True)
    m["ratio"] = m["close_qfq"] / m["close_raw"]
    m["dratio"] = m["ratio"].diff().abs()

    path = os.path.join(RAW, f"US_{sym}_daily.csv")
    m.to_csv(path, index=False)

    first, last = str(m["time_key"].iloc[0])[:10], str(m["time_key"].iloc[-1])[:10]
    years = (pd.to_datetime(last) - pd.to_datetime(first)).days / 365.25
    rec = {"symbol": sym, "block": "equity" if sym in EQUITY_BLOCK else "non-equity",
           "rows": len(m), "first_bar": first, "last_bar": last, "years": round(years, 2),
           "first_close_raw": float(m["close_raw"].iloc[0]),
           "last_close_raw": float(m["close_raw"].iloc[-1]),
           "qfq_ratio_steps_per_year": round(float((m["dratio"] > 1e-4).sum() / max(years, 1e-9)), 2),
           "file": f"data/raw/US_{sym}_daily.csv", "sha256": sha256_file(path)}
    records.append(rec)
    print(f"  [{i + 1:>2}/{len(UNIVERSE)}] {sym:<5} {len(m):>5} rows  {first} .. {last}  "
          f"{years:>5.1f}y  qfq steps/yr {rec['qfq_ratio_steps_per_year']:>5.1f}")

ret, quota_after = q.get_history_kl_quota(get_detail=False)
quota_after = quota_after if ret == mm.RET_OK else str(quota_after)
q.close()

common_start = max(r["first_bar"] for r in records) if records else None
manifest = {
    "generated_utc": datetime.now(timezone.utc).isoformat(),
    "ktype": "K_DAY", "autype": "NONE and QFQ side by side; only _raw is ever used as a price",
    "requested_window": [PROBE_START, END],
    "quota_before": quota_before, "quota_after": quota_after,
    "universe": UNIVERSE, "pulled": len(records), "failed": failed,
    "common_start_all_symbols": common_start,
    "symbols_starting_after_2006_09": [r["symbol"] for r in records if r["first_bar"] > "2006-09-05"],
    "symbols": records,
}
with open(MANIFEST, "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2, default=str)

print()
print(f"pulled       : {len(records)}/{len(UNIVERSE)}")
print(f"quota        : {quota_before} -> {quota_after}")
print(f"common start : {common_start}  (the earliest date ALL symbols share)")
late = manifest["symbols_starting_after_2006_09"]
if late:
    print(f"start later  : {', '.join(late)}")
print("manifest     : data/universe_daily_manifest.json")
