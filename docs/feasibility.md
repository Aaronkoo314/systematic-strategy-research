# Feasibility Report — moomoo OpenD, account and technical environment

**Stage:** A
**Report date:** 2026-09-15 (Asia/Singapore)
**Verification methods:** (a) live read-only API probes against the OpenD instance running on this
machine, (b) official moomoo / moomoo OpenAPI documentation fetched on 2026-09-15.

Evidence files:
- `logs/probe_20260915T082316414974+0000.json` — connectivity, account discovery, history quota
- `logs/probe_quotes_20260915T082758650618+0000.json` — market-data entitlement, account snapshot
- Probe source: `tools/probe_readonly.py`, `tools/probe_quotes.py` (read-only; enforced by `tests/test_probe_is_readonly.py`)

> **Read-only guarantee.** Neither probe calls `place_order`, `modify_order`, `unlock_trade`, or any
> other write API. No order was submitted and no account setting was changed.

---

## 1. Local environment (verified by direct inspection, 2026-09-15)

| Item | Observed value | Method |
|---|---|---|
| OS | Microsoft Windows 11 Home 10.0.22631 | `Get-CimInstance Win32_OperatingSystem` |
| CPU / RAM | Intel Core Ultra 7 155H / 31.6 GB | `Get-CimInstance` |
| Free disk | C: 12.8 GB free; D: 202.7 GB free | `Get-PSDrive` |
| Python | 3.12.3 at `D:\Software\Python\python.exe` | `python --version` |
| Git | 2.55.0.windows.3 | `git --version` |
| moomoo SDK | `moomoo_api` **10.7.6708** (`moomoo.__version__` = `10.07.6708`) | `pip list`, import |
| Other quant libs present | `backtrader 1.9.78.123`, `pandas 2.2.2`, `numpy 2.0.0` | `pip list` |
| OpenD | `moomoo_OpenD.exe` running, PID 13088, started 2026-09-15 13:47:40, path `%APPDATA%\moomoo_OpenD\moomoo_OpenD.exe` | `Get-Process` |
| OpenD listener | `127.0.0.1:11111` LISTEN (loopback only — **not** exposed to LAN/internet) | `Get-NetTCPConnection` |

**Note (positive finding):** OpenD is bound to `127.0.0.1`, not `0.0.0.0`. This already satisfies the
guardrail "do not expose OpenD to the public internet". Any future change to `0.0.0.0` must be
treated as a security change requiring explicit review.

---

## 2. Connectivity and session state (verified 2026-09-15 08:23 UTC / 16:23 SGT)

`OpenQuoteContext.get_global_state()` returned:

```
{'market_us': 'PRE_MARKET_BEGIN', 'market_hk': 'CLOSED', 'market_sg': 'AFTERNOON',
 'server_ver': '1010', 'trd_logined': True, 'qot_logined': True,
 'program_status_type': 'READY', 'program_status_desc': '', 'timestamp': '1789460597'}
```

- `qot_logined: True` and `trd_logined: True` → the OpenD session is authenticated for **both**
  quotation and trading at the time of the probe.
- `program_status_type: READY` → OpenD is serving requests.

**Not yet verified:** how long this session survives without manual intervention (overnight, on
laptop sleep/hibernate, after a Windows update reboot). This is the single biggest operational
unknown and is addressed in the open questions.

---

## 3. Brokerage entity and accounts (verified — this is hard evidence, not inference)

`get_acc_list()` was called across all seven `SecurityFirm` values and three market filters.
Account identifiers below are masked.

| Entity | Account | Env | Type | Markets authorised |
|---|---|---|---|---|
| **FUTUSG** (Futu Singapore / Moomoo Financial Singapore) | `[REDACTED]` | **REAL** | **MARGIN** | HK, US, HKCC, SG, HKFUND, SGFUND, USFUND, JP |
| (universal account present) | `[REDACTED]` | — | — | — |
| — | `[REDACTED]` | SIMULATE | MARGIN | US (`sim_acc_type: STOCK_AND_OPTION`) |
| — | `[REDACTED]` | SIMULATE | CASH | HK (`sim_acc_type: STOCK`) |

