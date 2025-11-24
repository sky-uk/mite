#!/bin/bash

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

# Because of the settings of the environment where the pipeline runs, cdBuild.sh is used for both mite and acurl CI.
# Here we check the JOB_NAME variable to determine which kind of run it is and call the appropriate script.
# Note that this script only runs tests. The release scripts are not called from here.

# First run pre-commit checks, then run the appropriate test script based on JOB_NAME.

echo "##### Run pre-commit checks before running tests #####"
/home/jenkins/.local/bin/pre-commit run --origin HEAD --source origin/master
PRE_COMMIT_STATUS=$?

if [ $PRE_COMMIT_STATUS -ne 0 ]; then
    git diff
fi


echo $JOB_NAME

if [[ "$JOB_NAME" =~ "mite-ci" ]]; then
    echo "##### Running as MITE-CI. ######"
    hatch env remove test.py3.11 && hatch run test.py3.11:test-cov ; TESTS_EXIT_CODE=$?

elif [[ "$JOB_NAME" =~ "acurl-ci" ]]; then
    echo "##### Running as ACURL-CI. ######"
    hatch env remove test.py3.11 && hatch run test.py3.11:acurl-test ; TESTS_EXIT_CODE=$?
fi

[ "$PRE_COMMIT_STATUS" -eq 0 -a "$TESTS_EXIT_CODE" -eq 0 ] || exit 1
echo "##### Tests passed #####"