# Research Status

**Claude: read this first every session. Update it as the last step before committing.**

---

## Current champion

- **File**: [Prosperity4/trader.py](../trader.py)
- **Round**: 2 (live); also validated on round 1
- **Strategy label**: `r2_retune` (PEPPER: beta=0, tw=4, de=3, cw=1)
- **Snapshot**: [strategies/01_r2_retune.py](strategies/01_r2_retune.py)

| Dataset | Total | ASH | PEPPER | Per-day |
|---|---|---|---|---|
| round1 | **252,341** | 46,666 | 205,675 | D-2=70,280 / D-1=93,646 / D=0=88,415 |
| round2 | **256,462** | 54,043 | 202,419 | D-1=87,252 / D=0=85,511 / D+1=83,699 |

Beats the prior champion (`baseline_mm_tuned_v1`) by +68k on R1 and +175k on R2.

## Round 2 additions

- **`bid()` returns 5000** — Market Access Fee bid. One-time fee, subtracted
  from R2 profit only if we end up in the top 50% of bids across all teams.
  Rationale in the code comment on `Trader.bid`.
- **`bench.py --dataset round2`** — run against round 2 data. `benchmarks.csv`
  now has a `dataset` column and a `pnl_d+1` column appended on the right.

## Currently investigating

_(nothing in progress — pick from "Next up" or ideate first)_

## Next up (in priority order)

1. **Decide final MAF bid**. 5000 is a placeholder. See code comment on
   `Trader.bid`. Pick a value before final submission.
2. **Manual "Invest & Expand"** — 50k budget across Research/Scale/Speed,
   submitted separately on the website (NOT in trader.py). PnL formula:
   `(research(r) × scale(s) × speed_rank) − budget_used`. Think through
   the optimization.
3. **Diagnose why PEPPER `take_width=4` works so well** — sharp cliff
   between tw=3 (60k) and tw=4 (200k). Likely adverse-selection; verify
   by inspecting which orders we *used* to take at tw=2 but *don't* at tw=4.
4. **Ideate new R2 strategies** — signals we haven't exploited (orderflow
   imbalance, trade-print features, drift-aware fair value).

## Standard loop (every session)

```
1. Read STATUS.md, tail of benchmarks.csv, ideas.md.
2. Do ONE of:
     a) Ideate     → append to ideas.md
     b) Implement  → new strategies/NN_<name>.py + grids/NN_<name>.json
     c) Benchmark  → python3 research/bench.py --trader <path> --label <name>
     d) Grid       → python3 gridsearch.py ... (add results to NOTES.md)
     e) Promote    → python3 research/promote.py --strategy <path> --label <name>
     f) Reject     → mark idea done, add lessons to NOTES.md
3. Update this STATUS.md to reflect what's done and what's next.
4. git commit + push.
```

## Invariants — do not violate

- **Never replace `trader.py` without a benchmarks.csv row proving it beats the current champion on total PnL.** Use `promote.py`; it enforces this.
- **`benchmarks.csv` is append-only.** Never rewrite rows.
- **Commit + push after every meaningful step** so any session can resume from any point.
- **One in-flight idea at a time** under "Currently investigating". If interrupted, leave it there for the next session to pick up.
- **Never put `import os` in `trader.py`.** The Prosperity grader rejects it ("forbidden pattern `import\s*os`"). Param overrides go through a `trader_params.json` sidecar (gitignored) read via `pathlib` + `open()`. `bench.py` and `gridsearch.py` write/delete that sidecar around each run.

## Resume command

When starting a session, paste:

> "Read `Prosperity4/research/STATUS.md` and continue from where we left off. Commit + push whenever you finish a meaningful step."
