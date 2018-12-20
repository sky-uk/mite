# Mite
## Load Testing Framework

Mite is a load testing framework with distributed components written in Python.
Requests are executed asynchronously, allowing large throughput from relatively small infrastructure.

To install mite, run `python setup.py install` in the directory with the setup.py. Will require acurl to be installed already. All other python dependencies will be installed. A .gitlab-ci.yml is included which will build a ready to use docker image with mite installed.

Run 'mite --help' for a full list of commands

## Your first scenario

Scenarios are a combination of 3 things, a set of Journeys to run, a datapool to provide test data for the journey (if applicable), and a volume model.

### Journeys

Journeys are async python functions, and are where you put the logic of what you'rew trying to achieve. Below is a simple example:

```python
import asyncio

async def journey(ctx, arg1, arg2):
    async with ctx.transaction('test1'):
        ctx.send('test_message', content=ctx.config.get('test_msg', 'Not set'))
        await asyncio.sleep(0.5)
```

This journey just sends a log message to be collected by the framework and waits for half a second. This journey takes 3 arguments, a context and two more. The other two arguments are not used in this journey but the context is.

#### Context

The context is important for every journey. It provides a number of useful methods for timing/naming of transactions, sending messages and defaults to including http functionality from acurl. Functionality can be included in the journey by attaching it to the context.

In the above example we see an example of naming a transaction `async with ctx.transaction('test1'):`. This will capture timing for the indented block.

We also see that the config is attached to the context with `ctx.config.get('test_msg', 'Not set')` and in this case, the value of that config value is sent to the log collector with `ctx.send('test_message', content=ctx.config.get('test_msg', 'Not set'))`

### Datapools

To feed data into your test journey, you'll need a datapool. Several of these are already provided in mite and usually read data in from an iterable. To specify a custom datapool implementation, you simply need a class that implements a `checkin` method which adds data to the pool and a `checkout` method which removes data from the pool to be used by journeys. 

For the above journey, which expects two arguments, we will show an example of the RecyclableIterableDataPool.

```python
from mite.datapools import RecyclableIterableDataPool

datapool = RecyclableIterableDataPool([(i, i+2) for i in range(5000)])
```

This pool will share data out to runners and check it back in when the runners are done with that block of data. In this case it cycles through a list of tuples which just contain two integers.

### Volume Model

A volume model defines how many instances of the journey should be ran within a window. The window is definied as a start and an end time, which will be fed to the model by the framework. This allows complex calculations to specify the current volume based on the current time. For this example we'll use a simple volume model

```python
volumemodel = lambda start, end: 10
```

This anonymous function does nothing with the start and end window, and will just return 10. This will just run 10 tasks forever.

### Scenario

We now need to package the journey, datapool and volume model into a scenario. This is a simple as defining a function which returns something in the correct format.

```python
def scenario():
    return [
        ['mite.example:journey', datapool, volumemodel],
    ]
```
A scenario is simply a list of lists, with each inner list having a journey, a datapool and a volume model. Multiple of these can be included in a scenario. The journey will look for 'mite.example' somewhere that exists on the PYTHONPATH. It will look in that file for the `journey` function that we previously specified. In this example, the datappol and volumemodel exist in the same scope as the scenario we are defining.

### Testing the journey

Before running the scenario, we should test the journey in isolation as a scenario can be made up of multiple journeys. This can be done with the `mite journey test` command. We just need to pass the name of the journey and the datapool it requires.

If config is required, this can be specified in multiple ways but the most common way is for the framework to read this off an envrionment variable. Any environment variable that starts with `MITE_CONF_` will be picked up by the framwework. The above journey tries to get the config value `test_msg` so we could set this by setting `MITE_CONF_test_msg`

After this is done, run the journey as below.

```sh
mite journey test mite.example:journey mite.example:datapool
```

If something goes wrong, adding the `--debugging` flag will drop into a debugger on error.

### Run the scenario

In order to run the finished scenario locally, which will include all the necessary fixtures, do the following

```sh
mite scenario test mite.example:scenario
```

## Distributed scenarios

In order to achieve high throughput, it's necessary to split mite into its respective components and distribute them across cores/machines. Mite is made up of a number of components, each with their own test control, execution and data pipeline responsibilities.

### Duplicator

The mite duplicator is responsible for ingesting logs from multiple sources and then duplicating those logs out to other components. It is usually the first component to start. The controller and runners feed their logs into the duplicator and cannot run without it. Only one duplicator is ran at a time but it is a very lightweight component.

To start the duplicator with one inbound socket open and two outbound sockets for the stats and collector components, run the following.

```sh
mite duplicator --message-socket=tcp://0.0.0.0:14302 tcp://127.0.0.1:14303 tcp://127.0.0.1:14304
```

### Stats

The mite stats component pulls stats out of the logs passed from the collector. As many of these can be run as is necessary to achieve desired throughput. It can be passed an optional in and out socket, but in our case we'll just run it with default sockets.

```sh
mite stats
```

The default in socket is `tcp://127.0.0.1:14304` which we previously told our duplicator to output on.

### Collector

The mite collector is an optional component designed to write the raw logs to files. It defaults to writing 10000 log lines to a file before rolling and timestamping the file. The most recent file is named `current`. Again, as many of these can be ran as is necessary to achieve throughput but for every collector run, a different `--collector-dir` must be specified. Run as below.

```sh
mite collector
```

### Recorder

The mite recorder is an optional component designed to record data to disk. It can be used for storing values created during scenarios, handling messages of the type 'data\_created' to write data and 'purge\_data' to delete old recorded values. There is an optional --recorder-dir argument to specify a folder where files are created.

```sh
mite recorder
```

Logs are compressed with msgpack and so that is necessary to unpack the logs into human readable form. We could also have specified an optional inbound socket but by defaul this will read off of the duplicators other outbound socket `tcp://127.0.0.1:14303` as well as an option to change how often logs are rolled, see `mite --help`.

### Prometheus Exporter

The prometheus exporter provides a http metrics endpoint for prometheus to scrape, pulling metrics from the stats components. In our case, stats components will output on the default socket and so the exporter will default to reading off that.

```sh
mite prometheus_exporter
```

### Runners

The mite runners are the component responsible for executing the journeys specified in the scenario. As many of these can be span up as you want but you should limit this to no more than one per core. The runner needs two arguments, a socket it can use to talk to a controller and a message socket it can use to send messages to the duplicator. In the below instance we'll let it use the defaults but see `mite --help` for more details.

```sh
mite runner
```

### Controller

The last component to run is the mite contoller. It dictates the scenario to run, loads and distrbutes the config to the runners and is responsible for managing the work that the runners are doing. As all our components are set up to use default sockets, we just have to specify the scenario to run, much in the same way as the scenario test earlier in the documentation.

```sh
mite controller mite.example:scenario
```
