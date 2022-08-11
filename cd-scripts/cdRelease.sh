#!/bin/bash

VERSION=""

#get parameters
while getopts v: flag
do
  case "${flag}" in
    v) VERSION=${OPTARG};;
  esac
done

#get highest tag number, and add 1.0.0 if doesn't exist
CURRENT_VERSION=$(git describe --abbrev=0 --tags 2>/dev/null)

if [[ $CURRENT_VERSION == "" ]]
then
  CURRENT_VERSION="v1.0.0"
fi
# echo "Current Version: $CURRENT_VERSION"


#replace . with space so can split into an array
CURRENT_VERSION_PARTS=($(echo $CURRENT_VERSION | sed -E 's/v([0-9]+)\.([0-9]+)\.?([0-9]+)?/\1 \2 \3/'))

#get number parts
MAJOR=${CURRENT_VERSION_PARTS[0]}
MINOR=${CURRENT_VERSION_PARTS[1]}
PATCH=${CURRENT_VERSION_PARTS[2]}

# echo "Current: $MAJOR $MINOR $PATCH"

# echo $((MAJOR+1))

# exit 0

if [[ $VERSION == "major" ]]
then
  MAJOR=$((MAJOR+1))
elif [[ $VERSION == "minor" ]]
then
  MINOR=$((MINOR+1))
elif [[ $VERSION == "patch" ]]
then
  PATCH=$((PATCH+1))
else
  echo "No version type, try: -v [major, minor, patch]"
  exit 1
fi


#create new tag
NEW_TAG="v$MAJOR.$MINOR.$PATCH"
echo "($VERSION) updating $CURRENT_VERSION to $NEW_TAG"

GIT_COMMIT=$(git rev-parse HEAD)
NEEDS_TAG=$(git describe --contains $GIT_COMMIT 2>/dev/null)

if [ -z "$NEEDS_TAG" ]; then
    echo "TAGGING $NEW_TAG"
    git tag $NEW_TAG
    git push --tags
else
    echo "ALREADY HAS TAG"
fi

exit 0 
