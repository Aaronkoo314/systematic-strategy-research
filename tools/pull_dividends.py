"""Pull QQQ's cash-distribution record, needed now that overnight holding is allowed.

Why this exists. The 5-minute series is raw (AuType.NONE) on purpose: adjusted prices
give wrong share counts and are not executable order prices. While the strategy was
flat overnight that was the end of it - a position never spanned an ex-date, so no
distribution was ever received.

Allowing overnight holding changes that. A position held across an ex-date receives a
cash distribution, taxed at 30 % US withholding for a Singapore resident with no treaty
relief. It must be booked as a CASH EVENT on the ex-date, never by swapping in an
adjusted price series - an adjusted series encodes all future distributions into
historical prices, which is look-ahead.

Read-only.  Usage: python tools/pull_dividends.py
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
WINDOW_START, WINDOW_END = "2018-09-10", "2026-09-12"
WITHHOLDING = 0.30   # Singapore resident, no US treaty. Verified docs/feasibility.md §8.

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_CSV = os.path.join(ROOT, "data", "US_QQQ_dividends.csv")
OUT_JSON = os.path.join(ROOT, "data", "dividends_manifest.json")


def main() -> int:
    q = mm.OpenQuoteContext(host=HOST, port=PORT)
    ret, rehab = q.get_rehab(CODE)
    q.close()
    if ret != mm.RET_OK:
        print(f"ERROR get_rehab: {rehab}")
        return 1

    df = rehab.copy()
    df["ex_div_date"] = df["ex_div_date"].astype(str).str[:10]
    div = pd.to_numeric(df.get("per_cash_div"), errors="coerce").fillna(0.0)
    special = pd.to_numeric(df.get("special_dividend"), errors="coerce").fillna(0.0)
    split = pd.to_numeric(df.get("split_ratio"), errors="coerce").fillna(0.0)

    out = pd.DataFrame({
        "ex_date": df["ex_div_date"],
        "per_share_gross": div,
        "special": special,
        "split_ratio": split,
    })
    out = out[(out["per_share_gross"] > 0) | (out["special"] > 0) | (out["split_ratio"] > 0)]
    out = out.sort_values("ex_date").reset_index(drop=True)

    in_window = out[(out["ex_date"] >= WINDOW_START) & (out["ex_date"] <= WINDOW_END)].copy()
    in_window["withholding_rate"] = WITHHOLDING
    in_window["per_share_net"] = in_window["per_share_gross"] * (1.0 - WITHHOLDING)

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    in_window.to_csv(OUT_CSV, index=False)

    h = hashlib.sha256(open(OUT_CSV, "rb").read()).hexdigest()
    gross = float(in_window["per_share_gross"].sum())
    net = float(in_window["per_share_net"].sum())

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "code": CODE,
        "source": "moomoo OpenAPI get_rehab via local OpenD",
        "window": [WINDOW_START, WINDOW_END],
        "n_distributions_in_window": int(len(in_window)),
        "n_records_total": int(len(out)),
        "first_ex_date_on_record": str(out["ex_date"].iloc[0]) if len(out) else None,
        "first_ex_date_in_window": str(in_window["ex_date"].iloc[0]) if len(in_window) else None,
        "last_ex_date_in_window": str(in_window["ex_date"].iloc[-1]) if len(in_window) else None,
        "splits_in_window": int((in_window["split_ratio"] > 0).sum()),
        "total_per_share_gross": round(gross, 6),
        "total_per_share_net_after_30pct": round(net, 6),
        "withholding_rate": WITHHOLDING,
        "withholding_basis": ("Singapore tax residency, no US-Singapore income tax treaty; "
                              "W-8BEN status UNCONFIRMED - see investment_mandate.md §8"),
        "booking_rule": ("book as a cash credit on the ex-date for shares held at that "
                         "moment; never substitute an adjusted price series"),
        "file": "data/US_QQQ_dividends.csv",
        "sha256": h,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"distributions in window : {len(in_window)}")
    print(f"first / last ex-date    : {manifest['first_ex_date_in_window']} .. "
          f"{manifest['last_ex_date_in_window']}")
    print(f"splits in window        : {manifest['splits_in_window']}")
    print(f"total per share gross   : {gross:.4f}")
    print(f"total per share net 30% : {net:.4f}")
    print(f"\nsaved: data/US_QQQ_dividends.csv  sha256 {h[:24]}...")
    print(f"       data/dividends_manifest.json")
    print("\nfirst 5:")
    print(in_window.head(5).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
