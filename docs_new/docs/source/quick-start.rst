============
Quick start
============

Writing the first test
======================

Few words regarding mite what we are
going to try to do and some ideas on how to use it .

Before you start
----------------

In order to start writing your first test you'll need:

- A basic understanding of Python
- :doc:`Install Mite <../installation>` on your machine or environment
- A code editor to write the script and access to a terminal to start the test


Basic structure of a test
-------------------------
 
Write a journey
^^^^^^^^^^^^^^^

.. code-block:: python
    
    import asyncio

    async def journey(ctx, arg1, arg2):
        async with ctx.transaction('test1'):
            ctx.send(
                'test_message', 
                content=ctx.config.get('test_msg', 'Not set'), 
                sum=arg1 + arg2
            )
            await asyncio.sleep(0.5)


This journey just sends a log message to be collected by the framework and waits for half a second. 
This journey takes 3 arguments, a context and two numbers (which will be supplied by the datapool, see below).


.. admonition:: About the Context
    :class: important

    The context is important for every journey. It provides a number of useful methods for timing/naming of transactions,
    sending messages and defaults to including http functionality from acurl. Functionality can be included in the journey by attaching it to the context.
    In the above example we see an example of naming a transaction *async with ctx.transaction('test1'):*. This will capture timing for the indented block.
    We also see that the config is attached to the context with *ctx.config.get('test_msg', 'Not set')* and in this case, 
    the value of that config value is sent to the log collector with *ctx.send('test_message', content=ctx.config.get('test_msg', 'Not set'))*


Add a datapool
^^^^^^^^^^^^^^

To feed data into your test journey, you'll need a datapool. Several of these are already provided in mite and usually read data in from an iterable.
To specify a custom datapool implementation, you simply need a class that implements a checkin method which adds data to the pool and a checkout method which 
removes data from the pool to be used by journeys.

For the above journey, which expects two arguments, we will show an example of the *RecyclableIterableDataPool*.

.. code-block:: python

    from mite.datapools import RecyclableIterableDataPool

    datapool = RecyclableIterableDataPool([(i, i+2) for i in range(5000)])


This pool will share data out to runners and check it back in when the runners are done with that block of data. 
In this case it cycles through a list of tuples which each contain two integers.


Test the journey
^^^^^^^^^^^^^^^^

Before going ahead and create and run the scenario, we should test the journey in isolation as a scenario can be made up of multiple journeys. 
This can be done with the mite journey test command. We just need to pass the name of the journey and the datapool it requires:

.. code-block:: sh

    MITE_CONF_test_msg="Hello from mite" \
    mite journey test mite.example:journey mite.example:datapool

If something goes wrong, adding the ``--debugging`` flag to this command will drop excution into a debug session. 
The choice of debugger used can be managed by setting the PYTHONBREAKPOINT environment variable before running mite. 
Python's built-in (*pdb*) debugger is invoked by default, but this can be changed to use, say, the *ipdb* debugger:

.. code-block:: sh

    pip install ipdb
    export PYTHONBREAKPOINT=ipdb.set_trace
    export PYTHONPOSTMORTEM=ipdb.post_mortem

**PYTHONPOSTMORTEM** is a mite-specific extension to PEP 553 which defines the **PYTHONBREAKPOINT** functionality.





Write a Scenario
^^^^^^^^^^^^^^^^

We now need to package the journey, datapool and volume model into a scenario. 
This is a simple as defining a function which returns a list of triplets of (journey name, datapool, volumemodel).

.. code-block:: python

    def scenario():
        return [
            ['mite.example:journey', datapool, volumemodel],
        ]

The journey name should be a string with two parts separated by a colon. The first part is the name of a python module that is importable; 
the second is the name of a journey (an async function) within that module. It is necessary to specify this as a string, rather than as a python object, 
because the journey will be executed in a different python process than the scenario function is. Thus, we need a name for the journey that allows any python process to find it.

The volume model and data pool, on the other hand, are only used in the python process where the scenario function runs. They are both python objects.



Volume model
^^^^^^^^^^^^

A volume model defines how many instances of the journey should be ran within a window of time. 
The window is definied as a start and an end time (measured in seconds since the beginning of the test), which will be fed to the model by the framework.
This allows complex calculations to specify the current volume based on the current time. 
The volume model can also raise StopVolumeModel to inform mite that the load injection should stop for a given journey.
For this example we'll use a simple volume model which merely runs ten journeys simultaneously, forever.

.. code-block:: python

    volumemodel = lambda start, end: 10


Run the scenario
^^^^^^^^^^^^^^^^

In order to run the finished scenario locally, which will include all the necessary fixtures, run the following command:

.. code-block:: sh

    MITE_CONF_test_msg="Hello from mite" mite scenario test mite.example:scenario


Distributed deployments
-----------------------

In order to scale up mite capability to inject load, you will need to run it as a distributed suite of components. 
You can learn more about how to accomplish this in the :ref:`useful topologies <useful-topologies>` section of this documentation.

