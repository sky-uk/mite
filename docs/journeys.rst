===================================
Writing mite journeys and scenarios
===================================


Journeys
--------

The basics of writing mite journey functions are explained in the
`README`_.

.. _README: https://github.com/sky-uk/mite#journeys


.. _data-creation-scenarios:

Data creation scenarios
-----------------------

For many workloads, it is necessary to populate a test environment with
some data.  For example, if we are performance testing a web appʼs
signin, we need to seed the database with some usernames and passwords
that we can use in our signin HTTP requests.  In mite, this is
accomplished by **data creation scenarios**.

Firstly, when running a data creation scenario, we need to activate
miteʼs :ref:`recorder component <recorder-component>`.  This will
write the data as it is created to a series of `msgpack`_-format files
in a directory called ``recorder-data``.  These files will become the
input for a datapool for the load test journeys (see below).

.. _msgpack: https://msgpack.org/index.html

Secondly, we need to write some journey functions that use the appʼs
HTTP APIs to create data.  An example might be as follows:

.. code-block:: python

   import uuid
   from mite_http import mite_http

   @mite_http
   async def create_user(context):
       username = uuid.uuid4().hex
       async with ctx.transaction("Create user"):
           await ctx.http.post(ctx.config.get("app_url") + "/users/create",
                               json={"username": username, "password": "test1234"})
           await ctx.send("data_created", name="users", data={"username": username})


We use the python standard library :py:mod:`uuid module <uuid>` to
generate random user names, and create the users with a fixed password.
We then send a message with the type ``data_created`` and the name
``users``.  This will be read by the recorder process, which listens
to messages with type ``data_created``.  It will read the ``name`` of
all such messages.  For each message, the ``data`` is written as a
msgpack dictionary into the file ``recorder-data/{name}.msgpack``.

We create a scenario that runs this journey for a specific amount of
time at a specific rate, which will generate our test users.  If we have
other types of data that need to be populated in the environment, we can
write multiple journeys and run them as part of the same scenario.  By
giving a different ``name`` to each kind of data we create, we will get
different output files for each type of data.

.. note::

   The suggested approach to run the data creation journey for a
   specific time and TPS will generate an approximate number of test
   users.  If precise control of the number of users generated is
   needed, you should instead use a (nonrecyclable) datapool as input
   to the creation scenario.  The scenario will then be run once for
   each item in the data pool, creating a precisely specified number
   of users.

The next step is to create a data pool for the usernames:

.. code-block:: python

   from mite.datapools import RecyclableIterableDataPool

   usernames = []
   with open("recorder-data", "rb") as handle:
       for msg in iter(Unpacker(handle, raw=False, use_list=False)):
           usernames.append((msg["username"],))

   username_datapool = RecyclableIterableDataPool(usernames)

.. note::

   The datapool items (which are appended to the ``usernames`` variable)
   are tuples; this is required by miteʼs data pool framework.

Finally, we can use this datapool in our scenario:

.. code-block:: python

   @mite_http
   async def signin(ctx, username):
       async with ctx.transaction("Log in"):
           await ctx.http.post(ctx.config.get("app_url") + "/login",
                               json={"username": username, "password": "test1234"})

   def my_scenario():
       return [["my_file:signin", usernames_datapool, lambda start, end: 100]]
