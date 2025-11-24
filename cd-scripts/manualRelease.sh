#!/bin/bash

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

if isOnMaster; then
    echo "##### Job running on MASTER. Proceeding with the Tag and Release script. ######"
    echo "##### Starting tag process and check for version increment #####"
    # We are passing over the VERSION_INCREMENT_TYPE argument to tagBuild which will set the type of increment for the new version
    tagBuild $VERSION_INCREMENT_TYPE

    echo "##### Look for Acurl changes #####"
    checkAcurl

    echo "##### Build Linux-Wheels #####"
    buildLinuxWheels

    if [ "$VERSION_INCREMENT" = false ] && [ "$ACURL_CHANGED" = false ]; then
        echo "Mite version not incremented and Acurl not changed, nothing to upload"
    else
        echo "##### Init .pypirc #####"
        initPypirc

        echo "##### Upload package #####"
        python3 -m twine upload wheelhouse/* 
    fi

else
	echo "Not going to build the mite image because the job is not running on the master branch"
fi