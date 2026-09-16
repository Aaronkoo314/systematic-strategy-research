"""Figures F1-F6 of docs/report_sop.md.

Two rules from the SOP are enforced here rather than left to whoever calls it:

  R1  the denominator is always full NAV including idle cash. Nothing in this module
      ever divides by deployed value.
  R2  every figure states its cost basis in its own title.

Every figure also carries the standing caveat that the ex-ante power gate failed, so a
chart cannot be lifted out of the report and shown without it.
"""

from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

CAVEAT = ("Ex-ante power gate FAILED: this sample cannot distinguish an edge of this "
          "size from luck. Engineering validation, not evidence.")
NET = "net of all modelled costs"

plt.rcParams.update({
    "figure.dpi": 120, "savefig.dpi": 120, "font.size": 9,
    "axes.grid": True, "grid.alpha": 0.25, "axes.spines.top": False,
    "axes.spines.right": False, "figure.autolayout": False,
})


def _caveat(fig):
    fig.text(0.5, 0.005, CAVEAT, ha="center", va="bottom", fontsize=7,
             color="#a33", style="italic")


def _dt(df):
    return pd.to_datetime(df["time_key"])


def f1_equity(equity: pd.DataFrame, benchmark: pd.DataFrame | None, out: str,
              title_extra: str = "") -> str:
    """Equity curve on full NAV, thresholds marked."""
    fig, ax = plt.subplots(figsize=(11, 5.2))
    t = _dt(equity)
    nav0 = equity["nav"].iloc[0]
    ax.plot(t, equity["nav"] / nav0, lw=1.2, color="#1f4e79", label="candidate (full NAV)")
    if benchmark is not None and len(benchmark):
        ax.plot(_dt(benchmark), benchmark["nav"] / benchmark["nav"].iloc[0],
                lw=1.0, color="#999", label="buy & hold QQQ")

    for lvl, lab, c in ((0.05, "review -5%", "#e8a33d"),
                        (0.08, "halt -8%", "#d9722c"),
                        (0.20, "ABANDON -20%", "#c0392b")):
        ax.axhline(1 - lvl, ls="--", lw=0.8, color=c, alpha=0.7)
        ax.text(t.iloc[0], 1 - lvl, f" {lab}", color=c, fontsize=7, va="bottom")

    worst = equity["drawdown"].min()
    ax.set_title(f"F1  Equity on FULL NAV including idle cash - {NET}{title_extra}\n"
                 f"worst drawdown {worst:.2%}"
                 + ("   *** breached the 20% abandon point ***" if worst <= -0.20 else ""),
                 fontsize=10, loc="left")
    ax.set_ylabel("growth of 1")
    ax.legend(loc="upper left", frameon=False, fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.subplots_adjust(bottom=0.12)
    _caveat(fig)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def f2_price_with_fills(equity: pd.DataFrame, fills: pd.DataFrame, out: str,
                        title_extra: str = "") -> str:
    """Price with every fill marked. Overnight fills hollow - they carry gap risk and
    17-hour-old information and must be visually separable."""
    fig, (ax, axw) = plt.subplots(2, 1, figsize=(11, 6.4), sharex=True,
                                  gridspec_kw={"height_ratios": [3, 1]})
    t = _dt(equity)
    ax.plot(t, equity["price"], lw=0.7, color="#444", label="QQQ")

    if len(fills):
        f = fills.copy()
        f["t"] = pd.to_datetime(f["time_key"])
        for side, marker, col in (("buy", "^", "#2e7d32"), ("sell", "v", "#c0392b")):
            sub = f[f["side"] == side]
            day = sub[~sub["overnight"].astype(bool)]
            night = sub[sub["overnight"].astype(bool)]
            ax.scatter(day["t"], day["fill_price"], marker=marker, s=26, c=col,
                       zorder=3, label=f"{side} ({len(day)})")
            if len(night):
                ax.scatter(night["t"], night["fill_price"], marker=marker, s=40,
                           facecolors="none", edgecolors=col, linewidths=1.2, zorder=4,
                           label=f"{side} overnight ({len(night)})")

    ax.set_title(f"F2  Fills on price - {NET}{title_extra}\n"
                 f"hollow = overnight fill (gap risk, 17-hour-old information)",
                 fontsize=10, loc="left")
    ax.set_ylabel("QQQ")
    ax.legend(loc="upper left", frameon=False, fontsize=7, ncol=2)

    w = equity["deployed_value"] / equity["nav"]
    axw.fill_between(t, 0, w, color="#1f4e79", alpha=0.35, lw=0)
    axw.axhline(0.90, ls="--", lw=0.8, color="#c0392b")
    axw.text(t.iloc[0], 0.90, " exposure cap 90%", fontsize=7, color="#c0392b",
             va="bottom")
    axw.set_ylabel("weight")
    axw.set_ylim(0, 1.05)
    axw.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.subplots_adjust(bottom=0.10)
    _caveat(fig)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def annual_table(equity: pd.DataFrame, benchmark: pd.DataFrame | None,
                 fills: pd.DataFrame) -> pd.DataFrame:
    eq = equity.copy()
    eq["year"] = pd.to_datetime(eq["time_key"]).dt.year
    rows = []
    for y, g in eq.groupby("year"):
        r = g["nav"].iloc[-1] / g["nav"].iloc[0] - 1.0
        hwm = g["nav"].cummax()
        dd = (g["nav"] / hwm - 1.0).min()
        b = np.nan
        if benchmark is not None and len(benchmark):
            bq = benchmark.copy()
            bq["year"] = pd.to_datetime(bq["time_key"]).dt.year
            bg = bq[bq["year"] == y]
            if len(bg):
                b = bg["nav"].iloc[-1] / bg["nav"].iloc[0] - 1.0
        n = 0
        fee = 0.0
        if len(fills):
            ff = fills.copy()
            ff["year"] = pd.to_datetime(ff["time_key"]).dt.year
            n = int((ff["year"] == y).sum())
            fee = float(ff.loc[ff["year"] == y, "fees"].sum())
        rows.append({"year": int(y), "net_return": r, "benchmark": b,
                     "difference": r - b if b == b else np.nan,
                     "max_drawdown": dd, "fills": n, "fees": fee,
                     "fees_pct_nav": fee / g["nav"].iloc[0] * 100,
                     "avg_weight": float((g["deployed_value"] / g["nav"]).mean())})
    return pd.DataFrame(rows)


def f3_annual(tbl: pd.DataFrame, out: str, title_extra: str = "") -> str:
    """Return attribution by calendar year, with the best year's share called out."""
    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    x = np.arange(len(tbl))
    ax.bar(x - 0.2, tbl["net_return"] * 100, width=0.4, color="#1f4e79",
           label="candidate")
    if tbl["benchmark"].notna().any():
        ax.bar(x + 0.2, tbl["benchmark"] * 100, width=0.4, color="#bbb",
               label="buy & hold")
    ax.axhline(0, color="#333", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(tbl["year"].astype(str))
    ax.set_ylabel("net return %")
    ax.legend(frameon=False, fontsize=8)

    tot = float((1 + tbl["net_return"]).prod() - 1)
    best = tbl.loc[tbl["net_return"].idxmax()]
    ex_best = tbl.drop(tbl["net_return"].idxmax())
    tot_ex = float((1 + ex_best["net_return"]).prod() - 1) if len(ex_best) else 0.0
    ax.set_title(f"F3  Return by calendar year - {NET}{title_extra}\n"
                 f"total {tot:+.1%}   best year {int(best['year'])} {best['net_return']:+.1%}"
                 f"   total EXCLUDING the best year {tot_ex:+.1%}",
                 fontsize=10, loc="left")
    fig.subplots_adjust(bottom=0.14)
    _caveat(fig)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def f4_concentration(trades: pd.DataFrame, out: str, title_extra: str = "") -> str:
    """How much of the result came from how few trades."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2))
    if len(trades):
        p = np.sort(trades["net_pnl"].to_numpy())[::-1]
        cum = np.cumsum(p)
        a1.plot(np.arange(1, len(p) + 1) / len(p) * 100, cum, lw=1.3, color="#1f4e79")
        a1.axhline(cum[-1], ls="--", lw=0.8, color="#888")
        a1.set_xlabel("% of trades, best first")
        a1.set_ylabel("cumulative net P&L (USD)")

        labels, vals = [], []
        for frac in (0.01, 0.05, 0.10):
            k = max(1, int(len(p) * frac))
            labels.append(f"ex best\n{frac:.0%}")
            vals.append(float(p[k:].sum()))
        labels.insert(0, "all")
        vals.insert(0, float(p.sum()))
        a2.bar(labels, vals, color=["#1f4e79", "#547ca8", "#8fa9c4", "#c3d2df"])
        a2.axhline(0, color="#333", lw=0.8)
        a2.set_ylabel("net P&L (USD)")
        top1 = float(p[:max(1, len(p) // 100)].sum())
        share = top1 / p.sum() * 100 if p.sum() != 0 else float("nan")
        a1.set_title(f"best 1% of trades = {share:.0f}% of total P&L", fontsize=9,
                     loc="left")
    fig.suptitle(f"F4  Concentration of results - {NET}{title_extra}", fontsize=10, x=0.02,
                 ha="left")
    fig.subplots_adjust(bottom=0.16, top=0.86)
    _caveat(fig)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def f5_drawdown(equity: pd.DataFrame, out: str, title_extra: str = "") -> str:
    fig, ax = plt.subplots(figsize=(11, 3.6))
    t = _dt(equity)
    ax.fill_between(t, equity["drawdown"] * 100, 0, color="#c0392b", alpha=0.35, lw=0)
    for lvl, c in ((5, "#e8a33d"), (8, "#d9722c"), (20, "#c0392b")):
        ax.axhline(-lvl, ls="--", lw=0.8, color=c)
    ax.set_ylabel("drawdown %")
    ax.set_title(f"F5  Underwater, on full NAV - {NET}{title_extra}   "
                 f"worst {equity['drawdown'].min():.2%}", fontsize=10, loc="left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.subplots_adjust(bottom=0.16)
    _caveat(fig)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def f6_costs(fills: pd.DataFrame, equity: pd.DataFrame, out: str,
             title_extra: str = "") -> str:
    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    if len(fills):
        f = fills.copy()
        f["year"] = pd.to_datetime(f["time_key"]).dt.year
        comp = f.groupby("year").agg(fees=("fees", "sum"),
                                     slip=("slippage_cost", "sum"))
        x = np.arange(len(comp))
        ax.bar(x, comp["fees"], color="#1f4e79", label="broker fees")
        ax.bar(x, comp["slip"], bottom=comp["fees"], color="#8fa9c4",
               label="modelled slippage")
        ax.set_xticks(x)
        ax.set_xticklabels(comp.index.astype(str))
        nav0 = equity["nav"].iloc[0]
        ax.axhline(nav0 * 0.10, ls="--", lw=0.9, color="#c0392b")
        ax.text(0, nav0 * 0.10, " 10%/yr fee ceiling", fontsize=7, color="#c0392b",
                va="bottom")
        ax.set_ylabel("USD")
        ax.legend(frameon=False, fontsize=8)
    ax.set_title(f"F6  Cost by year, itemised{title_extra}", fontsize=10, loc="left")
    fig.subplots_adjust(bottom=0.14)
    _caveat(fig)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out
