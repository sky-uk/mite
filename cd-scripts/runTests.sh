#!/bin/sh -x

MY_VENV=$HOME/mite-tests

python3.8 -m venv --system-site-packages $MY_VENV
. $MY_VENV/bin/activate

pip install -U pip

pip install -r requirements.txt || exit 1
pip install -r dev-requirements.txt || exit 1

pre-commit run --origin HEAD --source origin/master
PRE_COMMIT_STATUS=$?

if [ $PRE_COMMIT_STATUS -ne 0 ]; then
    git diff
fi

tox; TOX_EXIT_CODE=$?
coverage html

# Further ideas for jobs to run:
# - license check
# - make sure test coverage increases
# And, once we're sure that the pipeline is working:
# - integration/performance tests
# Once we have docs:
# - documentation coverage
# - docs build (on master only)

[ "$TOX_EXIT_CODE" -eq 0 -a "$PRE_COMMIT_STATUS" -eq 0 ] || exit 1
