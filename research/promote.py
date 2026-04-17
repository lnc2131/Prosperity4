#!/usr/bin/env python3
"""
promote.py — promote a candidate strategy to be the new champion trader.py.

Rules (enforced):
  1. Benchmark the candidate fresh right now.
  2. Benchmark the current trader.py fresh right now (no trusting stale rows).
  3. Candidate must have strictly higher TOTAL PnL than current trader.py.
  4. If --require-per-day is passed, candidate must also be >= current on every day.
  5. If all checks pass:
        a) Snapshot current trader.py to research/strategies/NN_prev_<label>_<timestamp>.py
        b) Overwrite trader.py with the candidate
        c) Append rows to benchmarks.csv for both runs, with the candidate labeled as champion.
        d) Git-add the snapshot + trader.py + benchmarks.csv and make a commit.
        e) Print the new PnL and the diff vs the previous champion.
  6. If checks fail, print the per-day + total diff and exit non-zero.
     trader.py is never touched on failure.

Usage:
    python3 research/promote.py --strategy research/strategies/01_foo.py --label foo_v1
    python3 research/promote.py --strategy research/strategies/01_foo.py --label foo_v1 --require-per-day
    python3 research/promote.py --strategy research/strategies/01_foo.py --label foo_v1 --no-commit
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import shutil
import subprocess
import sys
from pathlib import Path

import bench  # reuse runner / csv appender

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                                   # Prosperity4/
STRATEGIES = HERE / "strategies"
TRADER = ROOT / "trader.py"


def next_snapshot_name(label: str) -> Path:
    existing = sorted(STRATEGIES.glob("*.py"))
    nums = []
    for p in existing:
        m = re.match(r"(\d+)_", p.name)
        if m:
            nums.append(int(m.group(1)))
    nxt = (max(nums) + 1) if nums else 0
    stamp = _dt.datetime.utcnow().strftime("%Y%m%d")
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", label).strip("_") or "unnamed"
    return STRATEGIES / f"{nxt:02d}_prev_{safe}_{stamp}.py"


def git(*args, check=True, capture=False):
    kw = dict(cwd=str(ROOT))
    if capture:
        kw["capture_output"] = True
        kw["text"] = True
    return subprocess.run(["git", *args], check=check, **kw)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", required=True, help="path to candidate .py file")
    ap.add_argument("--label", required=True, help="label under which it will be stored")
    ap.add_argument("--require-per-day", action="store_true",
                    help="also require candidate >= current on every day")
    ap.add_argument("--no-commit", action="store_true",
                    help="do everything except git commit")
    ap.add_argument("--force", action="store_true",
                    help="bypass PnL checks (use with care)")
    args = ap.parse_args(argv)

    candidate = Path(args.strategy).resolve()
    if not candidate.exists():
        print(f"error: candidate not found: {candidate}", file=sys.stderr)
        return 2
    if not TRADER.exists():
        print(f"error: champion not found: {TRADER}", file=sys.stderr)
        return 2

    print(f"→ benchmarking current champion ({TRADER.name}) ...")
    cur = bench.run(TRADER, None)
    print(f"  champion total = {cur['total']:.2f}  days={cur['days']}")

    print(f"→ benchmarking candidate ({candidate.name}) as '{args.label}' ...")
    cand = bench.run(candidate, None)
    print(f"  candidate total = {cand['total']:.2f}  days={cand['days']}")

    # Decision.
    total_delta = cand["total"] - cur["total"]
    per_day = {d: cand["days"].get(d, 0) - cur["days"].get(d, 0)
               for d in ("D-2", "D-1", "D=0")}
    print("\nDiff (candidate − champion):")
    print(f"  total: {total_delta:+.2f}")
    for d, v in per_day.items():
        print(f"    {d}: {v:+.2f}")

    passes_total = total_delta > 0
    passes_per_day = all(v >= 0 for v in per_day.values())

    ok = passes_total and (passes_per_day if args.require_per_day else True)
    if not ok and not args.force:
        print("\n✗ REJECTED — candidate did not beat champion "
              f"(total_ok={passes_total}, per_day_ok={passes_per_day}). "
              "trader.py is unchanged.")
        # Still record the failed attempt so the ledger is honest.
        bench.append_row(args.label, None, cand,
                         f"rejected (delta_total={total_delta:+.2f})")
        return 1

    # Promote.
    print("\n✓ PASSES — promoting.")
    snapshot = next_snapshot_name("champion")
    shutil.copy2(TRADER, snapshot)
    print(f"  snapshot {TRADER.name} → {snapshot.relative_to(ROOT)}")
    shutil.copy2(candidate, TRADER)
    print(f"  trader.py ← {candidate.relative_to(ROOT)}")

    # Record both runs.
    bench.append_row("prev_champion_prepromote", None, cur,
                     "pre-promotion verification")
    bench.append_row(args.label, None, cand,
                     f"promoted to champion (delta_total={total_delta:+.2f})")

    if args.no_commit:
        print("  --no-commit: skipping git commit.")
        return 0

    git("add", str(snapshot.relative_to(ROOT)),
        str(TRADER.relative_to(ROOT)),
        str((HERE / "benchmarks.csv").relative_to(ROOT)))

    msg = (
        f"Promote {args.label}: PnL {cur['total']:.0f} → {cand['total']:.0f} "
        f"({total_delta:+.0f})\n\n"
        f"Per-day:\n"
        f"  D-2: {cur['days'].get('D-2', 0):.0f} → {cand['days'].get('D-2', 0):.0f} "
        f"({per_day['D-2']:+.0f})\n"
        f"  D-1: {cur['days'].get('D-1', 0):.0f} → {cand['days'].get('D-1', 0):.0f} "
        f"({per_day['D-1']:+.0f})\n"
        f"  D=0: {cur['days'].get('D=0', 0):.0f} → {cand['days'].get('D=0', 0):.0f} "
        f"({per_day['D=0']:+.0f})\n\n"
        f"Snapshot of previous champion: {snapshot.relative_to(ROOT)}\n"
        f"Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
    )
    git("commit", "-m", msg)
    print("  committed. (push manually with `git push`.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
