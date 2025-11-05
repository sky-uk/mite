#!/bin/bash


echo "##### Run pre-commit checks #####"
/home/jenkins/.local/bin/pre-commit run --origin HEAD --source origin/master
PRE_COMMIT_STATUS=$?

if [ $PRE_COMMIT_STATUS -ne 0 ]; then
    git diff
fi


echo "##### Run tests with tox #####"
hatch run test.py3.11:test ; TESTS_EXIT_CODE=$?
[ "$TESTS_EXIT_CODE" -eq 0 -a "$PRE_COMMIT_STATUS" -eq 0 ] || exit 1
echo "##### Pre-commit and Tests passed #####"
