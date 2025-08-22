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

echo "##### Run acurl/tests/test_httpbin.py only (py311 via tox) #####"
echo "##### Memory usage before tests #####"
free -m || vm_stat
ps
TOXENV=py311 tox -- -v acurl/tests/test_httpbin.py; TOX_EXIT_CODE=$?

echo "##### Memory usage after tests #####"
free -m || vm_stat
ps

[ "$TOX_EXIT_CODE" -eq 0 -a "$PRE_COMMIT_STATUS" -eq 0 ] || exit 1

if isOnMaster ; then
    echo "##### Job running on MASTER. Proceeding with the Tag and Release script. ######"
    ./cd-scripts/cdTagRelease.sh
else
    echo "###### Job running on a Branch. Stopping here. ######"
fi