Findings:

1. **The live brokerage entity is Futu Singapore (`security_firm: FUTUSG`), confirmed by the API
   itself.** No US (`FUTUINC`), AU, MY, JP or CA *real* account exists under this moomoo ID — those
   firm/market combinations returned only the shared simulated accounts.
2. **The real account is a MARGIN account, not a cash account.** This does not force the use of
   leverage, but it means buying power can exceed settled cash and short sales are permitted at the
   account level. The Stage-A guardrail "no margin borrowing, no short selling" must therefore be
   enforced *by our software*, because the broker will not enforce it for us.
3. **Paper trading is reachable through the API** (`TrdEnv.SIMULATE`, US margin account), which
   satisfies the Goal-9 requirement for a paper stage. Its funding is simulated: `total_assets`
   1,000,000 with `power` 2,000,000 — i.e. the paper account is a 2× margin US stock+option account
   with USD 1,000,000, **not** a mirror of the real account. Paper-stage results must therefore be
   position-sized to the intended real capital in software, not left at the paper default.

---

## 4. Real account state — **REDACTED**

A read-only snapshot of the live account was taken on 2026-09-15 via `accinfo_query`,
`position_list_query` and `order_list_query`. **All balances, buying power, margin figures and
open positions are deliberately excluded from this repository**, together with the raw probe logs
that contain them (see `.gitignore`). Redacted copies of the logs are committed under
`logs/redacted/` and preserve only capability evidence.

The design consequences that the rest of this project depends on, stated without account specifics:

1. **The trading portfolio is a carve-out, not the whole account.** The notional USD 10,000 sleeve
   shares one margin account with other holdings outside this system's authority, so unencumbered
   cash equal to the sleeve is not guaranteed at any moment. A pre-trade check against *actual
   settled cash attributable to the trading portfolio* is mandatory before any live order.
2. **The broker enforces none of the v1 guardrails.** Long-only and no-leverage apply to the sleeve,
   and *our software* must enforce them — the broker will not.
3. **The account is MARGIN, not CASH.** `power` (buying power) did not equal `cash` in the snapshot.
   Buying power is therefore **not** a safe proxy for available cash and must never be used for
   position sizing.
4. **Other holdings dominate account-level risk.** Any systematic sleeve added on top would have
   its account-level risk driven by those holdings rather than by its own signals, so the two
   sleeves must be separated explicitly before any portfolio-level limit means anything.
5. **`risk_status` returned a broker-specific level** whose meaning is not documented in the
   OpenAPI reference. It should be read in-app rather than assumed benign.

Open orders at probe time: none, in both REAL and SIMULATE.

## 5. Market-data entitlement through the API (verified 2026-09-15)

| Capability | Result | Evidence |
|---|---|---|
| Real-time US quote subscription | **Works.** `subscribe(['US.SPY','US.IEF','US.BIL'], SubType.QUOTE)` → `RET_OK` | probe #2 |
| Quote retrieval | **Works.** SPY last 760.88, IEF 90.93, BIL 91.50 (data_date 2026-09-14, i.e. prior US close — probe ran during US pre-market) | probe #2 |
| Subscription quota | **300 total**, 3 used, 297 remaining (→ Tier 2, ≥ 10,000 HKD assets) | `query_subscription` |
| Option quota | 60 | `query_subscription` |
| Order-book (LV2) subscribe | Call **accepted** (`RET_OK`). Depth *content* not verified — market was closed. Do not yet claim LV2 depth is entitled. | probe #2 |
| Daily candles | **Works**, `AuType.QFQ` (forward-adjusted) available | probe #1 |
| 1-min / 5-min candles | **Works** (SPY 2026-09-10 09:31 ET onwards retrieved) | probe #2 |
| Historical candle quota | **300 total**, 291 remaining. Rule: 1 quota per *new* symbol; repeats within 7 days are free | `get_history_kl_quota` + docs |
| Trading calendar | **Works** — `request_trading_days(US)` returns session dates and `WHOLE`/half-day type | probe #2 |
| Static instrument info | **Works but unusable for point-in-time universe construction** — see below | probe #2 |

