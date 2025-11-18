#!/bin/bash


echo "##### Run pre-commit checks #####"
cd acurl
ruff check . || PRE_COMMIT_STATUS=$?
PRE_COMMIT_STATUS=$?

if [ $PRE_COMMIT_STATUS -ne 0 ]; then
    git diff
fi


echo "##### Run tests with hatch #####"
# Sort of an hack we are using hatch to run the unit tests here. 
# For this reason we have to move back to the parent directory first.
cd ..
hatch run acurl-test:test ; TESTS_EXIT_CODE=$?
[ "$TESTS_EXIT_CODE" -eq 0 -a "$PRE_COMMIT_STATUS" -eq 0 ] || exit 1
echo "##### Pre-commit and Tests passed #####"
