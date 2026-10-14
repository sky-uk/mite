"""cdRelease

Usage:
    cdRelease.py [options] [--patch|--minor|--major]

    cdRelease.py (-h | --help)

Options:
    -h --help       Show this screen
    --patch         Increment patch version segment
    --minor         Increment minor version segment
    --major         Increment major version segment

"""

import logging
import re
import subprocess
import sys

import docopt
from packaging.version import parse


logger = logging.getLogger("cdRelease")


class GitError(Exception):
    pass


def git(*args, check=True):
    """Run a git command and return its stdout, stripped."""
    proc = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


# Must stay in sync with tag_regex in pyproject.toml:92, which is what
# hatch-vcs uses to derive the package version from the tag.
TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def all_version_tags():
    return [t for t in git("tag", "--list").splitlines() if TAG_RE.match(t)]


def latest_version():
    tags = all_version_tags()
    return max(parse(t) for t in tags) if tags else parse("v0.0.0")


def head_version_tags():
    return [t for t in git("tag", "--points-at", "HEAD").splitlines() if TAG_RE.match(t)]


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
    else:
        raise AssertionError("no version increment type given")

    return f"v{major}.{minor}.{patch}"


def create_and_push_tag(tag):
    logger.info(f"Creating git tag '{tag}'")
    git("tag", "-a", tag, "-m", f"Automatic version tag {tag}")
    git("push", "origin", f"refs/tags/{tag}")


def main():
    opts = docopt.docopt(__doc__)
    logging.basicConfig(
        level="INFO",
        format="[%(asctime)s] <%(levelname)s> [%(name)s] [%(funcName)s] %(message)s",
    )

    if not any([opts["--major"], opts["--minor"], opts["--patch"]]):
        logger.error(
            "The job requires on option between major, minor or patch to know how to increment the version. Aborting.'"
        )
        sys.exit(1)

    existing = head_version_tags()
    if existing:
        logger.error("HEAD already tagged (%s)", ", ".join(existing))
        sys.exit(1)

    new_tag = increment_version_manually(latest_version(), opts)

    create_and_push_tag(new_tag)
    sys.exit(0)


if __name__ == "__main__":
    main()
