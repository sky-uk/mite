#!/bin/bash

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

if isOnMaster; then
    echo "##### Job running on MASTER. Proceeding with the Tag and Release script. ######"
    ./cd-scripts/cdTagRelease.sh ${VERSION_INCREMENT_TYPE}

else
	echo "Not going to build the mite image because the job is not running on the master branch"
fi
