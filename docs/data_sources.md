# Data Source Evaluation

**Date: 2026-09-15.** Requirement (gate G7): a source whose **licence permits personal research**,
with documented adjustment methodology and enough history to cover several market regimes.

**Conclusion: six of seven external free sources are eliminated. The seventh cannot be assessed
without the operator's own action. The working plan is the broker's own data — subject to two
unresolved prerequisites that must be settled before any local history store is built.**

---

## 1. Eliminated sources

| Source | Status | Decisive reason |
|---|---|---|
| **Yahoo / `yfinance`** | **ELIMINATED — licence** | Yahoo ToS 2.4(ix) prohibits collecting data *"using any automated means, devices, programs, algorithms or methodologies… without our express, prior permission."* No self-service route to that permission was found. Technically the best option — longest history, documented CRSP-standard adjustment with an explicit dividend-multiplier formula — but this is an explicit prohibition, not a grey area. `yfinance`'s Apache licence covers the Python code, **not** Yahoo's data. |
| **Tiingo (free Starter)** | **ELIMINATED — licence** | Best-documented data quality of any candidate (CRSP standard, returns raw `divCash` and `splitFactor` so the series can be self-audited). But ToS 1.6(a) forbids Starter-tier users to *"write, save, archive, back up, or otherwise retain Tiingo Data in any persistent or durable storage."* A reproducible backtest is by definition a persisted historical series. Paid Power tier is USD 360/yr = **3.6 %/yr of TP** — economically absurd against a strategy whose entire fixed-fee budget is ~0.33 %/yr. |
| **Alpha Vantage (free)** | **ELIMINATED — data permissions** | Two independent structural blocks: `outputsize=full` is premium-only (free keys return ~100 data points ≈ 5 months), and the only endpoint carrying adjusted closes and dividend/split events, `TIME_SERIES_DAILY_ADJUSTED`, is entirely premium. Its licence terms are among the cleanest — explicitly permitting personal research — but a clean licence cannot compensate for zero data access. |
| **Nasdaq Data Link / Quandl (free)** | **ELIMINATED — no such data** | The free tier has no US equity/ETF daily dataset at all. The WIKI price source froze on 2018-04-11 and covered common stocks, not ETFs. Anonymous metadata requests are now blocked by an anti-bot layer, and the official documentation page returns 404. |
| **Issuer NAV / distributions (SSGA, iShares)** | **NOT A PRICE SOURCE** | Authoritative but mismatched: issuers publish **NAV**, while this project transacts at **market price**, and ETFs trade at premiums/discounts. No issuer publishes a documented NAV+distribution total-return methodology, and no stable documented historical-NAV download endpoint was found. SSGA additionally restricts reproduction of its content. **Correct use: cross-checking dividend amounts, and authoritative inception dates.** |
| **Shiller dataset** | **NOT FIT FOR PURPOSE** | Free and very long (from 1871), but monthly and index-level. This project's signal comes from a completed *daily* bar and executes at the next open — monthly index data cannot rehearse that. Its own licence text is `not_found`. |

## 2. Not assessable without the operator

| Source | Status |
|---|---|
| **Stooq** | **BLOCKED.** Three problems compound: (1) since roughly March 2026 downloads require an API key, and the key page is behind the site's own verification; (2) **the CSV endpoint now serves a JavaScript proof-of-work bot-detection challenge** — confirmed by our own request on 2026-09-15, which returned HTTP 200 with a 796-byte challenge page, not CSV; (3) **no terms of use and no adjustment methodology could be found anywhere** — both `not_found`. Using it would mean backtesting without knowing either the licence status or how the price series is constructed. **Obtaining the key requires solving the site's human-verification step, which the operator must do personally — bypassing bot detection is out of scope for this project's tooling.** |

## 3. Working plan: the broker's own data

**Primary source: moomoo / Futu OpenAPI historical daily bars.** Rationale:

