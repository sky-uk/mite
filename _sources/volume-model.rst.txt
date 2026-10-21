==========================
Volume model specification
==========================

A mite volume model should be a callable accepting two arguments, the
start and end times (in seconds).  It should return an integer,
indicating the number of transaction per second to run during this
interval.  There are several ways to specify the volume model for a
scenario.

The simplest is by using an anonymous (lambda) function:

.. code-block:: python

   lambda start, end: return 10

More complex named functions can also be used.

Mite also provides a simple DSL for specifying volume models, in the
``mite.volume_model`` module.  The components of the DSL are:

``Nothing(duration=1)``
   Zero TPS for the specified duration

``Constant(tps=1, duration=10)``
   A constant number of tps for the specified duration

``Ramp(duration=10)``
   A smooth (linear) transition between the two volume model components
   on either side of the ramp term.  If the ramp appears between two
   components, then the from and to values are automatically computed to
   match those.  If the ramp is the first component in a chain, then
   pass the ``frm`` argument in addition to ``duration``; if it is the
   last in a chain pass the ``to`` argument.

You can combine pieces of this DSL using the addition operator.  For
example, here is a volume model which runs an initial 1-minute warm-up
period, followed by an hour-long trapezoidal load pattern (ramp up for 5
minutes, maintain for 50 minutes, ramp down for 5 minutes):

.. code-block:: python

   from mite.volume_model import Constant, Ramp

   volume_model = Constant(tps=1, duration=60) + Ramp(duration=300) + \
       Constant(tps=1000, duration=50) + Ramp(duration=300, to=0)
