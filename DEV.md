# Development Setup

## Prerequisites

- Python 3.10 or 3.11
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

See the documentation in `DEV.md` in the `sky-id-mite-nft` repo.

# Docs

To push a new version of the docs

```
# Install graphviz on your system (On MacOS: brew install graphviz)
pip install sphinx
# somewhere on your machine
MITE_DOCS_PATH=`pwd`
git clone git@github.com:sky-uk/mite.git mite-docs
cd mite-docs
git checkout gh-pages
# cd back to the mite checkout
cd docs
make html
cp -r _build/html/* $MITE_DOCS_PATH/mite-docs
cd $MITE_DOCS_PATH/mite-docs
git add .
git commit -m "update docs"
git push
```

# Running tests

## Unit tests

Run the unit tests on all supported Python versions (currently 3.10 and 3.11):

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

The tests will automatically run on both Python 3.10 and 3.11 if you have them installed. Hatch will manage the virtual environments for you.

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
