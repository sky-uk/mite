#!/bin/bash

function isOnMaster() {
    current_revision=$(git rev-parse HEAD)
    branch=$(git branch -r --contains $current_revision)
    set +e
    echo "$branch" | grep -q "origin/master$"
    result=$?
    set -e
    return ${result}
}


echo "##### Run pre-commit checks #####"
/home/jenkins/.local/bin/pre-commit run --origin HEAD --source origin/master
PRE_COMMIT_STATUS=$?

if [ $PRE_COMMIT_STATUS -ne 0 ]; then
    git diff
fi

echo "##### Run tests with tox #####"
tox; TOX_EXIT_CODE=$?
[ "$TOX_EXIT_CODE" -eq 0 -a "$PRE_COMMIT_STATUS" -eq 0 ] || exit 1

if isOnMaster ; then
    echo "##### Job running on MASTER. Proceeding with the Tag and Release script. ######"
    ./cd-scripts/cdTagRelease.sh
else
    echo "###### Job running on a Branch. Stopping here. ######"
fi
