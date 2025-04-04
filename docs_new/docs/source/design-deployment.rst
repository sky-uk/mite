=====================
Design and deployment
=====================

Design of mite
==============

Mite is designed as a distributed system made up of several components.
Some are required, and others are optional.  The components communicate
over TCP, so you can run them anywhere that they can talk to each other
in this fashion: as ordinary processes on a single machine, in
containers (on a single machine or in a cloud container orchestration
environment like Kubernetes) or on different machines entirely.

The components that make up mite are:

- controller*: manages a test scenario and feeds tasks to the runners.
- runner: responsible for injecting the test load into the target system
- duplicator*: a message router between the controller/runner and their
  downstream components
- collector: logs messages appearing on the mite message bus to a file
- receiver: dispatches incoming messages to connected ``processors``
- recorder*: listens for special messages on the bus and records them
  to a file. 
.. This is used for :doc:`data creation scenarios <data-creation-scenarios>`.
- stats: aggregates raw messages from the controller and runner into
  statistical summaries
- exporter*: (aka prometheus exporter) listens for aggregations from the
  stats component, and exposes these via HTTP to a 
.. :ref:`Prometheus instance <prometheus-doc>`


The components marked with an asterisk are singletons; the rest can be
scaled up to meet the demand of the test.  The communication pathways
between the components are represented in the following diagram:

.. graphviz::

   digraph architecture {

   runner -> duplicator;
   controller -> duplicator;
   duplicator -> stats;
   duplicator -> collector;
   duplicator -> recorder;
   stats -> exporter;

   subgraph cluster_receiver {
     graph[style=dotted];
     node [style=filled];
     stats collector;
     label = "receiver                                   ";
     color=black;
   }

   subgraph rc {
     rank="same"
     runner
     controller
     runner -> controller [dir=both, label = "    "];
   }

  }


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
disk.  It can be used for storing values created during

.. :ref:`data creation scenarios <data-creation-scenarios>`, 

handling
messages of the type ``data_created`` to write data and ``purge_data``
to delete old recorded values.  There is an optional ``--recorder-dir``
argument to specify a folder where files are created.

.. code-block:: sh

   mite recorder

Logs are compressed with `msgpack`_; the repo includes a ``cat_msgpack.py``
script for quickly dumping their contents (but the most common usage will
be to read them in programmatically in test journey files).  We could also
have specified an optional inbound socket but here we are relying on the
default of ``tcp://127.0.0.1:14303``, previously specified as an output
socket for the duplicator.

.. _msgpack: https://msgpack.org/index.html


Receiver
--------

The mite receiver component is a generic mechanism that can perform tasks
not limited to fulfilling a single role (eg. stats, collector). This allows
changing a mite pipeline more easily, without introducing new processes and
network components. A ``mite.cli.receiver`` instance can have multiple custom
``processors`` connected to it as either listeners or raw listeners and can
dispatch incoming messages to them.

.. code-block:: sh

   mite receiver tcp://127.0.0.1:14303 \
    --processor=my.custom.processors:StatsProcessor \
    --processor=my.custom.processors:CollectorProcessor

   mite receiver tcp://127.0.0.1:14310 \
    --processor=my.custom.processors:PrintProcessor



Prometheus Exporter
-------------------

The prometheus exporter provides a http metrics endpoint for the time series database to scrape,
pulling metrics from the stats components.  In our case, the stats
components will output on its default socket and the exporter is
configured to read from there by default.

.. code-block:: sh

   mite prometheus_exporter

There is more about data visualization in the next page (:doc:`Data visualization<../data-visualization>`).

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



.. _useful-topologies:

Useful topologies
=================

While itʼs true that increasing the heft of a test scenario increases
the load on all miteʼs components, nowhere is the increase more apparent
than on the runners, the component directly responsible for injecting
the load on a 1:1 basis into the target system.  Therefore, it makes the
most sense to separate the runners from the other components of mite.
This both avoids interference between the components and makes it easy
to scale the resources devoted to the runners.


