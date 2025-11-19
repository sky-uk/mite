#!/bin/bash

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

# Because of the settings of the environment where the pipeline runs, cdBuild.sh is used for both CI testing and manual releases as we can change the default scripts used.
# In a normal situation, we would have two separate scripts, one for CI and one for manual releases.
# Here we check the JOB_NAME variable to determine which kind of run it is and call the appropriate script.

# manual-release job will run the release script directly
# any other job (like miteci-release) will run the test script. Then the pipeline shape will take care of calling the release script if the tests pass for the CI job.

echo "##### Run pre-commit checks before running tests #####"
/home/jenkins/.local/bin/pre-commit run --origin HEAD --source origin/master
PRE_COMMIT_STATUS=$?

if [ $PRE_COMMIT_STATUS -ne 0 ]; then
    git diff
fi

[ "$PRE_COMMIT_STATUS" -eq 0 ] || exit 1

echo "##### pre-commit check is good. Proceeding to determine which Test script to run. ######"
echo $JOB_NAME

if [[ "$JOB_NAME" =~ "mite-ci" ]]; then
    echo "##### Running as MITE-CI. ######"
    ./cd-scripts/runMiteTests.sh
    ./cd-scripts/runAcurlTests.sh
elif [[ "$JOB_NAME" =~ "acurl-ci" ]]; then
    echo "##### Running as ACURL-CI. ######"
    ./cd-scripts/runAcurlTests.sh
fi
