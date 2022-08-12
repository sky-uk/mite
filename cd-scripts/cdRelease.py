"""cdRelease

Usage:
    cdRelease.py [options] patch
    cdRelease.py [options] minor
    cdRelease.py [options] major

    cdRelease.py (-h | --help)

Options:
    -h --help       Show this screen

"""

import logging
import sys

import docopt
import git
from packaging.version import parse

logger = logging.getLogger("cdRelease")


def increment_version(clv, opts):
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
    new_tag = increment_version(current_latest_version, opts)

    create_and_push_tag(repo, new_tag)

    sys.exit(0)


if __name__ == "__main__":
    main()
