===============
Mite components
===============

Distributed components
======================

In order to achieve high throughput, it's necessary to split mite into
discrete components and distribute them across cores/machines.  Mite as
an entity consists of a number of these components, each with their own
responsibilities for test control, execution and/or data collection.

Duplicator
----------

The mite duplicator is responsible for ingesting messages from multiple
sources and then duplicating them to other components.  It ensures that
messages that arrive at an incoming socket are distributed exactly once
to each of N outgoing sockets.  It is usually the first component to
start.  The controller and runners feed their logs into the duplicator
and cannot run without it.  Only one duplicator can run at a time.

To start the duplicator with one inbound socket (``--message-socket``)
and two outbound sockets (the remaining arguments) for the stats and
collector components, run the following.

.. code-block:: sh

   mite duplicator --message-socket=tcp://0.0.0.0:14302 tcp://127.0.0.1:14303 tcp://127.0.0.1:14304

Stats
-----

The mite stats component aggregates statistics out of the messages
passed from the collector.  As many stats daemons can be run as is
necessary to achieve desired throughput. It can be passed an optional
in and out socket, but in our case we'll just run it with default
sockets.

.. code-block:: sh

    mite stats

The default in socket is ``tcp://127.0.0.1:14304``` which we previously
told our duplicator to output on.  The default output socket is on
port 14305.

Collector
---------

The mite collector is an optional component designed to write the raw
logs to files.  It defaults to writing 10000 log lines to a file before
rolling and timestamping the file.  The most recent file is named
``current``.  Again, as many of these can be run as is necessary to
achieve throughput.  However, each collector must be passed a different
``--collector-dir``, to avoid them overwriting each otherʼs logs.  The
log lines will be round-robined across all the collectorsʼ output
directories.

.. code-block:: sh

   mite collector --collector-dir mite-logs

Recorder
--------

The mite recorder is an optional component designed to record data to
disk.  It can be used for storing values created during data creation
scenarios (TODO: link), handling messages of the type ``data_created``
to write data and ``purge_data`` to delete old recorded values.  There
is an optional ``--recorder-dir`` argument to specify a folder where
files are created.

.. code-block:: sh

   mite recorder

Logs are compressed with `msgpack`_; the repo includes a ``cat_msgpack.py``
script for quickly dumping their contents (but the most common usage will
be to read them in programmatically in test journey files).  We could also
have specified an optional inbound socket but here we are relying on the
default of ``tcp://127.0.0.1:14303``, previously specified as an output
socket for the duplicator.

.. _msgpack: https://msgpack.org/index.html

Prometheus Exporter
-------------------

The prometheus exporter provides a http metrics endpoint for the
:ref:`prometheus <prometheus-doc>` time series database to scrape,
pulling metrics from the stats components.  In our case, the stats
components will output on its default socket and the exporter is
configured to read from there by default.

.. code-block:: sh

   mite prometheus_exporter


.. _prometheus: https://prometheus.io/

Runners
-------

The mite runners are the component responsible for injecting the load
into the system under test.  As many of these can be created as is
necessary for the volume of load you are injecting, but for optimum
performance you should make sure that each has a whole CPU core on
which to run.  The runner needs two arguments, a socket it can use to
talk to the controller and a message socket it can use to send messages
to the duplicator.  In the below instance we'll let it use the defaults
of 14301 for communicating with the controller and 14302 for  messages
out to the duplicator.

.. code-block:: sh

    mite runner

Controller
----------

The last component to run is the mite controller.  It dictates the
scenario to run, loads and distrbutes the config to the runners and is
responsible for managing the work that the runners are doing.  As all
our components are set up to use default sockets, we just have to
specify the scenario to run, in the format of a python importable module
and a name in that module (separated by a colon).

.. code-block:: sh

    mite controller mite.example:scenario
