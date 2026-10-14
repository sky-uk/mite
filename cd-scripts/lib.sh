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

function checkAcurl() {
    local response http_code published local_version

    response=$(curl -sS --retry 3 --retry-connrefused --max-time 30 \
                    -w '\n%{http_code}' https://pypi.org/pypi/acurl/json)
    http_code=$(tail -n1 <<<"$response")

    case "$http_code" in
        200) published=$(sed '$d' <<<"$response" | jq -r '.info.version') ;;
        404) echo "acurl not yet on PyPI; will publish"; ACURL_CHANGED=true; return ;;
        *)   echo "PyPI lookup failed (HTTP $http_code); refusing to guess" >&2; exit 1 ;;
    esac

    [[ -n "$published" && "$published" != "null" ]] \
        || { echo "could not parse published acurl version" >&2; exit 1; }

    local_version=$(hatch run release:python -c \
        "import tomllib,pathlib;print(tomllib.loads(pathlib.Path('acurl/pyproject.toml').read_text())['project']['version'])")

    # compare with packaging.version.parse, not string equality
    if hatch run release:python -c "
import sys
from packaging.version import parse
sys.exit(0 if parse(sys.argv[1]) != parse(sys.argv[2]) else 1)" "$local_version" "$published"; then
        echo "acurl $published -> $local_version; will publish"
        ACURL_CHANGED=true
    else
        echo "acurl unchanged at $published"
        ACURL_CHANGED=false
    fi
}

function buildLinuxWheels() {
    rm -rf wheelhouse-mite wheelhouse-acurl

    if [ "$VERSION_INCREMENT" = true ]; then
        echo "##### Building Mite #####"
        hatch run release:build-mite
    fi

    if [ "$ACURL_CHANGED" = true ]; then
        echo "##### Building Acurl #####"
        hatch run release:wheels-acurl
        hatch run release:sdist-acurl
    fi
}
