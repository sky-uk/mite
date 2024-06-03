#!/bin/sh -x

/home/jenkins/.local/bin/pre-commit run --origin HEAD --source origin/master
PRE_COMMIT_STATUS=$?

if [ $PRE_COMMIT_STATUS -ne 0 ]; then
    git diff
fi

pip install ujson
tox -e py310; TOX_EXIT_CODE=$?

# Further ideas for jobs to run:
# - license check
# - make sure test coverage increases
# And, once we're sure that the pipeline is working:
# - integration/performance tests
# Once we have docs:
# - documentation coverage
# - docs build (on master only)

[ "$TOX_EXIT_CODE" -eq 0 -a "$PRE_COMMIT_STATUS" -eq 0 ] || exit 1