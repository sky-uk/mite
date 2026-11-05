=================
Benchmark testing
=================

A benchmark run is a short ``mite scenario test`` (or ``mite journey
test``) that prints a summary report at the end and sets a non-zero exit
status if any threshold is breached.  This makes it suitable as a
pass/fail gate in a CI pipeline.

Running a benchmark
-------------------

Add ``--report`` to a local test run:

.. code-block:: sh

   mite scenario test my_tests.scenarios:benchmark_scenario \
       --report \
       --hide-constant-logs \
       --max-errors-threshold=0 \
       --benchmark-percentiles=50:0,90:400,98:1100,99:0

``--hide-constant-logs`` hides the stats that are otherwise logged every
two seconds, leaving just the final report.

When the run finishes, mite checks each threshold, logs an error for every
breach and exits with status 1 if there were any.

Thresholds
----------

All thresholds default to ``0``, which means the check is not run.  Times
are in milliseconds.

======================================================  ===========================================================
Option                                                  Fails the run when
======================================================  ===========================================================
``--max-errors-threshold=N``                            more than ``N`` errors and exceptions were raised
``--max-response-time-threshold=MS``                    the slowest response took longer than ``MS``
``--mean-response-time-threshold=MS``                   the mean response time is greater than ``MS``
``--standard-deviation-response-time-threshold=MS``     the response time standard deviation is greater than ``MS``
``--standard-deviation-req-sec-threshold=N``            the requests per second standard deviation is greater than ``N``
``--benchmark-percentiles=...``                         a percentile is at or above its threshold (``--report`` only)
======================================================  ===========================================================

Response times are taken from the ``total_time`` of each HTTP request
(and Selenium page load and network resource), not from the duration of
the transactions or journeys around them.

Percentiles
-----------

``--benchmark-percentiles`` sets which percentiles appear in the report
and, optionally, a threshold for each.  It takes one of two forms.

Inline
~~~~~~

A comma-separated list of ``percentile:threshold`` pairs:

.. code-block:: sh

   --benchmark-percentiles=50:0,90:400,98:1100,99:0

Percentiles must be whole numbers from 1 to 99.  A threshold of ``0``
reports the percentile without checking it.  If the option is left out,
``50:0,90:0,98:0,99:0`` is used.

These percentiles apply to every response in the run, combined.

Per transaction
~~~~~~~~~~~~~~~

To also report and check individual transactions, pass a spec
(``python.module:name_in_module``, as for scenarios and ``--config``)
naming a dictionary:

.. code-block:: python

   # my_tests/benchmarks.py
   login_benchmark = {
       "*": {50: 0, 90: 400, 98: 1100, 99: 0},
       "Log in": {90: 300, 99: 800},
       "Log in :: Fetch token": {99: 500},
   }

.. code-block:: sh

   --benchmark-percentiles=my_tests.benchmarks:login_benchmark

Each value maps percentiles to thresholds in milliseconds, with ``0``
meaning "report only".

- ``"*"`` sets the percentiles for the run as a whole, exactly as the
  inline form does.  It is a literal key, not a wildcard pattern.  If it
  is left out, the default ``50:0,90:0,98:0,99:0`` is used.
- Every other key is a transaction name, as passed to
  ``ctx.transaction(...)``, and must match exactly.  Nested transactions
  use their full name, joined with ``" :: "``; a request is only counted
  against its innermost transaction, not its parents.
- A transaction's percentiles replace the ``"*"`` percentiles for that
  transaction; they are not merged.
- Only the transactions listed are reported and checked.  Requests in any
  other transaction, or outside a transaction, still count towards the
  run as a whole.
- Transactions with the same name in different journeys are combined.

The two forms are told apart by the first character: inline values start
with a digit, and Python module names cannot.

The report
----------

The report shows:

- **Latency**: mean, minimum, maximum, standard deviation, the
  percentage of responses within one standard deviation of the mean, and
  the configured percentiles.  Percentiles with a threshold are coloured
  and marked ``✓`` (pass) or ``✗`` (fail), with the thresholds in the row
  below.
- **Req/Sec**: the same statistics for requests per second, sampled every
  two seconds.
- **Per Transaction**: when transactions are configured, a latency table
  and a requests table (including request and error counts) with one row
  per transaction.  The latency table has a column for every percentile
  used by any transaction; ``-`` marks a percentile a transaction doesn't
  report.
- **Summary**: total requests, duration and data transferred.

``N/A`` is shown where there isn't enough data: percentiles and standard
deviations need at least two samples.  A percentile threshold that can't
be checked for this reason is logged as a warning rather than failing the
run, as is a configured transaction that recorded no responses (usually a
sign its name doesn't match).
