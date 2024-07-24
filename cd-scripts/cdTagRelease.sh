#!/bin/bash

function tagBuild() {   
    git config user.email "mite@noreply.github.com"
    git config user.name "Jenkins-CI"
    pip3 install docopt GitPython packaging requests
    python3 cd-scripts/cdRelease.py
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
        if [[ -n $(grep "version = $LATEST_ACURL_VERSION$" acurl/setup.cfg) ]]; then
        echo "Acurl has changed, but the version of acurl hasn't changed"
        exit 1
        fi
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

###### MAIN SECTION ######

echo "##### Starting tag process and check for version increment #####"
tagBuild

echo "##### Look for Acurl changes #####"
checkAcurl

echo "##### Build Linux-Wheels #####"
buildLinuxWheels

if [ "$VERSION_INCREMENT" = false ]; then
        echo "Mite version not incremented, nothing to upload"
else
    echo "##### Init .pypirc #####"
    initPypirc

    echo "##### Upload package #####"
    python3 -m twine upload wheelhouse/*
fi