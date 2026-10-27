Mite: the mighty performance testing framework
==============================================

Mite is a performance testing framework created by the performance
testing in Sky UKʼs Identity group.  The philosophy driving the effort
was simple:

1. Scalability.  The apps that we test are scalable, distributed systems;
   our performance testing framework should be as well.
2. Maintainability.  As software engineers, we have a full arsenal of
   information organization and reuse techniques.  We should treat our
   performance tests as code, and bring these same techniques to bear.
3. Snakiness.  Python is the best language for us to accomplish our
   goals for the project.

We use mite for:

* application performance testing — soak, peak and scalability runs
* exercising our internal Kafka consumers and producers
* writing directly into a database, either to test the database itself
  or to build the datapools a test will later draw on

.. admonition:: Module support
   :class: note

   The Kafka, HTTP and InfluxDB integrations are the ones we actively
   use and support.

   The rest still work and are documented here deliberately: other teams
   might still use them, and we would rather they stay discoverable than quietly
   disappear.  Expect less from us on those. Contributions to any of
   them are welcome.

Contributing
------------

Bug reports, questions and pull requests are welcome. See
`CONTRIBUTING <https://github.com/sky-uk/mite/blob/master/CONTRIBUTING.md>`_
for the workflow, coding standards, and how to reach the maintainers.


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   tutorial
   components
   journeys
   volume-model
   config
   design-deployment
   prometheus
   stats
   influxdb
   otel
   plugins/index


..
   Indices and tables
   ==================

   * :ref:`genindex`
   * :ref:`modindex`
   * :ref:`search`
