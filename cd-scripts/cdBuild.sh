#!/bin/bash

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

# Note that this script only runs tests. The release scripts are not called from here.

# First run pre-commit checks, then the tests.
echo "##### Run pre-commit checks before running tests #####"
pre-commit run --origin HEAD --source origin/master
PRE_COMMIT_STATUS=$?

if [ $PRE_COMMIT_STATUS -ne 0 ]; then
    git diff
fi

echo "##### Running tests #####"
hatch env remove test.py3.12 && hatch run test.py3.12:test-cov ; TESTS_EXIT_CODE=$?

[ "$PRE_COMMIT_STATUS" -eq 0 -a "$TESTS_EXIT_CODE" -eq 0 ] || exit 1
echo "##### Tests passed #####"