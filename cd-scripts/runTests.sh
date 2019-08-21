#!/bin/sh

python3.7 -m venv /mite-tests
. /mite-tests/bin/activate

pip install -r requirements.txt || exit 1
pip install -r dev-requirements.txt || exit 1

tox; TOX_EXIT_CODE=$?
coverage html

flake8; FLAKE8_EXIT_CODE=$?

# Further ideas for jobs to run: license check, black (once we're sure that
# the pipeline is working): integration/performance tests, documentation
# coverage, docs build (on master only), force test coverage to monotonically
# increase, ...

[ $TOX_EXIT_CODE -eq 0 -a $FLAKE8_EXIT_CODE -eq 0 ] || exit 1
