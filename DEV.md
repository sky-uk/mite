# Running tests

## Unit tests

Run the unit tests on all supported python versions (currently 3.7 and
3.8), including a code-coverage report:

```
cd /path/to/mite
tox
```

This requires that you have python 3.7 and 3.8 installed locally (on
ubuntu – specifically the dingo release – `sudo apt install python3.7
python3.8`).  You will also need tox installed globally (or in the
virtualenv you use for development).  You can view a hyperlinked
version of the source annotated according to coverage with:

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