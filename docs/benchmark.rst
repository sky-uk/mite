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

Times are in milliseconds.

.. important::

   ``0`` means different things for different thresholds:

   - **Errors**: ``0`` means **no errors are allowed**.  This is the
     default for ``--max-errors-threshold``, so by default a single error
     fails the run.
   - **Everything else** (response times, standard deviations and
     percentiles): ``0`` means the check is **not run**.  This is the
     default for all of them.

======================================================  ===========================================================
Option                                                  Fails the run when
======================================================  ===========================================================
``--max-errors-threshold=N``                            more than ``N`` errors and exceptions were raised (``0``: none allowed)
``--max-response-time-threshold=MS``                    the slowest response took longer than ``MS``
``--mean-response-time-threshold=MS``                   the mean response time is greater than ``MS``
``--standard-deviation-response-time-threshold=MS``     the response time standard deviation is greater than ``MS``
``--standard-deviation-req-sec-threshold=N``            the requests per second standard deviation is greater than ``N``
``--benchmark-percentiles=...``                         a percentile is at or above its threshold (``--report`` only)
======================================================  ===========================================================

Response times are taken from the ``total_time`` of each HTTP request
(and Selenium page load and network resource), not from the duration of
the transactions or journeys around them.

Percentiles and error thresholds
--------------------------------

``--benchmark-percentiles`` sets which percentiles appear in the report
and, optionally, a threshold for each.  Despite its name, the
per-transaction form below can also set error thresholds.  It takes one
of two forms.

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
       "*": {50: 0, 90: 400, 98: 1100, 99: 0, "max_errors_threshold": 5},
       "Log in": {90: 300, 99: 800, "max_errors_threshold": 0},
       "Log in :: Fetch token": {99: 500},
   }

.. code-block:: sh

   --benchmark-percentiles=my_tests.benchmarks:login_benchmark

Each value is a dictionary of settings:

- **Integer keys** are percentiles (1 to 99), mapped to a threshold in
  milliseconds.  ``0`` means report only.
- **``"max_errors_threshold"``** is the maximum number of errors and
  exceptions allowed, matching ``--max-errors-threshold``.  **``0``
  means no errors are allowed**, not that the check is off.  To skip the
  error check, leave the key out.

Any other string key is rejected.

- ``"*"`` sets the percentiles for the run as a whole, exactly as the
  inline form does.  It is a literal key, not a wildcard pattern.  If it
  is left out, the default ``50:0,90:0,98:0,99:0`` is used.
- A ``"max_errors_threshold"`` in ``"*"`` replaces
  ``--max-errors-threshold`` for the run as a whole.  Without one, the
  command-line option (default ``0``) still applies.
- Every other key is a transaction name, as passed to
  ``ctx.transaction(...)``, and must match exactly.  Nested transactions
  use their full name, joined with ``" :: "``; a request is only counted
  against its innermost transaction, not its parents.
- A transaction's percentiles replace the ``"*"`` percentiles for that
  transaction; they are not merged.
- Only the transactions listed are reported and checked.  Requests and
  errors in any other transaction, or outside a transaction, still count
  towards the run as a whole.
- A transaction's errors are only checked if it sets
  ``"max_errors_threshold"``.  An error is counted against the innermost
  transaction it was raised in.
- Transactions with the same name in different journeys are combined.

The two forms are told apart by the first character: inline values start
with a digit, and Python module names cannot.

The report
----------

The report has two tables, **Latency** and **Req/Sec**, followed by a
summary of total requests, duration and data transferred.  Each table
has one row for the run as a whole, labelled ``*`` to match the config
key, followed by one row per configured transaction in alphabetical
order.  Without a per-transaction config there is only the ``*`` row.

.. code-block:: text

   Latency
   +---------------+----------+-----+----------+------------+------------+--------+
   | Transaction   |   Avg    | ... | 50 %tile |  90 %tile  |  99 %tile  | Errors |
   +---------------+----------+-----+----------+------------+------------+--------+
   | *             | 169.57ms | ... | 120.00ms | 560.00ms ✗ |  776.00ms  |  2 ✗   |
   |               |          |     |          |   <400ms   |            |   ≤0   |
   +---------------+----------+-----+----------+------------+------------+--------+
   | Fetch profile | 600.00ms | ... |    -     |     -      | 796.00ms ✗ |  1 ✓   |
   |               |          |     |          |            |   <650ms   |   ≤3   |
   +---------------+----------+-----+----------+------------+------------+--------+
   ✓ pass  ✗ fail  Limits: <ms for percentiles, ≤count for errors (≤0 = no errors allowed)

**Latency** shows the mean, minimum, maximum, standard deviation, the
percentage of responses within one standard deviation of the mean, a
column for every percentile used by any row, and the error count.

- Where a result has a threshold, the cell is coloured, marked ``✓``
  (pass) or ``✗`` (fail), and shows the limit underneath: ``<400ms``
  for a percentile, which must be below its threshold, and ``≤3`` for
  errors, which may equal theirs.  ``≤0`` means no errors are allowed.
- A result without a threshold shows just the value.
- ``-`` marks a percentile that row doesn't report.
- The ``*`` row always has an error limit: the ``"*"``
  ``max_errors_threshold`` if set, otherwise ``--max-errors-threshold``.
  A transaction only has one if it sets ``max_errors_threshold``.

**Req/Sec** shows the same statistics for requests per second, sampled
every two seconds, with each row's request and error counts.

``N/A`` is shown where there isn't enough data: percentiles and standard
deviations need at least two samples.  A percentile threshold that can't
be checked for this reason is logged as a warning rather than failing the
run, as is a configured transaction that recorded no responses (usually a
sign its name doesn't match).
