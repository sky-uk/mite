

# this block can be moved below - before or with the wheel
ACURL_CHANGED=false

# FIXME - This section works correctly locally returning false. 
# Investigate why it doens't work correctly in the pipeline
#
# if [[ -n $(git show --name-only ${CD_VCS_REF} ./acurl) ]]; then
#     echo "Acurl has changed"
#     ACURL_CHANGED=true
#     LATEST_ACURL_VERSION=$(curl -s https://pypi.org/pypi/acurl/json | jq -r '.info .version')
#     if [[ -n $(grep "version = $LATEST_ACURL_VERSION$" acurl/setup.cfg) ]]; then
#     echo "Acurl has changed, but the version of acurl hasn't changed"
#     exit 1
#     fi
# fi
mkdir -p /tmp/workspace
echo "export ACURL_CHANGED=\"$ACURL_CHANGED\"" >> /tmp/workspace/env_vars

# BUILD STEP from Circle-ci - it just run tox.
tox -e py310; TOX_EXIT_CODE=$?
[ "$TOX_EXIT_CODE" -eq 0 -a "$PRE_COMMIT_STATUS" -eq 0 ] || exit 1