#!/bin/bash

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"



echo "##### Run pre-commit checks #####"
/home/jenkins/.local/bin/pre-commit run --origin HEAD --source origin/master
PRE_COMMIT_STATUS=$?

if [ $PRE_COMMIT_STATUS -ne 0 ]; then
    git diff
fi

echo "##### Run tests with tox #####"
tox; TOX_EXIT_CODE=$?
[ "$TOX_EXIT_CODE" -eq 0 -a "$PRE_COMMIT_STATUS" -eq 0 ] || exit 1
echo "##### Pre-commit and Tests passed #####"
