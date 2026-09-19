"""Distribution records for the cash-leg proxies SHY and BIL, as ex-date cash events.

Needed because the first attempt at pricing the cash leg decomposed a QFQ series into
price and distribution components DAILY. QFQ is affine (P_adj = P*A + B), so the daily
difference between adjusted and raw returns is nonzero noise on every day, not only on
ex-dates; clipping that noise at zero kept the positive half and produced a 5.98%/yr
"return" for BIL over 2012-2026, roughly four times the truth. The same class of
artefact has now been hit three times in this project (QQQ ratio steps, XLF, this).

The only honest treatment is the one every other leg already uses: raw prices, and the
actual distribution credited as CASH on its ex-date, net of 30% withholding. This pulls
the record that makes that possible. Same output format as tools/pull_dividends_daily.py.

Read-only. Costs 1 history-quota unit per symbol not fetched in the last 7 days.
Usage: python tools/pull_cash_dividends.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import moomoo as mm
import pandas as pd

HOST, PORT = "127.0.0.1", 11111
WINDOW_START, WINDOW_END = "2006-01-01", "2026-09-12"
WITHHOLDING = 0.30
SYMBOLS = ("SHY", "BIL")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    q = mm.OpenQuoteContext(host=HOST, port=PORT)
    ret, q0 = q.get_history_kl_quota(get_detail=False)
    summary = {"generated_utc": datetime.now(timezone.utc).isoformat(),
               "withholding_rate": WITHHOLDING, "quota_before": q0 if ret == mm.RET_OK else str(q0),
               "symbols": {}}
    for sym in SYMBOLS:
        ret, rehab = q.get_rehab(f"US.{sym}")
        if ret != mm.RET_OK or rehab is None or not len(rehab):
            print(f"  {sym}: FAILED or empty - {str(rehab)[:80]}")
            summary["symbols"][sym] = {"error": str(rehab)[:200]}
            continue
        df = rehab.copy()
        df["ex_date"] = df["ex_div_date"].astype(str).str[:10]
        cash = pd.to_numeric(df.get("per_cash_div"), errors="coerce").fillna(0.0)
        special = pd.to_numeric(df.get("special_dividend"), errors="coerce").fillna(0.0)
        split = pd.to_numeric(df.get("split_ratio"), errors="coerce").fillna(0.0)
        out = pd.DataFrame({
            "ex_date": df["ex_date"],
            "per_share_gross": (cash + special).round(6),
            "special": special.round(6),
            "split_ratio": split,
            "withholding_rate": WITHHOLDING,
        })
        out["per_share_net"] = (out["per_share_gross"] * (1 - WITHHOLDING)).round(6)
        out = out[(out["ex_date"] >= WINDOW_START) & (out["ex_date"] <= WINDOW_END)]
        # Keep split rows even though they carry no cash: BIL reverse-split 1-for-2 on
        # 2017-11-30 (raw close 45.74 -> 91.48) and a raw return series that does not know
        # about it books a +100% day. The consumer applies split_ratio as a price multiplier.
        is_split = (out["split_ratio"] != 0) & (out["split_ratio"] != 1)
        out = out[(out["per_share_gross"] > 0) | is_split].sort_values("ex_date").reset_index(drop=True)
        path = os.path.join(ROOT, "data", f"US_{sym}_dividends_daily.csv")
        out.to_csv(path, index=False)
        yrs = (pd.to_datetime(out["ex_date"].iloc[-1]) - pd.to_datetime(out["ex_date"].iloc[0])).days / 365.25
        summary["symbols"][sym] = {
            "rows": len(out), "first_ex_date": out["ex_date"].iloc[0], "last_ex_date": out["ex_date"].iloc[-1],
            "ex_dates_per_year": round(len(out) / max(yrs, 1e-9), 2),
            "gross_total_per_share": round(float(out["per_share_gross"].sum()), 4),
            "splits_in_window": int(((split != 0) & (split != 1)).sum()),
            "file": f"data/US_{sym}_dividends_daily.csv"}
        s = summary["symbols"][sym]
        print(f"  {sym}: {s['rows']} ex-dates {s['first_ex_date']} .. {s['last_ex_date']}  "
              f"({s['ex_dates_per_year']}/yr, monthly payer -> ~12)  gross {s['gross_total_per_share']}/sh  "
              f"splits {s['splits_in_window']}")
    ret, q1 = q.get_history_kl_quota(get_detail=False)
    summary["quota_after"] = q1 if ret == mm.RET_OK else str(q1)
    q.close()
    with open(os.path.join(ROOT, "data", "cash_dividends_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=str)
    print(f"  quota {summary['quota_before']} -> {summary['quota_after']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
