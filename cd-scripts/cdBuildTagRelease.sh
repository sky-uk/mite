




# TAG STEP from Circle-ci - 
# it has sshkeys and fingerprints in the config
# FIXME- it is failing but we are on a branch without PR. 
#In any case it likely to run only on master!
echo "Set up git config email and name"
git config user.email "mite@noreply.github.com"
git config user.name "Jenkins-CI"
echo " install pip requirements for the tag script"
pip3 install docopt GitPython packaging requests
echo "run cdRelease"
python3 cd-scripts/cdRelease.py



# linux-wheels
# environment:
# CIBW_BEFORE_ALL_LINUX: "yum install -y libcurl-devel || apt-get install -y libcurl-dev || apk add curl-dev"
# CIBW_SKIP: "*i686"

# ------------------ build wheels
# ---- Check Aculr first
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

# ----- build wheels
source /tmp/workspace/env_vars
if [ "$VERSION_INCREMENT" = false ]; then
    echo "Mite version not incremented, not building"
else
    pip3 install --user cibuildwheel==2.8.1 build twine
    python3 -m build --outdir ./wheelhouse
fi
if [ "$ACURL_CHANGED" = true ]; then
    cd acurl
    pip3 install --user cibuildwheel==2.8.1 build Cython twine
    python3 -m build --sdist --outdir ../wheelhouse
fi

# ini .pypirc
# echo -e "[pypi]" >> ~/.pypirc
#             echo -e "username = __token__" >> ~/.pypirc
#             echo -e "password = $PYPI_PASSWORD" >> ~/.pypirc

# upload packages to pypi
#           command: /root/.local/bin/twine upload wheelhouse/*
