"""Data audit for the moomoo/Futu daily history that will back the research.

Answers four questions that must be settled BEFORE any backtest, because each one
can silently invalidate every number produced afterwards:

  Q1  How far back does each instrument actually go?
  Q2  Does AuType.QFQ reverse DIVIDENDS, or only splits?
      A price-only series discards ~1 %/yr of distributions, and it discards them
      ASYMMETRICALLY for a strategy that sits in cash part of the time.
  Q3  Are there missing sessions versus the official trading calendar?
  Q4  Can the pulled data be pinned - row counts, date ranges, SHA-256 - so a
      backtest is reproducible and its inputs are verifiable later?

Strictly read-only against the broker. Writes CSVs to data/raw/ (git-ignored) and
a manifest to data/data_manifest.json (tracked).

Usage: python tools/audit_data.py
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

import moomoo as mm
import pandas as pd

HOST, PORT = "127.0.0.1", 11111

# QQQ is the operator's chosen instrument. The others are candidate defensive
# legs and benchmark components; probing them now costs 1 history quota each.
SYMBOLS = ["US.QQQ", "US.SPY", "US.BIL", "US.SHY", "US.IEF", "US.TLT", "US.AGG"]

PROBE_START = "1990-01-01"
END = "2026-09-12"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
MANIFEST = os.path.join(ROOT, "data", "data_manifest.json")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_all(q, code: str, autype) -> pd.DataFrame | None:
    """Full daily history, paging through the API's page_req_key."""
    frames, key = [], None
    while True:
        ret, df, key = q.request_history_kline(
            code, start=PROBE_START, end=END, ktype=mm.KLType.K_DAY,
            autype=autype, max_count=1000, page_req_key=key)
        if ret != mm.RET_OK:
            print(f"    [ERR] {code} {autype}: {df}")
            return None
        frames.append(df)
        if key is None:
            break
    return pd.concat(frames, ignore_index=True)


def main() -> int:
    os.makedirs(RAW, exist_ok=True)
    q = mm.OpenQuoteContext(host=HOST, port=PORT)

    ret, quota_before = q.get_history_kl_quota(get_detail=False)
    print(f"history quota before: {quota_before}")

    ret, cal = q.request_trading_days(market=mm.TradeDateMarket.US,
                                      start="2006-01-01", end=END)
    calendar = set(pd.DataFrame(cal)["time"]) if ret == mm.RET_OK else set()
    print(f"US trading calendar sessions 2006-01-01..{END}: {len(calendar)}")

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": "moomoo OpenAPI via local OpenD",
        "sdk_version": getattr(mm, "__version__", "unknown"),
        "timezone_note": "time_key is US Eastern session date as returned by the API",
        "end_requested": END,
        "instruments": {},
    }

    for code in SYMBOLS:
        print(f"\n=== {code} ===")
        raw = fetch_all(q, code, mm.AuType.NONE)
        adj = fetch_all(q, code, mm.AuType.QFQ)
        if raw is None or adj is None:
            manifest["instruments"][code] = {"error": "fetch failed"}
            continue

        m = raw[["time_key", "open", "high", "low", "close", "volume"]].merge(
            adj[["time_key", "open", "high", "low", "close"]],
            on="time_key", suffixes=("_raw", "_qfq"))
        m["ratio"] = m["close_qfq"] / m["close_raw"]

        # --- Q2: dividend adjustment detection -------------------------------
        m["dratio"] = m["ratio"].diff().abs()
        steps = m[m["dratio"] > 1e-4]
        first_dt = pd.to_datetime(m["time_key"].iloc[0])
        last_dt = pd.to_datetime(m["time_key"].iloc[-1])
        years = max((last_dt - first_dt).days / 365.25, 1e-9)
        steps_per_year = len(steps) / years

        if m["ratio"].nunique() == 1 and abs(m["ratio"].iloc[0] - 1.0) < 1e-9:
            verdict = "NO_ADJUSTMENT"
        elif steps_per_year >= 3:
            verdict = "LIKELY_INCLUDES_DIVIDENDS"
        elif steps_per_year > 0:
            verdict = "SPLITS_ONLY_OR_SPARSE"
        else:
            verdict = "CONSTANT_RATIO_NO_STEPS"

        # --- Q3: calendar gaps ----------------------------------------------
        have = set(str(t)[:10] for t in m["time_key"])
        expected = set(d for d in calendar if d >= str(m["time_key"].iloc[0])[:10])
        missing = sorted(expected - have)

        # --- Q4: pin it ------------------------------------------------------
        path = os.path.join(RAW, f"{code.replace('.', '_')}_daily.csv")
        m.to_csv(path, index=False)

        info = {
            "rows": len(m),
            "first_bar": str(m["time_key"].iloc[0]),
            "last_bar": str(m["time_key"].iloc[-1]),
            "years": round(years, 2),
            "adjustment": {
                "ratio_first": round(float(m["ratio"].iloc[0]), 8),
                "ratio_last": round(float(m["ratio"].iloc[-1]), 8),
                "n_steps_gt_1bp": int(len(steps)),
                "steps_per_year": round(steps_per_year, 2),
                "verdict": verdict,
                "example_steps": [
                    {"date": str(r["time_key"])[:10],
                     "raw_close": round(float(r["close_raw"]), 4),
                     "qfq_close": round(float(r["close_qfq"]), 4),
                     "ratio": round(float(r["ratio"]), 6)}
                    for _, r in steps.head(4).iterrows()
                ],
            },
            "calendar": {
                "expected_sessions": len(expected),
                "missing_sessions": len(missing),
                "missing_examples": missing[:5],
            },
            "file": os.path.relpath(path, ROOT).replace("\\", "/"),
            "sha256": sha256_file(path),
        }
        manifest["instruments"][code] = info

        print(f"  rows={info['rows']}  {info['first_bar'][:10]} -> {info['last_bar'][:10]}"
              f"  ({info['years']}y)")
        print(f"  adjustment: {verdict}  (ratio {info['adjustment']['ratio_first']}"
              f" -> {info['adjustment']['ratio_last']}, {len(steps)} steps,"
              f" {steps_per_year:.2f}/yr)")
        print(f"  calendar: {len(missing)} missing of {len(expected)} expected")

    ret, quota_after = q.get_history_kl_quota(get_detail=False)
    manifest["quota_before"], manifest["quota_after"] = str(quota_before), str(quota_after)
    print(f"\nhistory quota after: {quota_after}")
    q.close()

    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, default=str)
    print(f"manifest written: data/data_manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
