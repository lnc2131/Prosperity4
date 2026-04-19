# Research notes

Free-form log of findings, hypotheses, dead ends, and lessons.
Reverse-chronological (newest first).

---

## 2026-04-19 — Round 2 retune: PEPPER reversion_beta was actively harmful

Round 2 data added (3 days: D-1, D=0, D+1; ASH range 9979-10023, PEPPER drifts
+1000/day intraday — same pattern as R1). Same products, same 80-position
limits. Round 2 introduces the Market Access Fee (MAF) via `Trader.bid()`:
top 50% of bids across all teams get +25% quote flow on the live simulation,
bid is deducted from R2 profit only if accepted. Testing uses 80% of quotes
(no extra access), slightly randomized per submission.

**Current-champion baseline on R2 data**: 81,451 total (ASH 54k, PEPPER 27k),
with PEPPER **losing -15k on D+1**. Disaster.

**Root cause**: `reversion_beta = -0.229` predicted the market would revert
against recent returns. But PEPPER has a smooth +1000 intraday drift every
day — so negative beta bets *against* the trend and systematically gets
picked off. It worked acceptably on R1 only because R1 D-2/D-1 had noisier
moments the reversion caught by luck.

**Fix**: `reversion_beta = 0.0` (no prediction) + wider `take_width = 4`
(only cross when edge ≥4 ticks; filters adverse-selection noise) +
`default_edge = 3` + `clear_width = 1`. Sweeps around this are flat within
a few %, so the optimum is not razor-thin.

**Cross-validation**:

| Config              | R1 total | R2 total | R1 PEPPER | R2 PEPPER |
|---------------------|---------:|---------:|----------:|----------:|
| Previous champion   |  184,422 |   81,451 |   137,756 |    27,408 |
| R2 retune (new)     |  252,341 |  256,462 |   205,675 |   202,419 |
| Delta               |  +67,919 | +175,011 |   +67,919 |  +175,011 |

ASH is unchanged — the old ASH tuning still wins on both datasets (46,666 / 54,043).

**Interesting observation**: `take_width` 3→4 on PEPPER jumps PnL 60k→200k.
Sharp cliff. Hypothesis: many book-crossings at exactly 2-3 ticks are
"small liquidity takers getting picked off" — adverse flow. tw=4 skips
them. Worth a dedicated diagnosis session (see STATUS.md "Next up").

**Tooling**: bt.sh now reads `DATASET` env var (default round1). bench.py
takes `--dataset round2`. benchmarks.csv has `dataset` + `pnl_d+1` columns
appended; pre-existing rows still valid (default to round1 semantically).

---

## 2026-04-17 — Submission rejected for `import os`; switched to sidecar JSON

The Prosperity website grader rejected the first submission attempt with:

> Code submitted contains malicious statements — Code submitted violates rule
> `import\s*os` from forbidden patterns

Trader.py had `import os as _os` to read `TRADER_PARAMS` from the environment
(used by `gridsearch.py`). Removed entirely.

**New mechanism**: trader.py reads an optional `trader_params.json` sidecar
file located next to itself (via `pathlib.Path(__file__).resolve().parent`).
`bench.py` and `gridsearch.py` write that file before each run and delete it
afterwards. The sidecar is gitignored so it can never get committed and alter
the live submission's behaviour.

Verified post-fix:
- bench.py reproduces 184,422.50 exactly with no override.
- bench.py with `--params-json '{"ASH_COATED_OSMIUM":{"take_width":1}}'`
  changes ASH PnL 46,666 → 43,328, confirming the sidecar is being read.
- No leftover `trader_params.json` after either run (try/finally cleans up).

**Lesson**: the old `Env-var param injection works cleanly through PyO3` note
below is true *for the local backtester* but doesn't survive the grader.
Sidecar JSON works for both.

---

## 2026-04-17 — Baseline established, grid search infrastructure complete

**Champion**: `baseline_mm_tuned_v1`, PnL 184,422.

Grid search revealed the following about round 1:

### ASH_COATED_OSMIUM
- Stable around 10000 with tiny std (~5) across all three days.
- Higher `take_width` (3 vs 1) substantially helps — captures more crossing flow.
- `soft_position_limit=50` (i.e. minimal inventory skew) beats tighter limits;
  ASH inventory is low risk because the mean doesn't move.
- `default_edge` doesn't matter much in the 2–5 range.

### INTARIAN_PEPPER_ROOT
- Mean drifts +1000/day (D-2 → 10500, D-1 → 11500, D=0 → 12500).
- Intraday std ~289.
- `adverse_volume=10` (low) clearly beats 15–25. Translation: filtering out
  high-volume quotes was *removing* signal. Heavy quotes ARE the fair-price
  anchor; we should trust them.
- `reversion_beta=-0.229` stays best; positive values are catastrophic. Short-
  term reversion is real.
- **D=0 is weak** (19k vs 51k/67k). Worth investigating. Hypothesis: at higher
  price levels the absolute-value threshold logic may be producing fewer
  take opportunities. Needs data analysis.

### Framework observations
- Env-var param injection (`TRADER_PARAMS`) works cleanly through PyO3.
- Sequential grid runs at ~0.95s each; 96-combo sweep in ~90s.
- The backtester's stdout "TOTAL" and per-product tables are stable/parseable.

---
