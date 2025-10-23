#!/bin/bash

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

VERSION_INCREMENT_TYPE=${1}


###### MAIN SECTION ######

echo "##### Starting tag process and check for version increment #####"
# We are passing over the VERSION_TYPE argument to tagBuild which will set the type of increment for the new version
# If not passed, cdRelease.py will use the  GH PR to check which kind of increment it is supposed to be as VERSION_TYPE will be an empty string
tagBuild ${VERSION_INCREMENT_TYPE}

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