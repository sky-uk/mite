# Development Setup

## Prerequisites

- Python 3.10-3.12
- [Hatch](https://hatch.pypa.io/) for project management

Install Hatch:
```bash
pip install hatch
```

## Code Quality

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting. All style rules are configured in `pyproject.toml`.

To check your code:
```bash
hatch run lint:check
```

To automatically fix and format code:
```bash
hatch run lint:format-mite
```

For the acurl subproject:
```bash
hatch run lint:acurl-check
hatch run lint:acurl-format
```

# Releasing

## Public

Not yet authorized

## Internal

Jenkins job **`mite-manual-release`** (`cd.yml`), triggered manually. Entry point
is `cd-scripts/manualRelease.sh`. Requires `PYPI_TOKEN` in the agent environment.

### Trigger

One parameter, selected when the job is run:

| Parameter | Values | Effect |
|---|---|---|
| `VERSION_INCREMENT_TYPE` | `patch` / `minor` / `major` | Which segment of **mite's** version to bump |

This parameter affects mite only. **acurl is versioned independently** — publishing
it requires bumping `version` in `acurl/pyproject.toml` by hand; the release job
detects that automatically (see "Versioning" below) and does not need a
separate trigger.

### What the job does, in order

```
1. isOnMaster          -> not on master? exit 0, nothing happens
2. assertReleasable    -> PYPI_TOKEN set? valid increment type? working tree clean?
3. checkAcurl          -> local acurl version != published PyPI version? -> ACURL_CHANGED
4. tag-create          -> create the next mite version tag LOCALLY (not pushed yet)
5. buildLinuxWheels    -> mite sdist+wheel; acurl manylinux wheels + sdist (if ACURL_CHANGED)
6. twine check         -> validate every artifact before anything is uploaded
7. twine upload         -> publish to PyPI
8. tag-push            -> push the mite tag to origin -- LAST, only after a successful upload
```

If anything in steps 5-7 fails, the local tag from step 4 is deleted automatically.
Nothing is left on `origin`; the next attempt starts from a clean state.

### Versioning

- **mite** — derived from git tags by `hatch-vcs`
  (`git describe --dirty --tags --long --match 'v*'`). The release tag must exist
  *before* the build, because the build reads the version from it. The next
  version is the highest existing `v*` tag plus the selected increment.
- **acurl** — a plain `version` string in `acurl/pyproject.toml`, bumped by hand in
  the PR that changes acurl. Published automatically on the next release run after
  that version differs from what's currently on PyPI.

### Artifacts

| Project | Output directory | Contents |
|---|---|---|
| mite | `wheelhouse-mite/` | pure-Python wheel + sdist |
| acurl | `wheelhouse-acurl/` | manylinux x86_64 wheels (cp310-cp313) + sdist |

acurl wheels are built with `cibuildwheel`, and each wheel's own test suite runs
**inside its build container** before upload — a wheel is never published without
first passing its tests on the exact interpreter it was built for.

### Operator notes

- **Triggered on a non-master branch** -> exits 0 silently. This is expected, not
  an error.
- **Commit already tagged** -> mite's release is skipped; acurl may still publish
  if its version changed independently.
- **Dirty working tree** -> the job refuses to release. `hatch-vcs`'s `--dirty`
  flag would otherwise produce a version PyPI rejects, and that would only be
  discovered after tagging and building — the job checks this upfront instead.
- **Retrying a failed release is safe.** Uploads use `--skip-existing`, and a
  failed attempt never leaves an orphan tag, so simply re-running the job after
  fixing whatever broke is the correct recovery — no manual tag cleanup needed.
- **The release toolchain is pinned** (`[tool.hatch.envs.release]` in
  `pyproject.toml`) — `cibuildwheel`, `twine`, and `build` versions are fixed, so
  the job's behaviour doesn't drift between runs.
- **`origin/master` tags are the source of truth for the next version.** Keep a
  local clone's tags in sync with `git fetch --tags --force` before relying on
  `git describe` locally — a stale or local-only tag will compute the wrong next
  version.

# Docs

The docs are built with Sphinx, from a mix of `.rst` and Markdown sources
under `docs/`. Build them with:

```
hatch run docs:build
```

The output lands in `docs/_build/html`. Warnings are treated as errors, so a
broken cross-reference or a page missing from the toctree in `docs/index.rst`
will fail the build rather than publish silently. `hatch run docs:clean`
removes the build directory.

To push a new version of the docs

```
# Install graphviz on your system (On MacOS: brew install graphviz)
# somewhere on your machine
MITE_DOCS_PATH=`pwd`
git clone git@github.com:sky-uk/mite.git mite-docs
cd mite-docs
git checkout gh-pages
# cd back to the mite checkout
hatch run docs:build
cp -r docs/_build/html/* $MITE_DOCS_PATH/mite-docs
cd $MITE_DOCS_PATH/mite-docs
git add .
git commit -m "update docs"
git push
```

# Running tests

## Unit tests

Run the unit tests on all supported Python versions (currently 3.10-3.13):

```bash
hatch run test:test
```

Run tests with coverage report:
```bash
hatch run test:test-cov
```

View the HTML coverage report:
```bash
hatch run test:cov-report
```

Run acurl tests:
```bash
hatch run test:acurl-test
```

The tests will automatically run on every installed Python version in the matrix (3.10-3.13) if you have them installed. Hatch will manage the virtual environments for you.

## Performance tests

Run the performance tests using Hatch:

```bash
hatch run perf-test:perf-test
```

The output will be in the `output` directory (configured via `MITE_PERFTEST_OUT` environment variable).

### Results

The performance test results (as of 2025-11-19) running on macOS with Apple Silicon:

#### Scenario 1

Total requests (1 min): 143,879

| Process    | Mem   | CPU   |
|------------|-------|-------|
| Controller | ~37MB | ~16%  |
| Duplicator | ~35MB | ~13%  |
| Runner     | ~44MB | ~53%  |

#### Scenario 10

Total requests (1 min): 543,132

| Process    | Mem   | CPU   |
|------------|-------|-------|
| Controller | ~41MB | ~22%  |
| Duplicator | ~40MB | ~35%  |
| Runner     | ~47MB | ~123% |

#### Scenario 100

Total requests (1 min): 785,389

| Process    | Mem   | CPU   |
|------------|-------|-------|
| Controller | ~25MB | ~6%   |
| Duplicator | ~25MB | ~27%  |
| Runner     | ~54MB | ~120% |

#### Scenario 1000

Total requests (1 min): 681,760

| Process    | Mem   | CPU   |
|------------|-------|-------|
| Controller | ~38MB | ~2%   |
| Duplicator | ~39MB | ~22%  |
| Runner     | ~104MB| ~114% |
