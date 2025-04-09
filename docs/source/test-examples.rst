======================
WIP - Advance Examples
======================

How to add metrics 
===================



Custom processessor
===================
You can find how to use it the design-deployment section

**Example custom processors:**

.. code-block:: python

    import os
    from uuid import uuid4

    from mite import collector
    from mite.cli import stats
    from mite.zmq import Sender


    class StatsProcessor:
        def __init__(self):
            sender = Sender()
            sender.bind("tcp://127.0.0.1:14310")
            self.stats = stats.Stats(sender=sender.send)

        def process_message(self, message):
            return self.stats.process(message)

    class CollectorProcessor:
        def __init__(self):
            self.collector = collector.Collector(collector_id=str(uuid4()))

        def process_raw_message(self, message):
            return self.collector.process_raw_message(message)

    class PrintProcessor:
        def process_message(self, message):
            print(message)


Custom stats
=============


Journey examples per modules
============================

Example per module and descriptions to understand
And addition for the metrics and how to use them.

Kafka
-----

HTTP
-----

AMQP 
-----
No longer in use by the team


Browser 
-------
No longer in use by the team

Selenium 
--------
No longer in use by the team

Websockets 
----------
No longer in use by the team

