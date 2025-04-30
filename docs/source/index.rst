.. Mite documentation master file, created by
   sphinx-quickstart on Thu Mar 27 14:54:31 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Mite documentation
==================

Mite is an open source performance testing framework created by the performance
testing in Sky UK's Identity group.

We use mite for:

* Apps Performance testing (soak, peak and scalability tests).
* Test our internal Kafka consumers and producers.
* Inject data direclty in our data base to test the DB itself or to generate our datapools.

.. admonition:: Modules currently supported
   :class: caution

   We currently fully support *Kafka* and *HTTP* modules.
   The other modules should still work but we are not activetely supporting them so please be mindful when using them and 
   please be patient if you need our support with any of those.


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   introduction
   installation
   quick-start
   design-deployment
   data-visualization
   test-examples
.. contributing-guidelines
.. api-references - it's not worth to show it if not completed.


..
   Indices and tables
   ==================

   * :ref:`genindex`
   * :ref:`modindex`
   * :ref:`search`