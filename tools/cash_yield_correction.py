"""How much did booking idle cash at 0% understate every cash-heavy result?

Every model in this project - the static-weight fallback, V1, V2, the barrier chains -
pays the un-invested part of the sleeve nothing. The abandon point forces that part to
50-75% of the sleeve. Over 2006-2026 a zero-duration Treasury ETF earned 1.6-1.9%/yr and
has paid 4-4.5%/yr since late 2023, so the omission is not a rounding error: on a 75%
cash sleeve it is on the order of 1-3%/yr of the WHOLE sleeve, which is larger than any
edge this project has measured or plausibly could.

This is not a strategy and not a backtest of one. It is a sizing of a modelling error,
done in pandas on daily closes, so that the fallback the operator can implement tomorrow
is priced correctly before any research direction is judged against it.

Method. QQQ leg: raw close return plus net dividend (30% withheld) on ex-dates, from the
files already on disk. Cash leg: a T-bill ETF's total return from its QFQ series (QFQ
includes distributions - verified: SHY steps 12x/yr), split into price return (raw) and
distribution component (QFQ minus raw); the distribution component is taxed at 30%. Two
proxies: SHY (1-3y, ~1.9y duration, on disk from 2006-09) and BIL (1-3m, ~0 duration, on
disk from 2012-01). Annual calendar rebalance to target weights on the first session of
each year, matching src/backtest/portfolio.py. No fees: an annual two-asset rebalance is
2-4 orders a year, 0.02-0.04%/yr, stated rather than modelled.

Also reported: the same blends with the cash leg's distributions UNTAXED, because whether
section 871(k) exempts a non-resident from withholding on a Treasury ETF's qualified
interest income is a live, unresolved question worth ~1%/yr on this sleeve.

Usage: python tools/cash_yield_correction.py
"""

from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
WITHHOLD = 0.30
WEIGHTS = (0.25, 0.35, 0.50)
FORWARD_BILL_YIELD = 0.043          # indicative current 3m T-bill, for the forward line only


def load_daily(sym):
    d = pd.read_csv(os.path.join(RAW, f"US_{sym}_daily.csv"))
    d["date"] = d["time_key"].str[:10]
    return d.set_index("date")[["close_raw", "close_qfq"]]


def qqq_total_return():
    q = load_daily("QQQ")
    div = pd.read_csv(os.path.join(ROOT, "data", "US_QQQ_dividends_daily.csv"))
    div["ex_date"] = div["ex_date"].astype(str).str[:10]
    net = div.groupby("ex_date")["per_share_net"].sum()
    pr = q["close_raw"].pct_change().fillna(0.0)
    prev_close = q["close_raw"].shift(1)
    dy = pd.Series(0.0, index=q.index)
    common = net.index.intersection(q.index)
    dy.loc[common] = net.loc[common].values / prev_close.loc[common].values
    return (pr + dy).rename("QQQ")


def cash_total_return(sym, withhold):
    """Raw price return plus the ACTUAL distribution as cash on its ex-date.

    A first version decomposed the QFQ series daily into price and distribution parts and
    clipped the difference at zero. QFQ is affine (P*A + B), so that difference is noise on
    every day, not only ex-dates, and keeping its positive half produced 5.98%/yr for BIL
    over 2012-2026 - about four times the truth. Same artefact family as the QQQ and XLF
    ratio-step false alarms. Ex-date cash events are the only honest method and are what
    every other leg in this project already uses.
    """
    c = load_daily(sym)
    div = pd.read_csv(os.path.join(ROOT, "data", f"US_{sym}_dividends_daily.csv"))
    div["ex_date"] = div["ex_date"].astype(str).str[:10]

    # splits: BIL reverse-split 1-for-2 on 2017-11-30 (raw 45.74 -> 91.48). Put pre-split
    # closes in post-split units for the RETURN series only; dividend yield below uses the
    # contemporaneous unadjusted close, so per-share cash and price stay in matching units.
    raw = c["close_raw"].astype(float).copy()
    splits = div[(div["split_ratio"] != 0) & (div["split_ratio"] != 1)]
    for ex, ratio in zip(splits["ex_date"], splits["split_ratio"].astype(float)):
        raw.loc[raw.index < ex] *= ratio
    pr = raw.pct_change().fillna(0.0)

    gross = div[div["per_share_gross"] > 0].groupby("ex_date")["per_share_gross"].sum()
    prev_close = c["close_raw"].shift(1)
    dy = pd.Series(0.0, index=c.index)
    common = gross.index.intersection(c.index)
    dy.loc[common] = (1.0 - withhold) * gross.loc[common].values / prev_close.loc[common].values
    return (pr + dy.fillna(0.0)).rename(sym)


