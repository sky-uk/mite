#!/bin/bash

cd `git rev-parse --show-toplevel`

mkdir -p test/perf/output

# if ! git diff-index --quiet HEAD -- ; then
#     echo "Repo is dirty!!!"
#     exit 1
# fi

docker build -t mite-perftest -f Dockerfile.perftest . || exit 1

docker run --user `id -u` --rm \
       --mount "type=bind,source=`pwd`/test/perf/output,destination=/output" \
       --env MITE_PERFTEST_OUT=/output \
       mite-perftest python test/perf/perftest.py \
       `git rev-parse --abbrev-ref HEAD`-`git rev-parse --short HEAD`
