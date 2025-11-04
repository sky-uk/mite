# Mite

[![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/release/python-3100/) [![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/) [![MIT license](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/sky-uk/mite/blob/master/LICENSE) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black) [![Docs](https://img.shields.io/badge/docs-read-blue)](https://sky-uk.github.io/mite/)

## Load Testing Framework

Mite is a load testing framework with distributed components written in Python.
Requests are executed asynchronously, allowing large throughput from relatively small infrastructure.

## Installation

```bash
pip install mite
```


This requires that you have libcurl installed on your system (including C header files for development, which are often distributed separately from the shared libraries).  On Ubuntu, this can be accomplished with the command:

```
sudo apt install libcurl4 libcurl4-openssl-dev
```
(NB we recommend using a version of libcurl linked against openssl
rather than gnutls, since the latter has memory leak problems)


You can also use the dockerfile included in this repository to run
mite.  In order to get a shell in a container with mite installed, run
these commands (assuming you have docker installed on your machine):
```
docker build -t mite .
docker run --rm -it mite sh
```

Run `mite --help` for a full list of commands

## Your first scenario

Scenarios are a combination of 3 things, a set of journeys to run, a
datapool to provide test data for the journey (if applicable), and a
volume model.

### Journeys

Journeys are async python functions, and are where you put the logic of
what you're trying to achieve.  Below is a simple example:

```python
import asyncio

async def journey(ctx, arg1, arg2):
    async with ctx.transaction('test1'):
        ctx.send('test_message', content=ctx.config.get('test_msg', 'Not set'), sum=arg1 + arg2)
        await asyncio.sleep(0.5)
```

This journey just sends a log message to be collected by the framework
and waits for half a second.  This journey takes 3 arguments, a context
and two numbers (which will be supplied by the datapool, see below).

#### Context

The context is important for every journey.  It provides a number of
useful methods for timing/naming of transactions, sending messages and
defaults to including http functionality from acurl.  Functionality can
be included in the journey by attaching it to the context.

In the above example we see an example of naming a transaction `async
with ctx.transaction('test1'):`.  This will capture timing for the
indented block.

We also see that the config is attached to the context with
`ctx.config.get('test_msg', 'Not set')` and in this case, the value of
that config value is sent to the log collector with
`ctx.send('test_message', content=ctx.config.get('test_msg', 'Not set'))`

### Datapools

To feed data into your test journey, you'll need a datapool. Several of
these are already provided in mite and usually read data in from an
iterable. To specify a custom datapool implementation, you simply need a
class that implements a `checkin` method which adds data to the pool and
a `checkout` method which removes data from the pool to be used by
journeys.

For the above journey, which expects two arguments, we will show an
example of the RecyclableIterableDataPool.

```python
from mite.datapools import RecyclableIterableDataPool

datapool = RecyclableIterableDataPool([(i, i+2) for i in range(5000)])
```

This pool will share data out to runners and check it back in when the
runners are done with that block of data.  In this case it cycles
through a list of tuples which each contain two integers.

### Volume Model

A volume model defines how many instances of the journey should be ran
within a window of time.  The window is definied as a start and an end
time (measured in seconds since the beginning of the test), which will be
fed to the model by the framework.  This allows complex calculations to
specify the current volume based on the current time.  The volume model
can also raise `StopVolumeModel` to inform mite that the load injection
should stop for a given journey.  For this example we'll use a simple
volume model which merely runs ten journeys simultaneously, forever.

```python
volumemodel = lambda start, end: 10
```

### Scenario

We now need to package the journey, datapool and volume model into a
scenario.  This is a simple as defining a function which returns
a list of triplets of (journey name, datapool, volumemodel).

```python
def scenario():
    return [
        ['mite.example:journey', datapool, volumemodel],
    ]
```

The journey name should be a string with two parts separated by a
colon.  The first part is the name of a python module that is
importable; the second is the name of a journey (an async function)
within that module.  It is necessary to specify this as a string, rather
than as a python object, because the journey will be executed in a
different python process than the scenario function is.  Thus, we need a
name for the journey that allows any python process to find it.

The volume model and data pool, on the other hand, are only used in the
python process where the scenario function runs.  They are both python
objects.

### Testing the journey

Before running the scenario, we should test the journey in isolation as
a scenario can be made up of multiple journeys.  This can be done with
the `mite journey test` command.  We just need to pass the name of the
journey and the datapool it requires:

```sh
MITE_CONF_test_msg="Hello from mite" mite journey test mite.example:journey mite.example:datapool
```

If something goes wrong, adding the `--debugging` flag to this command
will drop excution into a debug session. The choice of debugger used can be
managed by setting the [`PYTHONBREAKPOINT` environment variable](https://www.python.org/dev/peps/pep-0553/#environment-variable)
before running mite. Python's built-in [pdb](https://docs.python.org/3/library/pdb.html))
debugger is invoked by default, but this can be changed to use, say, the
[ipdb debugger](https://github.com/gotcha/ipdb):

```
pip install ipdb
export PYTHONBREAKPOINT=ipdb.set_trace
export PYTHONPOSTMORTEM=ipdb.post_mortem
```

`PYTHONPOSTMORTEM` is a mite-specific extension to [PEP
553](https://www.python.org/dev/peps/pep-0553/) which defines the
`PYTHONBREAKPOINT` functionality.

### Run the scenario

In order to run the finished scenario locally, which will include all
the necessary fixtures, run the following command:

```sh
MITE_CONF_test_msg="Hello from mite" mite scenario test mite.example:scenario
```

## Distributed deployments

In order to scale up miteʼs capability to inject load, you will need to
run it as a distributed suite of components.  You can learn more about
how to accomplish this in the [documentation](https://sky-uk.github.io/mite/design-deployment.html).


### Deploy distributed mite with docker compose

Build mite image: 
```
docker build -t mite .
````

Run mite deployments:

Use `make` from `mite/local` dir:
```
make up # start mite containers
make status # check status of mite containers
make clean # remove all mite containers
```
or
```
docker-compose -f docker_compose.yml up
```

For more information on distributed mite usage, [info](/local/README.md)

## Maintainers

If you run into any trouble or need support getting to grips with Mite,
reach out on [Slack](https://sky.slack.com/messages/mite) if you work at Sky,
 or contact one of the maintainers if you're an external contributer:

| [<img src="https://avatars.githubusercontent.com/jb098" width=100 height=100 alt="Jordan Brennan" /><br />Jordan Brennan](https://github.com/jb098)<br /><sub>💻</sub> | [<img src="https://avatars.githubusercontent.com/aecay" width=100 height=100 alt="Aaron Ecay" /> <br />Aaron Ecay](https://github.com/aecay)<br /><sub>💻</sub> | [<img src="https://avatars.githubusercontent.com/DavAnnunz" width=100 height=100 alt="Davide Annunziata" /><br />Davide Annunziata](https://github.com/DavAnnunz)<br /><sub>💻</sub> | [<img src="https://avatars.githubusercontent.com/ryanlinnit-sky" width=100 height=100 alt="Ryan Linnit" /><br />Ryan Linnit](https://github.com/ryanlinnit-sky)<br /><sub>💻</sub> | [<img src="https://avatars.githubusercontent.com/cosmaprc" width=100 height=100 alt="Cosmin Purcherea" /><br />Cosmin Purcherea](https://github.com/cosmaprc)<br /><sub>💻</sub> |
| :---: | :---: | :---: | :---: | :---: |

**Special thanks to the following contributors:**

* [Tony Simpson](https://github.com/tonysimpson)