def blend(rq, rc, w_q, start, end):
    """Annual calendar rebalance to (w_q, 1-w_q). rc may be None for cash at 0%."""
    df = pd.DataFrame({"q": rq})
    df["c"] = rc if rc is not None else 0.0
    df = df.loc[(df.index >= start) & (df.index <= end)].dropna()
    years = pd.Index(df.index.str[:4])
    nav, vq, vc = 1.0, w_q, 1.0 - w_q
    out, last_year = [], None
    for dt, (r_q, r_c), yr in zip(df.index, df[["q", "c"]].to_numpy(), years):
        if last_year is not None and yr != last_year:            # first session of a new year
            tot = vq + vc
            vq, vc = tot * w_q, tot * (1.0 - w_q)
        last_year = yr
        vq *= 1.0 + r_q
        vc *= 1.0 + r_c
        out.append(vq + vc)
    s = pd.Series(out, index=df.index)
    yrs = (pd.to_datetime(s.index[-1]) - pd.to_datetime(s.index[0])).days / 365.25
    cagr = s.iloc[-1] ** (1 / yrs) - 1.0
    dd = float((s / s.cummax() - 1.0).min())
    return cagr, dd, yrs


rq = qqq_total_return()
legs = {
    "SHY net 30%": cash_total_return("SHY", WITHHOLD),
    "SHY untaxed": cash_total_return("SHY", 0.0),
    "BIL net 30%": cash_total_return("BIL", WITHHOLD),
    "BIL untaxed": cash_total_return("BIL", 0.0),
}
windows = {
    "2006-09 .. 2026-09 (20y, has 2008)": ("2006-09-01", "2026-09-11", ["SHY net 30%", "SHY untaxed"]),
    "2012-01 .. 2026-09 (14.7y)": ("2012-01-03", "2026-09-11", ["SHY net 30%", "BIL net 30%", "BIL untaxed"]),
}

print("=" * 108)
print("WHAT BOOKING IDLE CASH AT 0% COST THE FALLBACK - annual rebalance, no fees, QQQ dividends net 30%")
print("=" * 108)
report = {}
for label, (lo, hi, use) in windows.items():
    print(f"\n{label}")
    print(f"{'QQQ w':>6} | {'cash leg':>13} {'CAGR':>8} {'max DD':>8} | {'vs cash@0':>10}")
    print("-" * 70)
    report[label] = {}
    for w in WEIGHTS:
        base_cagr, base_dd, yrs = blend(rq, None, w, lo, hi)
        print(f"{w:>6.0%} | {'cash @ 0%':>13} {base_cagr:>8.2%} {base_dd:>8.1%} | {'-':>10}")
        report[label][f"{w}"] = {"cash_0": {"cagr": base_cagr, "max_dd": base_dd}}
        for leg in use:
            cagr, dd, _ = blend(rq, legs[leg], w, lo, hi)
            print(f"{'':>6} | {leg:>13} {cagr:>8.2%} {dd:>8.1%} | {cagr - base_cagr:>+10.2%}")
            report[label][f"{w}"][leg] = {"cagr": cagr, "max_dd": dd, "uplift": cagr - base_cagr}
    print(f"   ({yrs:.1f} years)")

# cash-leg standalone, so the proxy's own risk is visible
print("\n" + "=" * 108)
print("THE CASH PROXIES THEMSELVES")
print("=" * 108)
for leg, r in legs.items():
    lo = "2006-09-01" if leg.startswith("SHY") else "2012-01-03"
    s = (1 + r.loc[(r.index >= lo)]).cumprod()
    yrs = (pd.to_datetime(s.index[-1]) - pd.to_datetime(s.index[0])).days / 365.25
    cagr = s.iloc[-1] ** (1 / yrs) - 1
    dd = float((s / s.cummax() - 1).min())
    recent = (1 + r.loc[r.index >= "2023-09-01"]).prod() ** (365.25 / (pd.to_datetime(s.index[-1]) - pd.to_datetime("2023-09-01")).days) - 1
    print(f"  {leg:<13} CAGR {cagr:>6.2%}   max DD {dd:>6.1%}   since 2023-09 {recent:>6.2%}/yr")
    report.setdefault("cash_legs", {})[leg] = {"cagr": cagr, "max_dd": dd, "since_2023_09": recent}

print("\n" + "=" * 108)
print("FORWARD, AT TODAY'S BILL YIELD - arithmetic, not a backtest")
print("=" * 108)
print(f"  3m T-bill assumed {FORWARD_BILL_YIELD:.1%}. Uplift to the WHOLE sleeve = (1 - w_q) x yield x (1 - withholding):")
for w in WEIGHTS:
    net = (1 - w) * FORWARD_BILL_YIELD * (1 - WITHHOLD)
    gross = (1 - w) * FORWARD_BILL_YIELD
    print(f"  QQQ {w:.0%} / bills {1 - w:.0%}:  +{net:.2%}/yr net of 30% withholding,  +{gross:.2%}/yr if 871(k) exempts")
report["forward"] = {"bill_yield": FORWARD_BILL_YIELD,
                     "uplift_net": {f"{w}": (1 - w) * FORWARD_BILL_YIELD * (1 - WITHHOLD) for w in WEIGHTS},
                     "uplift_untaxed": {f"{w}": (1 - w) * FORWARD_BILL_YIELD for w in WEIGHTS}}

print()
print("  Every cash-heavy result in this project - the fallback, V1, V2, every long/flat rule -")
print("  was understated by roughly the 'vs cash@0' column for its cash fraction. The fallback")
print("  the operator can implement tomorrow is worth more than the record says, before any")
print("  research is spent.")

os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
with open(os.path.join(ROOT, "reports", "cash_yield_correction.json"), "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=2, default=str)
print("\nwritten: reports/cash_yield_correction.json")
