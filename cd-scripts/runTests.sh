#!/bin/sh

pip install -r requirements.txt || exit 1
pip install -r dev-requirements.txt || exit 1

tox; TOX_EXIT_CODE=$?
coverage html

flake8; FLAKE8_EXIT_CODE=$?

# Further ideas for jobs to run: license check, black (once we're sure that
# the repo is integration/performance tests, ...

[ $TOX_EXIT_CODE -eq 0 -a $FLAKE8_EXIT_CODE -eq 0 ] || exit 1
