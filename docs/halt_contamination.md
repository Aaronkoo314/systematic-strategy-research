# Every candidate and benchmark ran under a halt that never resumed

Status: **RECORD CORRECTED.** All three rejected candidates stay rejected, each on the
grounds that survive. The grounds that do not survive are withdrawn here, by name.

## 1. What happened

`src/risk/controls.py` implements the mandate's drawdown halt: at -8% from the
high-water mark the risk manager sets `halted=True`, `halt_kind="DRAWDOWN"`, blocks every
order that would increase exposure, lets risk-reducing orders through, and **waits for a
human `resume()`**. That is correct live behaviour. In a backtest no human ever calls
`resume()`, so after the first -8% drawdown every strategy in this project became
"sell when the target falls, never buy when it rises".

`docs/static_weight_correction.md` found and fixed this for the static-weight BENCHMARK.
It did not ask whether the CANDIDATES measured against that benchmark had run the same
way. They had. Read from `logs/experiment_log.jsonl` (the live log, not the earlier VOID
one) and confirmed by re-running V3:

| run | halted | orders blocked | realised weight | intended |
|---|---|---|---|---|
| V1 every training config (L1-L9) | True | 81,558-82,309 | 0.08-0.31 | 0.58-0.90 |
| V1 validation candidate (L12) | True | 36,191 | 0.71 | 0.90 |
| V1 final test candidate (L17) | True | 29,468 | 0.37 | - |
| V1 `buy_and_hold` comparator (L10) | True | 5,658 | 0.99 | 1.00 |
| V1 `static_0.71` comparator (L15) | True | 3,389 | 0.69 | 0.71 |
| V2 training configs (L25-L31) | True | 841-1,574 | 0.44-0.48 | 0.50 |
| V2 validation (L34, L43-46) | True | 99-104 | 0.089 | 0.50 |
| V3 35/65 QQQ/TLT, training, re-run as V3 ran it | True (DRAWDOWN) | 10 rebalance buys | - | - |
| V3 same, halts disabled | False | 0 | - | - |

V3's own log lines (L48-L76) do not carry a `halted` field, so it had to be re-run: the
as-run version made 8 fills and 8.54%/yr on training; with the halt disabled, 18 fills and
10.73%/yr. The halt cost that configuration 2.2%/yr and blocked more than half its orders.

An earlier correction (`logs/experiment_log_VOID_halt_bug.jsonl`) fixed the DAILY-loss
halt's missing expiry and re-ran. The re-run still contained the DRAWDOWN halt. One halt
was fixed and the other was not noticed, in the same file, in the same week.

## 2. What survives, candidate by candidate

The test is mechanical. A halt that blocks buys and permits sells can only **lower**
exposure after a drawdown begins. Therefore:

- any **drawdown** measured under the halt is a LOWER BOUND on the un-halted drawdown;
- any **return** measured under the halt is unreliable in either direction;
- any **comparison** between two halted runs is unreliable, because different rules are
  blocked at different moments and to different degrees.

**V1 volatility targeting.** Rejected on A9 (ex-ante power gate, `power_gate_result.md`)
and A2 (lost to a static blend at the same average weight). A9 is an ex-ante calculation
that never touched a backtest: **survives.** A2 compared a halted candidate to a halted
comparator, and volatility targeting wants to BUY precisely when volatility falls after a
drawdown - the moment the halt blocks it - while a static blend only needs to buy on
drift: asymmetric damage, **A2 withdrawn.** V1 remains rejected on A9 alone.

**V2 dip buying.** Rejected on A1 (training drawdown -33% to -36% breaches -20%) and on a
comparison ("worse drawdown than static 50% at a sixth the exposure"). A1's drawdowns are
lower bounds; the un-halted drawdowns are at least as deep: **A1 survives, strengthened.**
The "sixth the exposure" figure IS the halt (0.089 realised against 0.50 intended):
**comparison withdrawn.** V2 remains rejected on A1 alone.

**V3 stocks + Treasuries.** Rejected on the final test: -31.89% in 2022 when TLT lost
39.6%. A lower bound on the un-halted drawdown: **survives, strengthened.** The training
selection table (six configurations, L48-L53) that picked 35/65 is contaminated - every
row's return is wrong and every row's drawdown is a lower bound. The pick does not matter
to the verdict: whichever configuration had been chosen, its test-segment drawdown would
have been at least what was measured. **Selection table voided, verdict stands.**

**Static-weight benchmark.** Already corrected in `static_weight_correction.md`.

Nothing is un-rejected. What changes is what the record is allowed to SAY: not "timing
subtracted value" or "the dip buyer held a sixth the exposure and still drew down more",
because those sentences describe the risk manager, not the strategies.

## 3. Why it kept happening

Three times now a research result has measured the harness instead of the hypothesis:
the daily-loss halt with no expiry, the static benchmark under the drawdown halt, and
this. The common cause is structural: **a live-trading safety control was left active in a
research harness where the human it waits for does not exist.** Each time the run still
traded, still produced plausible curves, and still passed every test, because nothing
asserted that realised exposure tracked intended exposure.

The look-ahead leak had the same signature - an oracle returned 631x while 49 tests
passed - and was fixed by making the leak structurally impossible rather than by adding
a test. This needs the same treatment.

## 4. The fix that is required before any further run

1. **The engines must refuse to run a multi-year backtest with a never-resuming halt
   unless told to.** Concretely: `Backtester` and `PortfolioBacktester` raise unless
   either `bypass_risk_controls=True` (recorded in the summary, as now) or the
   `RiskManager` has an explicit research-mode auto-resume. Silence is not an option.
2. **Every summary must report `intended_weight_mean` next to `realised_weight_mean`**
   and flag any run where they differ by more than a stated tolerance. This is the
   assertion that would have caught all three incidents.
3. **`n_risk_blocked` must appear in every experiment-log line**, including the
   multi-asset path, which currently omits it.

Until 1-3 are in, no result produced by these engines may be quoted as a measurement of
a strategy.

## 5. Should V1-V3 be re-run un-halted?

No. Each remains rejected on a ground the halt cannot have manufactured, and re-running
would only refine numbers that do not change any verdict, at the cost of touching data
the frozen rules treat as consumed. The corrected record is the deliverable, not a new
set of curves.

## 6. Reproduce

```
python - <<'PY'
# see the halted flags directly
import json
for i, l in enumerate(open("logs/experiment_log.jsonl", encoding="utf-8"), 1):
    j = json.loads(l); s = j.get("summary", j)
    if "halted" in s: print(i, s.get("candidate"), s["halted"], s.get("n_risk_blocked"), s.get("avg_weight"))
PY
```
V3 re-run: the check script is described in section 1; it constructs `PortfolioBacktester`
exactly as `tools/run_experiment_v3.py` does, once with `RiskLimits(max_weight=1.0)` and
once with every drawdown and daily-loss limit set to 1.0.
