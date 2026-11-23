#!/bin/bash

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV=/tmp/mite-bare

echo "##### Core-only install check #####"

# Remove any existing virtual environment to start fresh
rm -rf "$VENV"
python3 -m venv "$VENV" || exit 1

# Install the project in a fresh virtual environment with only core dependencies
if ! "$VENV/bin/pip" install --quiet "$REPO_ROOT"; then
    echo "FAIL: pip install . failed with only [project].dependencies declared" >&2
    exit 1
fi

# Verify that the installed mite command works as expected
if ! "$VENV/bin/mite" --help >/dev/null; then
    echo "FAIL: mite --help failed on a core-only install" >&2
    exit 1
fi

# Verify Stats() construction (load + per-instance copy) doesn't crash. Integration processors needing a
# missing extra (httpperf, aiokafka, etc.) are EXPECTED to log a warning and
# be skipped here — assert non-empty, not that every processor loaded.
# FIXME - I don't like this
if ! "$VENV/bin/python" -c '
from mite.stats import Stats
s = Stats(None)
assert s._all_stats, "no stats processors loaded"
names = [stat.name for stat in s._all_stats]
assert "mite_transaction_total" in names, names
'; then
    echo "FAIL: Stats() construction failed on a core-only install" >&2
    exit 1
fi

echo "Core-only install check passed"
