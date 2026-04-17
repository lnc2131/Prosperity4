# Research notes

Free-form log of findings, hypotheses, dead ends, and lessons.
Reverse-chronological (newest first).

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
