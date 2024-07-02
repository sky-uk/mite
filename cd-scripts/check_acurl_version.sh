ACURL_CHANGED=false
if [[ -n $(git show --name-only ${CD_VCS_REF} ./acurl) ]]; then
    echo "Acurl has changed"
    ACURL_CHANGED=true
    LATEST_ACURL_VERSION=$(curl -s https://pypi.org/pypi/acurl/json | jq -r '.info .version')
    if [[ -n $(grep "version = $LATEST_ACURL_VERSION$" acurl/setup.cfg) ]]; then
    echo "Acurl has changed, but the version of acurl hasn't changed"
    exit 1
    fi
fi
mkdir -p /tmp/workspace
echo "export ACURL_CHANGED=\"$ACURL_CHANGED\"" >> /tmp/workspace/env_vars