### 5a. Two data limitations that change the research design

**(i) Daily history is short and inconsistent.** Earliest daily bar returned:

| Symbol | Earliest daily bar from moomoo | Actual inception |
|---|---|---|
| US.SPY | **2006-09-01** | 1993-01-22 |
| US.AGG | **2012-01-03** | 2003-09-22 |

moomoo's history therefore excludes the 2000–2002 bear market entirely, and for AGG excludes 2008.
A ~20-year SPY window does include 2008, 2018, 2020 and 2022, which is usable — but **moomoo data
alone cannot support a claim about behaviour across "different market environments" for every
instrument**, and per-symbol start dates differ, which silently biases any cross-sectional ranking.
Stage B must decide on a second, longer, traceable price source for research, keeping moomoo for
execution. (Not decided here — it is a cost/licensing decision needing your input.)

**(ii) `listing_date` is unusable.** `get_stock_basicinfo` returned `listing_date: '1970-01-01'` for
both SPY and IEF. Consequently **moomoo cannot be used to establish whether an instrument existed at
a historical decision date**, which is exactly what Goal 5 requires to avoid survivorship and
look-ahead bias. A separate listing-date source is required for any strategy with a changing
universe. A strategy with a small, hand-fixed, pre-1995-inception universe sidesteps this — at the
cost of admitting the universe itself was chosen with hindsight.

---

## 6. Trading capability through the API

