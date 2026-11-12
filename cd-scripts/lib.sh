#!/bin/bash

function isOnMaster() {
    git fetch --quiet origin master || return 1
    git merge-base --is-ancestor HEAD origin/master
}

function assertReleasable() {
    : "${PYPI_TOKEN:?PYPI_TOKEN is not set}"
    : "${VERSION_INCREMENT_TYPE:?VERSION_INCREMENT_TYPE is not set}"

    case "$VERSION_INCREMENT_TYPE" in
        patch|minor|major) ;;
        *) echo "invalid VERSION_INCREMENT_TYPE: $VERSION_INCREMENT_TYPE" >&2; exit 1 ;;
    esac

    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo "working tree dirty; refusing to release" >&2
        git status --short
        exit 1
    fi
}

function buildLinuxWheels() {
    rm -rf wheelhouse-mite

    if [ "$VERSION_INCREMENT" = true ]; then
        echo "##### Building Mite #####"
        hatch run release:build-mite
    fi
}
