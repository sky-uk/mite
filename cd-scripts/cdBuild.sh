#!/bin/bash

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

# Because of the settings of the environment where the pipeline runs, cdBuild.sh is used for both CI testing and manual releases as we can change the default scripts used.
# In a normal situation, we would have two separate scripts, one for CI and one for manual releases.
# Here we check the JOB_NAME variable to determine which kind of run it is and call the appropriate script.

# manual-release job will run the release script directly
# any other job (like miteci-release) will run the test script. Then the pipeline shape will take care of calling the release script if the tests pass for the CI job.

echo $JOB_NAME

if [[ "$JOB_NAME" =~ "mite-manual-release" ]]; then
    echo "##### Job running as MANUAL RELEASE. Proceeding with the Tag and Release script. ######"
    ./cd-scripts/cdRelease.sh ${VERSION_INCREMENT_TYPE}

else
    echo "##### Job running as CI. Proceeding with the Test script. ######"
    ./cd-scripts/runTests.sh
fi