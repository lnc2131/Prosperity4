# Strategy idea backlog

Tag format: `- [ ] <short_name> — <one-line hypothesis> — <expected cost: cheap/med/expensive>`

## Pending (queue — take from the top)

- [ ] `pepper_ob_imbalance` — skew fair value by `(bid_vol - ask_vol)` to front-run directional flow — cheap
- [ ] `pepper_drift_aware_fv` — PEPPER drifts ~+1000/day, factor that into fair value during slow sessions — cheap
- [ ] `ash_hidden_pattern` — PDF hints ASH "may follow a hidden pattern"; try short-EMA deviation signal — medium
- [ ] `pepper_day0_diagnosis` — understand why D=0 PnL is 3x worse than D-1 / D-2 before touching code — cheap (analysis only)
- [ ] `bigger_quote_on_strong_edge` — scale quote size (not just take) when fair-price edge is large — medium
- [ ] `pepper_volatility_filter` — stop market-making PEPPER during high-std windows — medium
- [ ] `ash_asymmetric_take_width` — ASH micro-bias: larger take_width when long, smaller when short (or vice versa) — cheap
- [ ] `pepper_autocorrelation_scan` — measure return autocorrelation at lags 1–20; decide if momentum or reversion — cheap (analysis)

## In progress

_(move a single idea here when you start working on it; remove on completion)_

## Done — kept

- `baseline_mm_tuned_v1` — fixed-fair ASH + big-vol-mid PEPPER with grid-searched params. **PnL: 184,422.** Current champion.

## Done — rejected (lessons in NOTES.md)

_(none yet)_

## Ideation rules

- Every idea must be falsifiable in a backtest (not "vibes"-based).
- Prefer ideas that are quick to test over speculative ones — retire them fast.
- Record *why* an idea was rejected in NOTES.md so the same ground isn't re-covered.
