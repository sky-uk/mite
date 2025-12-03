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

function tagBuild() {   
    VERSION_INCREMENT_TYPE="${1}"
    git config user.email "mite@noreply.github.com"
    git config user.name "Jenkins-CI"
    pip3 install docopt GitPython packaging requests
    echo "Tagging the build with a ${VERSION_INCREMENT_TYPE} version increment"
    python3 cd-scripts/cdTagRelease.py --${VERSION_INCREMENT_TYPE}
    if (( $? == 1)); then
        VERSION_INCREMENT=false
    fi
}

function checkAcurl() {
    ACURL_CHANGED=false

    if [[ -n $(git show --name-only ${CD_VCS_REF} ./acurl) ]]; then
        echo "Acurl has changed"
        ACURL_CHANGED=true
        LATEST_ACURL_VERSION=$(curl -s https://pypi.org/pypi/acurl/json | jq -r '.info .version')
        CURRENT_ACURL_VERSION=$(grep '^version = ' acurl/pyproject.toml | sed 's/version = "\(.*\)"/\1/')
        if [[ "$CURRENT_ACURL_VERSION" == "$LATEST_ACURL_VERSION" ]]; then
            echo "Acurl has changed, but the version hasn't been updated in pyproject.toml"
            echo "Current version: $CURRENT_ACURL_VERSION, PyPI version: $LATEST_ACURL_VERSION"
            exit 1
        fi
        echo "Acurl version will be updated from $LATEST_ACURL_VERSION to $CURRENT_ACURL_VERSION"
    fi
}

function buildLinuxWheels() {
    
    CIBW_BEFORE_ALL_LINUX="yum install -y libcurl-devel || apt-get install -y libcurl-dev || apk add curl-dev"
    CIBW_SKIP="*i686"

    if [ "$VERSION_INCREMENT" = false ]; then
        echo "Mite version not incremented, not building"
    else
        echo "##### Building Mite #####"
        pip3 install --user cibuildwheel==2.8.1 build twine
        python3 -m build --outdir ./wheelhouse
    fi
    
    if [ "$ACURL_CHANGED" = true ]; then
        echo "##### Building Acurl #####"
        cd acurl
        pip3 install --user cibuildwheel==2.8.1 build Cython twine
        python3 -m build --sdist --outdir ../wheelhouse
        cd ../
    fi
}

function initPypirc() {
    echo -e "[pypi]" > ~/.pypirc
    echo -e "username = __token__" >> ~/.pypirc
    echo -e "password = $PYPI_TOKEN" >> ~/.pypirc
}