"""cdRelease

Usage:
    cdRelease.py [options] [--patch|--minor|--major]
    cdRelease.py [options] [--pr_number=<pr_number>]

    cdRelease.py (-h | --help)

Options:
    -h --help       Show this screen
    --patch         Increment patch version segment
    --minor         Increment minor version segment
    --major         Increment major version segment

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
    else:
        raise ValueError(
            f"Does not contain a valid specification of a version to increment: {version_parts_to_increment}"
        )

    return f"v{major}.{minor}.{patch}"


def increment_version_manually(clv, opts):
    if opts["--major"]:
        major = clv.major + 1
        minor = 0
        patch = 0
    elif opts["--minor"]:
        major = clv.major
        minor = clv.minor + 1
        patch = 0
    elif opts["--patch"]:
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


def parse_pr(pr_number):
    resp = requests.get(f"https://api.github.com/repos/sky-uk/mite/pulls/{pr_number}")
    pr_message = resp.json()["body"]

    matches = re.findall(
        r"^- \[x\] (major|minor|patch)\r$", pr_message, re.IGNORECASE | re.MULTILINE
    )

    # Return a lowercase list, in case the user has changed the case during
    # the creation of their pull request
    return [m.lower() for m in matches if m.lower() in ("major", "minor", "patch")]


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

    if any([opts["--major"], opts["--minor"], opts["--patch"]]):
        # Get version increment from command line arg.
        new_tag = increment_version_manually(current_latest_version, opts)
    else:
        # Get version increment from value set in PR message body
        if opts["--pr_number"]:
            version_parts_to_increment = parse_pr(opts["--pr_number"])
        else:
            commit_message = repo.git.log("--format=%B", n=1)
            matches = re.findall(r"^.*\(#(\d+)\)$", commit_message, re.MULTILINE)
            version_parts_to_increment = parse_pr(matches[0])

        if not version_parts_to_increment:
            logger.info("No release")
            with open("/tmp/workspace/env_vars", "a") as f:
                f.write("export VERSION_INCREMENT=false")
            sys.exit(0)
        new_tag = increment_version_from_pr(
            current_latest_version, version_parts_to_increment
        )

    create_and_push_tag(repo, new_tag)

    sys.exit(0)


if __name__ == "__main__":
    main()