| Item | Finding | Source |
|---|---|---|
| Entities supported for API trading | "FUTU HK, Moomoo US, Moomoo SG, Moomoo AU, Moomoo CA, Moomoo MY, Moomoo JP" — **Moomoo SG is supported** | [trade doc](https://openapi.moomoo.com/moomoo-api-doc/en/trade/trade.html), fetched 2026-09-15 |
| Unlock required before any trade API | `unlock_trade(password=..., password_md5=..., is_unlock=True)` — SDK docstring: *"all trading APIs require a successful unlock before they can be operated"* | installed SDK 10.7.6708, `inspect.signature` |
| Order types in SDK | `NORMAL` (limit), `MARKET`, `ABSOLUTE_LIMIT`, `STOP`, `STOP_LIMIT`, `TRAILING_STOP`, `TRAILING_STOP_LIMIT`, `TWAP`, `VWAP`, `AUCTION`, … | SDK `OrderType` enum |
| Order types in **paper** trading | **"Paper trade only supports limit orders (NORMAL) and market orders (MARKET)."** | [trade doc](https://openapi.moomoo.com/moomoo-api-doc/en/trade/trade.html) |
| Order modification, US market | **"US market currently only supports ModifyOrderOp_Normal and ModifyOrderOp_Cancel"** | [trade doc](https://openapi.moomoo.com/moomoo-api-doc/en/trade/trade.html) |
| Time in force | `DAY`, `GTC`, `GTD`, `IOC` | SDK `TimeInForce` enum |
| Extended hours | `fill_outside_rth` parameter exists on `place_order` | SDK signature |
| Lot size, US ETFs | 1 share (SPY, IEF) | `get_stock_basicinfo` |
| Fractional shares | Offered by moomoo SG at a different fee basis (0.99 % of value, max $0.99) — **API support not verified** | fee page; **unverified for API** |
| Generic rate limit | "A maximum of 60 requests every 30 seconds" given as an *example* for snapshot; "frequency limitation rules for each API are different" | [authority doc](https://openapi.moomoo.com/moomoo-api-doc/en/intro/authority.html) |
| Order-placement rate limit | **Not found in documentation.** Must be treated as unknown and rate-limited conservatively in our code. | — |

**Design consequence:** because paper trading supports only `NORMAL` and `MARKET`, the strategy's
order type must be limited to those two if we want the paper stage to be a faithful rehearsal of
live. Any design relying on broker-side `STOP` / `TRAILING_STOP` orders **cannot be validated in
paper trading** and is therefore ruled out for version 1.

---

## 7. Cost model (moomoo Singapore, US stocks/ETFs) — official schedule, 2026-09-15

Source: [moomoo SG — U.S. Stocks, ETFs & Fractional Shares Fees](https://www.moomoo.com/sg/support/topic5_76?lang=en-us)

| Charge | Rate | Applies |
|---|---|---|
| Commission | **USD 0** | eligible SG clients |
| Platform fee | **USD 0.99 per order** | buy and sell |
| GST | **9 %** on commission/platform/clearing fees | since 2024-01-01 |
| Settlement fee | USD 0.003 per share, max 1 % of order value | buy and sell |
| SEC fee | 0.0000206 × value, min USD 0.01 | **sell only**, resumed 2026-04-04 |
| FINRA TAF | USD 0.000195 per share, min 0.01, max 9.79 | **sell only**, revised 2026-02-07 |
| CAT fee | USD 0.000003 per share (NMS) | since 2025-05-25 |
| Algo-order surcharge | +0.05 % of value | **avoid TWAP/VWAP order types** |

### Illustrative arithmetic (not a backtest result)

Platform fee including GST = 0.99 × 1.09 = **USD 1.0791 per order**.

Round trip, 2 shares of SPY at ≈ 760 (order value ≈ USD 1,521):

- Buy: 1.0791 + (2 × 0.003) + CAT ≈ **USD 1.085**
- Sell: 1.0791 + 0.006 + SEC max(0.01, 0.0313) + TAF max(0.01, 0.00039) + CAT ≈ **USD 1.127**
- **Round trip ≈ USD 2.21 ≈ 0.145 % of the traded value.**

Because the dominant term is a *fixed* USD 1.079 per order, cost drag scales inversely with
position size. Annual platform-fee drag at 9 % GST:

| Orders / year | Fee cost | Drag on USD 2,000 | Drag on USD 10,000 (notional TP) |
|---|---|---|---|
| 12 (6 round trips, 1 instrument) | 12.95 | **0.65 %** | 0.13 % |
| 24 (monthly 2-asset switch) | 25.90 | **1.30 %** | 0.26 % |
| 120 (5 holdings, monthly rebalance) | 129.49 | **6.47 %** | 1.29 % |
| 500 (intraday / frequent) | 539.55 | **27.0 %** | 5.40 % |

**This is the most important economic constraint discovered in Stage A.** At the proposed USD 2,000
pilot size, anything beyond roughly one or two instruments rebalanced monthly is dead on arrival
before a single signal is evaluated. Any candidate strategy in Stage B must be judged against this
table first.

Bid-ask spread on SPY/IEF/BIL is ≈ 1 cent (~0.001–0.01 %) and is negligible next to the fixed fee.

---

## 8. Tax — flagged, **not** resolved

| Item | Status |
|---|---|
| Singapore capital gains tax | Singapore does not levy a general capital gains tax. **Assumption, not verified for your circumstances** — trading frequency can, in principle, cause gains to be treated as trading income. Not a question I can settle; it needs a Singapore tax professional if the account is traded actively. |
| US dividend withholding | **30 %** on US-source dividends for Singapore residents; there is **no US–Singapore income tax treaty**, so W-8BEN cannot reduce it (it only certifies non-US status). Sources: [Syfe](https://www.syfe.com/magazine/us-withholding-tax-dividends-singapore-investor-guide/), [StashAway](https://www.stashaway.sg/r/dividend-withholding-tax-estate-tax-us-equities-singapore), [Endowus](https://endowus.com/insights/an-inconvenient-truth-tax-on-us-listed-etfs-04c7532c5d) |
| Effect on a US-ETF strategy | SPY yields roughly 1.1–1.2 % → ≈ **0.33–0.36 % / year** of permanent withholding drag while held. This is comparable in size to the entire fee budget and must appear in the cost model. |
| Interest-related dividends (QII) on US T-bill ETFs (BIL/SGOV) | Potentially exempt from the 30 % — **could not verify**, and it depends on annual issuer designation plus broker implementation. Treat as **unresolved**; do not assume the exemption. |
| US estate tax on US-situs assets | Applies above USD 60,000 for non-resident aliens. Below that at current size, but flagged. |
| Your tax residency | **Unconfirmed.** The brokerage entity is Futu SG; that does *not* establish your tax residency. |

Nothing above is tax advice; it is a list of cost items to verify.

---

## 9. Operational feasibility — open risks

| Risk | Status |
|---|---|
| OpenD supported OS | Windows, macOS, CentOS, Ubuntu ([doc](https://openapi.moomoo.com/moomoo-api-doc/en/quick/opend-base.html)). Windows 11 is supported. |
| Session persistence | **UNVERIFIED.** The docs do not state re-login frequency, session timeout, or device-verification behaviour. Observed: session was live and `trd_logined: True` after ~2.6 h of uptime. Longer-horizon behaviour must be measured, not assumed. |
| Laptop availability at US close | US regular close 16:00 ET = **04:00 SGT** (05:00 SGT during SG-vs-US DST offset changes). A daily-close strategy requires the machine awake and online in the early hours, or a decision to trade at the open instead. **Unresolved — see question 5.** |
| Hosting alternative | Renting a VPS would remove laptop dependence but adds cost and an OpenD login on a remote machine. **Not recommended yet** — no capability gap has been proven that justifies spending money. |
| Trade unlock | Real trading requires `unlock_trade` with the trading password each OpenD session. An unattended system therefore needs the password available to the process → a secrets-handling design decision for Stage C. **Never to be placed in chat, source, or config.** |
| C: drive free space | 12.8 GB. Low. Keep the project and data on D:. |

---

## 10. Prior work found on this machine (disclosure, not yet reviewed)

`D:\Quant` exists and contains an in-progress system: `live_daily.py`, `live_intraday.py`,
`strategies/{moving_average,daily_reversion,backtest,params}.py`, plus ~19 result folders including
`optimization_*`, `walk_forward_*`, `intraday_factors_*`, and per-symbol walk-forward /
fixed-out-of-sample runs (symbol names redacted).
`config.json` contains no credentials (checked: no `password`/`secret`/`token`/`api_key` keys) —
good. Its parameters describe an intraday MA-cross + VWAP strategy and a daily mean-reversion
strategy on a single symbol.

The historical-candle quota log also shows recent research downloads of several single names and
**two 3× leveraged ETFs** on 2026-09-14/15. The specific symbols are redacted here; they are
recorded in the operator's local, git-ignored copy.

Two things follow, and both need your decision (question 6):

1. Leveraged ETFs and intraday trading are **excluded by the project's own first-version guardrails**.
2. More importantly for research integrity: a directory of ~19 optimisation and walk-forward runs
   over the same few symbols represents **prior search that already consumed part of the
   multiple-testing budget**. If we later test a similar idea on the same data and call it
   out-of-sample, that claim would be false. I have not opened those result files. I need to know
   whether to (a) formally review and log them as prior experiments, or (b) start from a clean
   hypothesis on data/instruments not yet searched.

---

## 11. Feasibility verdict

| Question | Verdict |
|---|---|
| Can we connect to OpenD and read data and account state? | **YES — demonstrated, with logs.** |
| Is the brokerage entity confirmed? | **YES — Futu Singapore (FUTUSG), from the API.** |
| Is API trading supported for this entity? | **YES per official docs; not tested (no write calls made).** |
| Is paper trading reachable via API? | **YES — `TrdEnv.SIMULATE`, US margin account, limit + market orders only.** |
| Is the required market data available free? | **YES for LV1 US quotes, daily and intraday bars, calendar — no subscription purchase needed.** |
| Is the *historical* data adequate for honest validation? | **PARTIALLY — 2006+ for SPY, 2012+ for AGG, and `listing_date` is unusable. A second research data source is likely required.** |
| Is the full notional sleeve available as settled cash at any given moment? | **NOT GUARANTEED — the sleeve shares an account with other holdings; a settled-cash check precedes any live order. See §4.** |
| Can the system run unattended today? | **NO — unproven session persistence, laptop-dependent, trade-unlock secret handling undesigned.** |

**No hard blocker to proceeding to Stage B.** The blockers are decisions, not capabilities.
