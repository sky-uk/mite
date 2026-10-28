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

# Verify stats loading doesn't crash. Integration processors needing a
# missing extra (acurl, aiokafka, etc.) are EXPECTED to log a warning and be
# skipped here — assert non-empty, not that every processor loaded.
#
# PYTHONSAFEPATH (3.11+) keeps the repo's own acurl/ directory off sys.path,
# where it would otherwise satisfy `import acurl` as a namespace package and
# mask a genuinely missing dependency.
if ! PYTHONSAFEPATH=1 "$VENV/bin/python" -c '
from mite.stats import load_stats_entry_points as f
assert f(), "no stats processors loaded"
'; then
    echo "FAIL: load_stats_entry_points() failed on a core-only install" >&2
    exit 1
fi

echo "Core-only install check passed"