.. admonition:: Resource usage
    :class: note

    In the following sections, we describe our “real-world” usage of mite.
    This infrastructure is somewhat overprovisioned for our needs, but our
    focus has been on the performance of the applications which we test.
    While not wishing to be profligate, we believe it would be a mistake to
    shrink the injection infrastructure close to its performance limits.
    When resource constraints appear in an NFT exercise, they should stem
    from the system under test and not the test apparatus.  Anything other
    than the most occasional exception to this rule is an indication that
    the NFT is not efficiently organized.

    In fact, we have reason to believe that the peak performance of mite, in
    terms of maximum throughput per CPU and memory devoted to running mite,
    is significantly above what is implied by these numbers.  Furthermore,
    our resource usage already compares favorably with other performance
    engineering teams in Sky using different tools, even without having
    performed a dedicated performance tuning of our injection
    infrastructure.


Single machine
--------------

In the doc/example/ directory, you will find a docker-compose.yml file
which will deploy a full mite stack, along with supporting programs, on
your local machine.  While impractical for running a significant load
injection exercise (due to the performance limitations of a single
machine), this serves to illustrate the mechanics of getting the
components to talk to each other and the outside world.  For a concrete,
configuration-level view of setting up a mite pipeline, the reader is
referred to the files in that directory.  In the sections that follow,
we will discuss a few more abstract considerations for deploying mite in
different kinds of environments.

Virtual machines
----------------

At Sky, we have run mite in a configuration with 4 virtual machines.  One,
with 16GB of memory and 16 cores, hosts the controller, duplicator, stats,
exporter, and (if warranted) collector and recorder.  The other three have
8GB of memory and 16 cores each, and each host 16 runner processes.  Our
system under test consists of a 1:1 replica of the production environment,
deployed with each weekly release candidate.  The underlying hardware is
in a corporate datacentre (though it could just as easily correspond to
servers rented from a colocation facility or VM provider).  We regard
this as fairly typical of a traditional NFT setup in a medium to large
tech company.

We have used this infrastructure to inject load of up to 12k tps into
our system under test across a variety of journeys, including some which
simulate full user interaction with the platform, i.e. signin → modify
data → signout.

(Note that the provisioning of our test injection infrastructure is also
undercharacterized above: far more important than memory for the runners
is the bandwidth from them to the system under test – which is also less
straightforward to quantify in the than VM size.  Our injectors and
system under test are colocated in the same datacentres, both on the
inside of the corporate firewall.  This provides ample bandwidth for our
use case.)

We hope that this description of our usage will provide you with an idea
of the scale of infrastructure which mite requires to run, and will help
you to architect your deployment as well.

The Cloud
---------

In addition to the traditional VM-based deployment described above, we
have also used mite in a “cloud” environment – specifically in a
kubernetes cluster.  As above this is provisioned by the company, but
could just as easily be part of a hosted kubernetes offering such as
GKE.

In addition to the difference in the space into which the applications
are deployed, this environment also comes with a different release
cadence: continuous delivery is used with nightly NFT runs (recycling
the resources that are used to run CI testing during the day as
developers work on the code).  Finally, the environment also has NFRs
that are roughly an order of magnitude larger than the traditional
VM-based one.

Mite as a distributed system made of discrete units is in many ways
well-adapted to such an environment.  We have deployed it into the cluster
with the following resource allocations:


==========    ========  ====    ======
Component     Replicas  CPU     Memory
==========    ========  ====    ======
Controller    1         2       500MB
Duplicator    1         2       100MB
Exporter      1         0.25    100MB
Runner        50        1       500MB
Stats         20        1       50MB
==========    ========  ====    ======

For injecting loads of up to 22k tps, we have found 50 runners and 20
stats to be more than sufficient.  (We have noted that the abstract
“CPU” is more performant in this environment than in the VMs in the
previous section.)  As before, the network bandwidth used by mite in
this environment is not characterized; we have not run into problems
with our assumption that all the relevant pipes are fat enough for
within-cluster communication of the scale that we require.
