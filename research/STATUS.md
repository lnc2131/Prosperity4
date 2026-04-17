# Research Status

**Claude: read this first every session. Update it as the last step before committing.**

---

## Current champion

- **File**: [Prosperity4/trader.py](../trader.py) (commit `85225a9`)
- **Round**: 1
- **Total PnL (round1 days -2, -1, 0)**: **184,422**
  - D-2: 66,208
  - D-1: 84,228
  - D=0: 33,986
- **Per-product**:
  - `ASH_COATED_OSMIUM`: 46,666
  - `INTARIAN_PEPPER_ROOT`: 137,756
- **Strategy label**: `baseline_mm_tuned_v1`
- **Snapshot**: [strategies/00_champion_baseline.py](strategies/00_champion_baseline.py)

## Currently investigating

_(nothing in progress — pick from "Next up" or ideate first)_

## Next up (in priority order)

1. **Ideation pass** — brainstorm 5–10 concrete strategies for round 1. Append to [ideas.md](ideas.md).
2. **Diagnose D=0 PEPPER weakness** — PEPPER earned only 19,236 on D=0 vs 51k/67k on other days. Read price CSV, find the regime change. Write findings to [NOTES.md](NOTES.md).
3. Pick the highest-expected-value idea from [ideas.md](ideas.md) and implement it as `strategies/NN_<name>.py`.

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
