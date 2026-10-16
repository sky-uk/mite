"""checkAcurlVersion

Usage:
    checkAcurlVersion.py --published=<version> --output=<file>
    checkAcurlVersion.py (-h | --help)

Options:
    -h --help            Show this screen
    --published=<version>  Version currently published on PyPI
    --output=<file>       Write 'true'/'false' to this file

"""

import logging
import sys
import tomllib
from pathlib import Path

import docopt
from packaging.version import InvalidVersion, parse

logger = logging.getLogger("checkAcurlVersion")

EXIT_OK = 0
EXIT_FAILURE = 1

ACURL_PYPROJECT = Path(__file__).resolve().parent.parent / "acurl" / "pyproject.toml"


def local_version():
    data = tomllib.loads(ACURL_PYPROJECT.read_text())
    try:
        return data["project"]["version"]
    except KeyError as exc:
        raise KeyError(f"no [project].version in {ACURL_PYPROJECT}") from exc


def main():
    opts = docopt.docopt(__doc__)
    logging.basicConfig(
        level="INFO",
        format="[%(asctime)s] <%(levelname)s> [%(name)s] [%(funcName)s] %(message)s",
    )

    published = opts["--published"]

    try:
        local = local_version()
        changed = parse(local) != parse(published)
    except (OSError, KeyError, tomllib.TOMLDecodeError, InvalidVersion) as exc:
        logger.error("could not compare acurl versions: %s", exc)
        return EXIT_FAILURE

    if changed:
        logger.info("acurl %s -> %s; will publish", published, local)
    else:
        logger.info("acurl unchanged at %s", published)

    Path(opts["--output"]).write_text("true" if changed else "false")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
