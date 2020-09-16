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
  (For more on how mite tests are organized, see the `README`_)
- runner: responsible for injecting the test load into the target system
- duplicator*: a message router between the controller/runner and their
  downstream components
- collector: logs messages appearing on the mite message bus to a file
- receiver: dispatches incoming messages to connected ``processors``
- recorder*: listens for special messages on the bus and records them
  to a file. This is used for :ref:`data creation scenarios <data-creation-scenarios>`.
- stats: aggregates raw messages from the controller and runner into
  statistical summaries
- exporter*: (aka prometheus exporter) listens for aggregations from the
  stats component, and exposes these via HTTP to a
  :ref:`Prometheus instance <prometheus-doc>`

.. _README: https://github.com/sky-uk/mite#your-first-scenario

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


Useful topologies
=================

While itʼs true that increasing the heft of a test scenario increases
the load on all miteʼs components, nowhere is the increase more apparent
than on the runners, the component directly responsible for injecting
the load on a 1:1 basis into the target system.  Therefore, it makes the
most sense to separate the runners from the other components of mite.
This both avoids interference between the components and makes it easy
to scale the resources devoted to the runners.

A note on resource usage
------------------------

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

.. _vm-deployment:

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
