# Personal Quantitative Trading System — Stage A

**Current stage: A (investment mandate + account feasibility). Nothing is authorized to trade.**

`dry_run = true`, `live_enabled = false`. No order-placing code exists in this repository yet.

## What is here

```
docs/investment_mandate.md   Draft mandate: confirmed / provisional / unresolved (NOT approved)
docs/feasibility.md          Verified feasibility report with sources and verification dates
docs/selection_criteria.md   Stage B criteria, frozen before any candidate existed
docs/candidate_comparison.md Stage B verdict: all three candidates rejected
docs/data_sources.md         Data source evaluation: six of seven eliminated on licence or access
tools/probe_readonly.py      Read-only OpenD probe: connectivity, accounts, history quota
tools/probe_quotes.py        Read-only probe: market-data entitlement, account + position snapshot
tests/test_probe_is_readonly.py  Proves the probes contain no order/unlock calls
logs/redacted/*.json         Redacted probe output (raw logs are git-ignored)
tools/redact_logs.py         Strips balances, positions and identifiers from the raw logs
```

## Reproducing the Stage A evidence

Requires: Python 3.12, `moomoo_api` installed, moomoo OpenD running and logged in on
`127.0.0.1:11111`.

```bash
python tests/test_probe_is_readonly.py
python tools/probe_readonly.py
python tools/probe_quotes.py
```

Both probes are strictly read-only. They call only `get_global_state`, `get_history_kl_quota`,
`get_market_state`, `request_history_kline`, `subscribe`, `get_stock_quote`, `query_subscription`,
`request_trading_days`, `get_stock_basicinfo`, `get_acc_list`, `accinfo_query`,
`position_list_query`, `order_list_query`.

Account identifiers are masked in stdout and in the JSON summaries. No password, trading password,
or token is read, requested, or stored anywhere in this project.

## Verified environment (2026-09-15)

| | |
|---|---|
| Broker entity | Futu Singapore (`SecurityFirm.FUTUSG`) — confirmed from the API |
| Real account | MARGIN, USD (balances and positions redacted — not in this repo) |
| Paper account | `TrdEnv.SIMULATE`, US margin, limit + market orders only |
| OpenD | v1010, bound to loopback `127.0.0.1:11111`, `qot_logined` and `trd_logined` = True |
| SDK | `moomoo_api` 10.7.6708 |
| Market data | LV1 US quotes, daily + intraday bars, trading calendar — all working at zero cost |
| Fixed running cost today | USD 0.00 / year |

## Confirmed operating model (2026-09-15)

- **Every order is manually confirmed by the operator.** This system is **not unattended** and must
  never be described as such. No trading password is held by any background process.
- The trading portfolio shares a margin account with other holdings over which this project has
  no authority. See `investment_mandate.md` §7b for what that sharing does to the trading
  portfolio — including the finding that **the 20 % abandon point is not enforceable in
  trading-portfolio terms**.
- **No account balances, positions or identifiers are committed to this repository.** Raw probe
  logs are git-ignored; `logs/redacted/` holds capability-only copies produced by
  `tools/redact_logs.py`.
- Benchmarks: SPY, 60/40 SPY/IEF, and BIL, reported side by side.

## Stage gates

| Stage | Description | Status |
|---|---|---|
| A | Mandate + feasibility | complete |
| B | Strategy selection + frozen, preregistered research design | **NO CANDIDATE SELECTED** — all three rejected, 9/9 adversarial reviews fatal. See `candidate_comparison.md` |
| C | Implementation + historical validation + critical review | **NOT ENTERED** — blocked on the P0 account-isolation decision |
| D | Paper trading + operational validation (≥ 60 trading days) | blocked on C |
| E | Small-capital live pilot — **requires explicit written approval** | blocked on D |
