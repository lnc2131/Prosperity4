#!/usr/bin/env python3
"""
bench.py — run the backtester on a trader file, append one row to benchmarks.csv.

Usage:
    python3 research/bench.py --trader research/strategies/01_foo.py --label ash_momentum
    python3 research/bench.py --trader trader.py --label champion_rebench
    python3 research/bench.py --trader trader.py --label my_test --notes "sanity check"
    python3 research/bench.py --trader trader.py --label my_test --params-json '{"ASH_COATED_OSMIUM":{"take_width":2}}'

The backtester is always invoked through ../bt.sh so environment setup is consistent.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent         # .../Prosperity4/research
ROOT = HERE.parent                              # .../Prosperity4
BT = ROOT / "bt.sh"
CSV_PATH = HERE / "benchmarks.csv"

_TOTAL_RE = re.compile(r"^TOTAL\s+-\s+\d+\s+\d+\s+(-?\d+\.\d+)", re.MULTILINE)
_DAY_RE = re.compile(r"^(D-2|D-1|D=0)\s+(-?\d+)\s+\d+\s+\d+\s+(-?\d+\.\d+)", re.MULTILINE)
_PROD_RE = re.compile(
    r"^([A-Z_][A-Z_0-9]+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)",
    re.MULTILINE,
)


def run(trader_path: Path, params_override: dict | None) -> dict:
    env = os.environ.copy()
    env["TRADER"] = str(trader_path)

    # The trader reads optional overrides from a `trader_params.json` sidecar
    # next to its own file. Write it for the duration of the run, delete after.
    sidecar = trader_path.parent / "trader_params.json"
    wrote_sidecar = False
    if params_override is not None:
        sidecar.write_text(json.dumps(params_override))
        wrote_sidecar = True
    try:
        proc = subprocess.run(
            [str(BT), "--artifact-mode", "none"],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
    finally:
        if wrote_sidecar:
            try:
                sidecar.unlink()
            except FileNotFoundError:
                pass
    out = proc.stdout + proc.stderr
    tm = _TOTAL_RE.search(out)
    if not tm:
        print(out[-1500:], file=sys.stderr)
        raise RuntimeError("backtester did not produce a TOTAL line")
    total = float(tm.group(1))
    days = {label: float(pnl) for label, _, pnl in _DAY_RE.findall(out)}
    products = {
        m[0]: float(m[4])  # TOTAL column per product
        for m in _PROD_RE.findall(out)
    }
    return {"total": total, "days": days, "products": products, "stdout": out}


def append_row(label: str, params_override: dict | None, metrics: dict, notes: str):
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    fresh = not CSV_PATH.exists()
    with CSV_PATH.open("a", newline="") as f:
        w = csv.writer(f)
        if fresh:
            w.writerow(["timestamp", "strategy", "params_json", "pnl_total",
                        "pnl_d-2", "pnl_d-1", "pnl_d0",
                        "pnl_ash", "pnl_pepper", "notes"])
        w.writerow([
            _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            label,
            json.dumps(params_override or {}, separators=(",", ":")),
            metrics["total"],
            metrics["days"].get("D-2", 0),
            metrics["days"].get("D-1", 0),
            metrics["days"].get("D=0", 0),
            metrics["products"].get("ASH_COATED_OSMIUM", 0),
            metrics["products"].get("INTARIAN_PEPPER_ROOT", 0),
            notes,
        ])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trader", required=True, help="path to trader .py file to benchmark")
    ap.add_argument("--label", required=True, help="strategy label (kept in benchmarks.csv)")
    ap.add_argument("--notes", default="", help="optional free-text note")
    ap.add_argument("--params-json", default=None,
                    help="optional JSON dict of param override, written to a sidecar "
                         "trader_params.json next to the trader file for one run")
    args = ap.parse_args(argv)

    trader_path = Path(args.trader).resolve()
    if not trader_path.exists():
        print(f"error: trader file not found: {trader_path}", file=sys.stderr)
        return 2
    if not BT.exists():
        print(f"error: bt.sh not found at {BT}", file=sys.stderr)
        return 2

    params = None
    if args.params_json:
        params = json.loads(args.params_json)

    print(f"→ benchmarking {trader_path.name} as '{args.label}' ...")
    m = run(trader_path, params)
    append_row(args.label, params, m, args.notes)

    print(f"  total={m['total']:.2f}  "
          f"D-2={m['days'].get('D-2', 0):.0f}  "
          f"D-1={m['days'].get('D-1', 0):.0f}  "
          f"D=0={m['days'].get('D=0', 0):.0f}")
    for p, v in m["products"].items():
        print(f"  {p}: {v:.2f}")
    print(f"  appended row → {CSV_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
