#!/usr/bin/env python3
"""
gridsearch.py — parameter sweep for trader.py against the Rust backtester.

Flow per combo:
  1. serialize parameter overrides to JSON.
  2. run ./bt.sh with TRADER_PARAMS=<json> (the trader reads the env var in __init__).
  3. parse the backtester stdout for per-day PnL + per-product PnL.
  4. keep the best combos and print a leaderboard.

Usage:
    python3 gridsearch.py ash            # sweep only ASH_COATED_OSMIUM params
    python3 gridsearch.py pepper         # sweep only INTARIAN_PEPPER_ROOT params
    python3 gridsearch.py both           # sweep one product at a time (fast)
    python3 gridsearch.py joint          # full cartesian product (slow, but thorough)
    python3 gridsearch.py --top 20 ash   # show top 20 instead of default 10

Outputs:
  - sorted leaderboard to stdout
  - gridsearch_results_<product>.csv   (every combo + result)
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


HERE = Path(__file__).resolve().parent
BT = HERE / "bt.sh"
TRADER = HERE / "trader.py"
SIDECAR = HERE / "trader_params.json"  # written per-combo, deleted after

# Current baseline defaults — used when a product is NOT being swept so the
# other product's performance doesn't drift between runs.
DEFAULTS = {
    "ASH_COATED_OSMIUM": {
        "fair_value": 10000,
        "take_width": 1,
        "clear_width": 0,
        "disregard_edge": 1,
        "join_edge": 2,
        "default_edge": 4,
        "soft_position_limit": 40,
    },
    "INTARIAN_PEPPER_ROOT": {
        "take_width": 1,
        "clear_width": 0,
        "prevent_adverse": True,
        "adverse_volume": 15,
        "reversion_beta": -0.229,
        "disregard_edge": 1,
        "join_edge": 0,
        "default_edge": 1,
    },
}

# ---------------------------------------------------------------------------
# GRID DEFINITIONS — edit these freely.  Values are lists to sweep.
# ---------------------------------------------------------------------------
GRIDS: Dict[str, Dict[str, list]] = {
    "ASH_COATED_OSMIUM": {
        "take_width":          [1, 2, 3],
        "clear_width":         [0, 1],
        "default_edge":        [2, 3, 4, 5],
        "soft_position_limit": [20, 30, 40, 50],
    },
    "INTARIAN_PEPPER_ROOT": {
        "take_width":      [1, 2],
        "adverse_volume":  [10, 15, 20, 25],
        "reversion_beta":  [-0.5, -0.229, 0.0, 0.229],
        "default_edge":    [1, 2],
    },
}


# ---------------------------------------------------------------------------
# Backtester invocation + stdout parsing
# ---------------------------------------------------------------------------

_TOTAL_RE = re.compile(r"^TOTAL\s+-\s+\d+\s+\d+\s+(-?\d+\.\d+)", re.MULTILINE)
_DAY_RE = re.compile(
    r"^(D-2|D-1|D=0)\s+(-?\d+)\s+\d+\s+\d+\s+(-?\d+\.\d+)", re.MULTILINE
)
# Product row, e.g. "INTARIAN_PEPPER_ROOT   35356.00   65526.00    1623.00  102505.00"
_PRODUCT_RE = re.compile(
    r"^([A-Z_][A-Z_0-9]+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)",
    re.MULTILINE,
)


def run_backtest(params_override: Dict[str, Dict]) -> Dict:
    """Run one backtest with the given param override; parse PnL.

    Writes a `trader_params.json` sidecar next to trader.py (the trader reads
    it in __init__), runs bt.sh, and removes the sidecar afterwards. We do not
    use env vars because the Prosperity grader rejects `import os` in trader.py.
    """
    env = os.environ.copy()
    SIDECAR.write_text(json.dumps(params_override))
    try:
        proc = subprocess.run(
            [str(BT), "--artifact-mode", "none"],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        try:
            SIDECAR.unlink()
        except FileNotFoundError:
            pass
    out = proc.stdout + proc.stderr
    total_match = _TOTAL_RE.search(out)
    if not total_match:
        raise RuntimeError("couldn't parse backtester output:\n" + out[-800:])
    total = float(total_match.group(1))
    days = {label: float(pnl) for label, _, pnl in _DAY_RE.findall(out)}
    products = {
        m[0]: {"D-2": float(m[1]), "D-1": float(m[2]), "D=0": float(m[3]), "TOTAL": float(m[4])}
        for m in _PRODUCT_RE.findall(out)
    }
    return {"total": total, "days": days, "products": products}


# ---------------------------------------------------------------------------
# Grid helpers
# ---------------------------------------------------------------------------

def iter_grid(grid: Dict[str, list]) -> Iterable[Dict]:
    keys = list(grid)
    for combo in itertools.product(*(grid[k] for k in keys)):
        yield dict(zip(keys, combo))


def sweep_product(product: str, top_n: int = 10) -> List[Tuple[Dict, Dict]]:
    """Sweep ONE product, keeping other defaults fixed. Return sorted results."""
    grid = GRIDS[product]
    combos = list(iter_grid(grid))
    print(f"\n=== Sweeping {product} : {len(combos)} combos ===")
    results: List[Tuple[Dict, Dict]] = []
    t0 = time.time()
    for i, combo in enumerate(combos, 1):
        override = {product: combo}
        try:
            metrics = run_backtest(override)
        except Exception as e:
            print(f"  [{i:>3}/{len(combos)}] ERROR: {e}")
            continue
        results.append((combo, metrics))
        key_score = metrics["products"].get(product, {}).get("TOTAL",
                                                             metrics["total"])
        print(f"  [{i:>3}/{len(combos)}] {product}_pnl={key_score:>9.0f}  "
              f"total={metrics['total']:>9.0f}  {combo}")
    elapsed = time.time() - t0
    print(f"=== {len(combos)} runs in {elapsed:.1f}s "
          f"({elapsed/max(len(combos),1):.2f}s/run) ===")

    # Rank by the TARGET product's PnL (not overall), so other-product noise
    # doesn't drown the signal.
    results.sort(key=lambda r: r[1]["products"].get(product, {}).get("TOTAL",
                                                                     r[1]["total"]),
                 reverse=True)
    write_csv(f"gridsearch_results_{product.lower()}.csv", product, results)
    print_leaderboard(product, results[:top_n])
    return results


def sweep_joint(top_n: int = 10) -> List[Tuple[Dict, Dict]]:
    """Full cartesian product across BOTH grids."""
    ash_combos = list(iter_grid(GRIDS["ASH_COATED_OSMIUM"]))
    pep_combos = list(iter_grid(GRIDS["INTARIAN_PEPPER_ROOT"]))
    total = len(ash_combos) * len(pep_combos)
    print(f"\n=== Joint sweep : {total} combos "
          f"({len(ash_combos)} x {len(pep_combos)}) ===")
    results: List[Tuple[Dict, Dict]] = []
    t0 = time.time()
    i = 0
    for a, p in itertools.product(ash_combos, pep_combos):
        i += 1
        override = {"ASH_COATED_OSMIUM": a, "INTARIAN_PEPPER_ROOT": p}
        try:
            metrics = run_backtest(override)
        except Exception as e:
            print(f"  [{i:>4}/{total}] ERROR: {e}")
            continue
        combo = {"ASH": a, "PEPPER": p}
        results.append((combo, metrics))
        if i % 10 == 0 or i == total:
            print(f"  [{i:>4}/{total}] total={metrics['total']:>9.0f}")
    elapsed = time.time() - t0
    print(f"=== {total} runs in {elapsed:.1f}s ===")

    results.sort(key=lambda r: r[1]["total"], reverse=True)
    write_csv("gridsearch_results_joint.csv", "JOINT", results)
    print_leaderboard("JOINT", results[:top_n])
    return results


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def print_leaderboard(label: str, top: List[Tuple[Dict, Dict]]) -> None:
    print(f"\nTop {len(top)} — {label}")
    print("-" * 100)
    for rank, (combo, m) in enumerate(top, 1):
        d = m["days"]
        print(f"{rank:>2}. total={m['total']:>9.0f}  "
              f"D-2={d.get('D-2', 0):>8.0f}  D-1={d.get('D-1', 0):>8.0f}  "
              f"D=0={d.get('D=0', 0):>8.0f}  params={combo}")


def write_csv(path: str, label: str, results: List[Tuple[Dict, Dict]]) -> None:
    if not results:
        return
    out = HERE / path
    # Collect the union of all param keys so joint mode works too.
    param_keys: list = []
    seen: set = set()
    for combo, _ in results:
        for k in combo:
            if k not in seen:
                seen.add(k)
                param_keys.append(k)
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(param_keys + ["total_pnl", "D-2", "D-1", "D=0"]
                   + [f"{p}_total" for p in ["ASH_COATED_OSMIUM", "INTARIAN_PEPPER_ROOT"]])
        for combo, m in results:
            row = [json.dumps(combo[k]) if isinstance(combo.get(k), dict) else combo.get(k, "")
                   for k in param_keys]
            row += [m["total"], m["days"].get("D-2", 0),
                    m["days"].get("D-1", 0), m["days"].get("D=0", 0)]
            row += [m["products"].get(p, {}).get("TOTAL", 0)
                    for p in ["ASH_COATED_OSMIUM", "INTARIAN_PEPPER_ROOT"]]
            w.writerow(row)
    print(f"  wrote {out}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode",
                    choices=["ash", "pepper", "both", "joint"],
                    help="which sweep to run")
    ap.add_argument("--top", type=int, default=10, help="leaderboard length")
    args = ap.parse_args(argv)

    if not BT.exists():
        print(f"error: {BT} not found", file=sys.stderr)
        return 2

    if args.mode == "ash":
        sweep_product("ASH_COATED_OSMIUM", top_n=args.top)
    elif args.mode == "pepper":
        sweep_product("INTARIAN_PEPPER_ROOT", top_n=args.top)
    elif args.mode == "both":
        sweep_product("ASH_COATED_OSMIUM", top_n=args.top)
        sweep_product("INTARIAN_PEPPER_ROOT", top_n=args.top)
    elif args.mode == "joint":
        sweep_joint(top_n=args.top)

    return 0


if __name__ == "__main__":
    sys.exit(main())
