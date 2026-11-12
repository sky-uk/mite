#!/bin/bash
set -euo pipefail
set -E                        # ERR trap must fire inside functions

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

VERSION_INCREMENT=true        # buildLinuxWheels tests `= true`
NEW_TAG=""

function cleanup_on_failure() {
    if [[ -n "$NEW_TAG" ]] && git rev-parse -q --verify "refs/tags/$NEW_TAG" >/dev/null; then
        echo "release failed; removing local tag $NEW_TAG" >&2
        git tag -d "$NEW_TAG"
    fi
}
trap cleanup_on_failure ERR

if ! isOnMaster; then
    echo "Not releasing: job is not running on master"
    exit 0
fi

assertReleasable
rm -f .release-tag

git config user.email "mite@noreply.github.com"
git config user.name "Jenkins-CI"

# ---- 1. tag LOCALLY; hatch-vcs derives the version from it --------
echo "##### Tagging (${VERSION_INCREMENT_TYPE}) #####"
rc=0
hatch run release:tag-create "--${VERSION_INCREMENT_TYPE}" --output=.release-tag || rc=$?
case $rc in
    0) NEW_TAG=$(cat .release-tag) ;;
    2) echo "commit already tagged; nothing to release"; exit 0 ;;
    *) echo "tagging FAILED (exit $rc)" >&2; exit 1 ;;
esac

# ---- 2. build -----------------------------------------------------
echo "##### Build wheels #####"
buildLinuxWheels

# ---- 3. validate BEFORE upload ------------------------------------
shopt -s nullglob
mite_artifacts=(wheelhouse-mite/*)

if [ "$VERSION_INCREMENT" = true ] && (( ${#mite_artifacts[@]} == 0 )); then
    echo "expected mite artifacts, found none" >&2; exit 1
fi

(( ${#mite_artifacts[@]}  > 0 )) && hatch run release:check "${mite_artifacts[@]}"

# ---- 4. upload ----------------------------------------------------
export TWINE_USERNAME=__token__
export TWINE_PASSWORD="$PYPI_TOKEN"
(( ${#mite_artifacts[@]}  > 0 )) && hatch run release:upload "${mite_artifacts[@]}"

# ---- 5. push the tag LAST -----------------------------------------
if [ -n "$NEW_TAG" ]; then
    echo "##### Publishing tag $NEW_TAG #####"
    hatch run release:tag-push --tag="$NEW_TAG"
fi

echo "Release complete: ${NEW_TAG}"