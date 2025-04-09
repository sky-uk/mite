===================
Prometheus and mite
===================

.. _prometheus-doc:

Mite is designed to output the data on its performance tests to
`prometheus <https://prometheus.io/>`_ (for storage, indexing, and
machine-readable retrievability) and then `grafana
<https://grafana.com/>`_ (for data visualization and analysis).  In the
following sections, weʼll discuss some of the details involved in
configuring these applications.

Prometheus
----------

Prometheus collects its metrics by scraping an http endpoint at a
defined interval.  It should be configured to point to port 9301 on the
machine where the ``mite prometheus_exporter`` command runs.  Here is a
minimal ``prometheus.yml`` config file:

.. code-block:: yaml

   global:
     scrape_interval: 1s

   scrape_configs:
     - job_name: 'mite'
       static_configs:
         - targets: ['127.0.0.1:9301']

The ``targets`` is configured on the assumption that the prometheus
process runs on the same machine as the mite exporter process (as is the
case in our teamʼs :ref:`virtual machine deployment <vm-deployment>`).
If this is not the case, you will have to change the localhost IP to an
actual IP or hostname (as well as making sure that the mite box is
accessible to the prometheus from a firewall perspective).

Grafana
-------

The grafana instance you are using will need to be set up with your
prometheus as a data source.  `The Prometheus documentation`_ has an
example of how to accomplish this.  We provide `a dashboard`_ which is
pre-configured for mite.  The dashboard assumes that you have several
applications under test, which will have their measurements tagged in
Prometheus with an ``application`` label.  You will need to edit the
`dashboard variables`_ so that they reflect the names of your
applications.  (Otherwise, you can take out the ``application=~$app``
query from all the dashboard panels).  As the grafana documentation
points out, you will also need to edit the datasource of the dashboard
to match the prometheus instance you configured grafana with.

.. _The Prometheus documentation: https://prometheus.io/docs/visualization/grafana/
.. _a dashboard: https://github.com/sky-uk/id-mite-nft/blob/master/provisioning/grafana/dashboard-json/mite.json
.. _dashboard variables: https://grafana.com/docs/reference/templating/
