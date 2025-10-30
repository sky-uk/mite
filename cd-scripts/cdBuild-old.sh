#!/bin/bash -e

function isOnMaster() {
	current_revision=$(git rev-parse HEAD)
	branch=$(git branch -r --contains $current_revision)
	set +e
	echo "$branch" | grep -q "origin/master$"
	result=$?
	set -e
	return ${result}
}

if isOnMaster; then
	docker build -t mite .
	docker tag mite registry.tools.cosmic.sky/identity/sre/mite
	docker push registry.tools.cosmic.sky/identity/sre/mite
	echo "Mite image built successfully"

else
	echo "Skipped building the mite image because the job is not running on the master branch"
fi
