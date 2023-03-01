# Git workflow

To set up the pre-commit hooks for this project, run:

```
pip install -r dev-requirements.txt
pre-commit install
```

This will run a linter and formatter on the code before you check it in.
It will deny any checkins that do not conform to the projectʼs style
guidelines.  To run the checkers yourself, run `flake8` (linter) and
`black` (formatter) in the project directory.

# Releasing

## Public

Not yet authorized

## Internal

See the documentation in `DEV.md` in the `id-mite-nft` repo.

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

Run the unit tests on all supported python versions (currently 3.9,
3.10, and 3.11), including a code-coverage report:

```
cd /path/to/mite
tox
```

This requires that you have python 3.9, 3.10, and 3.11 installed locally (on
ubuntu `sudo apt install python3.9 python3.10 python3.11` after adding the
[deadsnakes
PPA](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa)).  You will
also need tox installed globally (or in the virtualenv you use for
development).  You can view a hyperlinked version of the source
annotated according to coverage with:

```
coverage html
<web-browser> coverage_html_report/index.html
```

## Performance tests

Requires docker:

```
cd test/perf
./run-perftest.sh
```

The output will be in the `test/perf/output` directory, in a
subdirectory named according to the current data, and another
subdirectory named according to the time the test was run (GMT) and the
branch name/current git commit.

### Results

The performance test baseline (as of 2019-07-24) is as follows (when run
on AWEʼs Macbook Pro 15 inch 2018, 2.2 GHz i7, 16GB RAM)

#### Scenario 1

Total requests (1 min): 50016

| Process    | Mem   | CPU  |
|------------|-------|------|
| Controller | ~45MB | ~20% |
| Duplicator | ~45MB | ~40% |
| Runner     | ~45MB | ~60% |

#### Scenario 10

Total requests (1 min): 182992

| Process    | Mem   | CPU   |
|------------|-------|-------|
| Controller | ~45MB | ~20%  |
| Duplicator | ~50MB | ~100% |
| Runner     | ~45MB | ~150% |

### Scenario 100

Total requests (1 min): 254812

| Process    | Mem   | CPU       |
|------------|-------|-----------|
| Controller | ~45MB | ~1% !!!   |
| Duplicator | ~55MB | ~115%     |
| Runner     | ~50MB | ~150-175% |

Duplicator memory usage spikes to ~90MB at 25 secs, but is stable
before/after.

#### Scenario 1000

Total requests (1 min): 264299

| Process    | Mem   | CPU     |
|------------|-------|---------|
| Controller | ~45MB | ~1% !!! |
| Duplicator | ~55MB | ~115%   |
| Runner     | ~90MB | ~180%   |

Duplicator memory usage spikes to ~70MB at 20 secs, but is stable before
and after.
