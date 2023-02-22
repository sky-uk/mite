#!/usr/bin/env bash

cd `git rev-parse --show-toplevel`

mkdir -p test/perf/output

# if ! git diff-index --quiet HEAD -- ; then
#     echo "Repo is dirty!!!"
#     exit 1
# fi

# If running under docker, then the image will be run in the system's uid
# namespace.  That means that we need to switch the user under which it runs,
# so that the perf test output data that it's creating in the test/perf/output
# directory is owned by the current user and not root.  On other container
# runtimes, such as podman, the container will be run in a new uid namespace
# where root (uid 0) is actually the current user.  Under that circumstance,
# the ownership of the output files works correctly, and changing the user id
# of the running container is undesirable because that results (in the host
# uid ns) in the files being owned by a nonexistent user.  This conditional
# accounts for the difference.
if docker --version | grep -q podman; then
    uid_arg=""
else
    uid_arg="--user `id -u`"
fi

docker build -t mite-perftest -f Dockerfile.perftest . || exit 1

docker run --rm $uid_arg \
       --mount "type=bind,source=`pwd`/test/perf/output,destination=/output" \
       --env MITE_PERFTEST_OUT=/output \
       mite-perftest python test/perf/perftest.py \
       `git rev-parse --abbrev-ref HEAD`-`git rev-parse --short HEAD`
