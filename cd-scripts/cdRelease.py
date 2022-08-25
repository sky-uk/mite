"""cdRelease

Usage:
    cdRelease.py [options] major
    cdRelease.py [options] minor
    cdRelease.py [options] patch
    cdRelease.py [options] [--pr_number=<pr_number>]

    cdRelease.py (-h | --help)

Options:
    -h --help       Show this screen

"""

import logging
import re
import sys

import docopt
import git
import requests
from packaging.version import parse

logger = logging.getLogger("cdRelease")


def increment_version_from_pr(clv, version_parts_to_increment):
    major = clv.major
    minor = clv.minor
    patch = clv.micro

    if "major" in version_parts_to_increment:
        major += 1
        minor = 0
        patch = 0
    elif "minor" in version_parts_to_increment:
        minor += 1
        patch = 0
    elif "patch" in version_parts_to_increment:
        patch += 1

    return f"v{major}.{minor}.{patch}"


def increment_version_manually(clv, opts):
    if opts["major"]:
        major = clv.major + 1
        minor = 0
        patch = 0
    elif opts["minor"]:
        major = clv.major
        minor = clv.minor + 1
        patch = 0
    elif opts["patch"]:
        major = clv.major
        minor = clv.minor
        patch = clv.micro + 1

    return f"v{major}.{minor}.{patch}"


def create_and_push_tag(repo, tag):
    logger.info(f"Creating git tag '{tag}'")
    try:
        git_tag = repo.create_tag(tag, message=f"Automatic version tag {tag}")
    except git.exc.GitCommandError:
        logger.error(f"Failed creating tag {tag}, possibly already exists")
        sys.exit(1)

    repo.remotes.origin.push(git_tag)

    status = repo.remotes.origin.push(git_tag)
    if status.error:
        logger.error(f"Failed to push remote tag: {status.error}")
        sys.exit(1)


def parse_pr(opts):
    resp = requests.get(
        f"https://api.github.com/repos/sky-uk/mite/pulls/{opts['--pr_number']}"
    )
    pr_message = resp.json()["body"]

    matches = re.findall(r"- \[x\] (\w+)(?:$|\n)", pr_message, re.IGNORECASE)

    # Return a lowercase list, in case the user has changed the case during
    # the creation of their pull request
    return [x.lower() for x in matches]


def main():
    opts = docopt.docopt(__doc__)
    logging.basicConfig(
        level="INFO",
        format="[%(asctime)s] <%(levelname)s> [%(name)s] [%(funcName)s] %(message)s",
    )

    repo = git.Repo(".")

    if current_tag := next(
        (tag for tag in repo.tags if tag.commit == repo.head.commit), None
    ):
        logger.error(
            f"Commit hash '{repo.head.commit}' Already has a tag '{current_tag}'"
        )
        sys.exit(1)

    try:
        latest_tag = repo.git.describe(["--abbrev=0", "--tags"])
    except git.exc.GitCommandError:
        latest_tag = "v0.0.0"

    current_latest_version = parse(latest_tag)

    if opts["--pr_number"]:
        version_parts_to_increment = parse_pr(opts)
        new_tag = increment_version_from_pr(
            current_latest_version, version_parts_to_increment
        )
    else:
        new_tag = increment_version_manually(current_latest_version, opts)

    create_and_push_tag(repo, new_tag)

    sys.exit(0)


if __name__ == "__main__":
    main()
