#!/bin/sh -x

/home/jenkins/.local/bin/pre-commit run --origin HEAD --source origin/master
PRE_COMMIT_STATUS=$?

if [ $PRE_COMMIT_STATUS -ne 0 ]; then
    git diff
fi

pip install -r test-requirements.txt
pip install -r requirements.txt
       
pip install ./acurl      
pip install ./acurl_ng

TEST_EXIT_CODE=1
pytest acurl/tests
EC1=$?
pytest acurl_ng/tests
EC2=$?

if [ "$EC1" -eq 0 -a "$EC2" -eq 0 ];
then
    TEST_EXIT_CODE=0
fi

# tox seems to be giving issues, so dropping it for now
# tox -e py39; TOX_EXIT_CODE=$?

# Further ideas for jobs to run:
# - license check
# - make sure test coverage increases
# And, once we're sure that the pipeline is working:
# - integration/performance tests
# Once we have docs:
# - documentation coverage
# - docs build (on master only)

# when we start using tox again, uncomment the line below
# [ "$TOX_EXIT_CODE" -eq 0 -a "$PRE_COMMIT_STATUS" -eq 0 ] || exit 1

# remove the line below once (if) we start using tox again
[ "$TEST_EXIT_CODE" -eq 0 -a "$PRE_COMMIT_STATUS" -eq 0 ] || exit

