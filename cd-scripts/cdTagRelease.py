"""cdRelease

Usage:
    cdRelease.py create (--patch | --minor | --major) --output=<file>
    cdRelease.py push --tag=<tag>
    cdRelease.py (-h | --help)

Options:
    -h --help        Show this screen
    --patch          Increment patch version segment
    --minor          Increment minor version segment
    --major          Increment major version segment
    --output=<file>  Write the created tag name to this file
    --tag=<tag>      Tag to push

"""

import logging
import re
import subprocess
import sys
from pathlib import Path


import docopt
from packaging.version import parse


logger = logging.getLogger("cdRelease")


# Exit-code contract with cd-scripts/manualRelease.sh, which branches on all
# three. Conflating these is what made failed releases report success.
EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_NOTHING = 2  # already tagged; not an error


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
    return [
        t
        for t in git("tag", "--points-at", "HEAD").splitlines()
        if TAG_RE.match(t)
    ]


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


def cmd_create(opts):
    existing = head_version_tags()
    if existing:
        logger.info(
            "HEAD already tagged (%s); nothing to do", ", ".join(existing)
        )
        return EXIT_NOTHING

    new_tag = increment_version_manually(latest_version(), opts)
    logger.info("Creating local git tag '%s'", new_tag)
    git("tag", "-a", new_tag, "-m", f"Automatic version tag {new_tag}")
    Path(opts["--output"]).write_text(new_tag)
    return EXIT_OK


def cmd_push(opts):
    tag = opts["--tag"]
    logger.info("Pushing tag '%s'", tag)
    git("push", "origin", f"refs/tags/{tag}")
    return EXIT_OK


def main():
    opts = docopt.docopt(__doc__)
    logging.basicConfig(
        level="INFO",
        format="[%(asctime)s] <%(levelname)s> [%(name)s] [%(funcName)s] %(message)s",
    )

    try:
        if opts["create"]:
            return cmd_create(opts)
        if opts["push"]:
            return cmd_push(opts)
    except GitError as exc:
        logger.error("%s", exc)
        return EXIT_FAILURE

    logger.error("no subcommand matched")
    return EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())
