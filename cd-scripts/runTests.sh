#!/bin/sh

MY_VENV=$HOME/mite-tests

python3.7 -m venv $MY_VENV
. $MY_VENV/bin/activate

pip install -r requirements.txt || exit 1
pip install -r dev-requirements.txt || exit 1

tox; TOX_EXIT_CODE=$?
coverage html

flake8; FLAKE8_EXIT_CODE=$?

# Further ideas for jobs to run:
# - license check
# - black
# - make sure test coverage increases
# And, once we're sure that the pipeline is working:
# - integration/performance tests
# Once we have docs:
# - documentation coverage
# - docs build (on master only)

[ $TOX_EXIT_CODE -eq 0 -a $FLAKE8_EXIT_CODE -eq 0 ] || exit 1
