#!/usr/bin/env bash
# Thin wrapper around the Rust backtester that sets the environment this
# machine needs (PyO3/libpython link paths) so you never have to remember them.
#
# Usage:
#   ./bt.sh                    # full round1, compact output
#   ./bt.sh --day -1           # just day -1
#   ./bt.sh --artifact-mode full --persist
#   ./bt.sh                    # runs trader.py with its current params
#   # (param overrides go through `trader_params.json` sidecar — see gridsearch.py)
#
# Any extra args are passed through to the backtester.

set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BT_DIR="${BT_DIR:-$THIS_DIR/../prosperity_rust_backtester}"
TRADER="${TRADER:-$THIS_DIR/trader.py}"
DATASET="${DATASET:-round1}"

export PATH="$HOME/.cargo/bin:$PATH"
export PYO3_PYTHON="${PYO3_PYTHON:-/usr/bin/python3}"
export RUSTFLAGS="${RUSTFLAGS:--L /Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib -C link-arg=-Wl,-rpath,/Library/Developer/CommandLineTools/Library/Frameworks}"

cd "$BT_DIR"
exec cargo run --release --quiet -- --trader "$TRADER" --dataset "$DATASET" "$@"