1. **It eliminates the mismatch between research data and execution data** — the single most valuable
   thing to protect here. Backtesting on vendor A's adjusted series while placing limit orders
   against Futu's quotes means any silent difference in adjustment convention (dividends included or
   not, ex-date versus pay-date, rounding) could exceed the entire claimed edge. Using one dataset
   for both drives that risk to zero.
2. **The adjustment is auditable, not a black box.** Futu publishes the adjustment form
   `P_adj = P × A + B` and exposes the underlying corporate actions via `RequestRehab`, so QFQ can
   be recomputed from `AuType.NONE` raw prices and reconciled bar by bar. Stooq and the issuers
   cannot be audited this way.
3. **Zero marginal cost and no third-party licence conflict** — the operator is already a Futu SG
   client and this data is part of the account's entitlement.
4. **Verified SPY coverage from 2006-09-01** spans the GFC, 2011, 2015–16, 2018Q4, 2020 and 2022 —
   every drawdown regime actually relevant to a 20 % abandon point.

### Drawbacks — these belong in the body of any conclusion, not a footnote

1. **History is short, and the bond side especially so.** SPY ≈ 19 years. AGG starts 2012-01-03,
   ≈ 14 years, **missing 2008 entirely** — and 2008 is precisely the episode a 60/40 bond allocation
   claims to withstand. Any bond-sleeve conclusion drawn from this data has never been tested
   against the one crisis that matters. IEF and BIL start dates are not yet probed.
2. **No independent second opinion.** Sharing one dataset between research and execution means a
   systematic error in Futu's adjustment factors would appear identically in both and therefore be
   invisible. **Mandatory mitigation: manually reconcile ~10 SPY ex-dividend dates against the
   issuer's published distribution history.**
3. **Licence status is unverified.** The Futu SG market-data agreement could not be obtained, so
   whether quotes may be stored locally for personal backtesting is genuinely unknown.
   **Do not build a local history store before settling this.**
4. **It cannot fix hindsight selection bias.** SPY/IEF/AGG/BIL are 2026 survivors. A fixed
   three-instrument universe has little classical survivorship bias, but severe hindsight selection
   bias, and no data source repairs that. Issuer inception dates prevent only one error — testing on
   dates when an instrument did not exist.

---

## 4. Unresolved prerequisites — **both must pass before any backtest**

| # | Item | Consequence if it fails |
|---|---|---|
| **D1** | Does the Futu SG market-data agreement permit storing history locally for personal backtesting? | No local store may be built; the primary plan collapses |
| **D2** | Does US-market QFQ include **cash dividends**, or only splits? Official docs do not state it (their example uses HK stocks). Test: recompute QFQ from `AuType.NONE` + `RequestRehab` and reconcile bar by bar, plus cross-check 10 SPY ex-dividend dates against issuer records. | **The entire data plan is void and the conclusion returns to "no usable data source"** |
| D3 | Earliest available daily bar for IEF and BIL | Determines the feasible backtest window |

Script prepared for D2: `tools/check_adjustment.py` — **written, not yet run, no result claimed.**

Verified issuer inception dates, to be hard-coded so no backtest window starts before an instrument
existed: **SPY 1993-01-22, BIL 2007-05-25, IEF 2002-07-22, AGG 2003-09-22.**

---

## 5. The sentence that must not be lost

**Choosing a data source does not upgrade "a backtest is possible" into "this is worth deploying."**
Even with the cleanest available data, this project still faces: under 20 years of SPY, under
15 years of AGG, 2–3 instruments, prior contamination from ~19 parameter searches run on related
instruments between 2026-08-28 and 2026-09-15, and roughly 0.6 %/yr of deterministic cost headwind.
Under those conditions no backtest constitutes strong marginal evidence. **"No candidate is worth
deploying" remains a fully qualified — and currently likely — conclusion.** This step should be
understood as making a rejection more credible, not as paving the way to deployment.
