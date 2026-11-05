# Mite


<div align="center">

<!-- <img src="https://raw.githubusercontent.com/sky-uk/mite/refs/heads/master/docs/_static/logo.png" alt="Mite logo" width="100" role="img"> -->

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/) [![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/) [![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/) [![Docs](https://img.shields.io/badge/docs-read-blue)](https://sky-uk.github.io/mite/)

[![Hatch project](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pypa/hatch/master/docs/assets/badge/v0.json)](https://github.com/pypa/hatch) [![linting - Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) [![MIT license](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/sky-uk/mite/blob/master/LICENSE) 

</div>

-----


## Load Testing Framework

Mite is a load testing framework with distributed components written in Python.
Requests are executed asynchronously, allowing large throughput from relatively small infrastructure.

## Installation

```bash
pip install mite
```

This installs the core framework only. If you're migrating from a pre-3.0
version of mite, or just want every integration available, install with the
`all` extra instead:

```bash
pip install 'mite[all]'
```

See [Optional install extras](#optional-install-extras) below for installing
only the integrations you need.

Some extras require system libraries. `http`, `browser`, `otel`, and `all`
need libcurl installed (including C header files for development, which are
often distributed separately from the shared libraries). On Ubuntu, this can
be accomplished with the command:

```
sudo apt install libcurl4 libcurl4-openssl-dev
```
(NB we use a version of libcurl linked against openssl rather than
gnutls. This was originally because gnutls had high memory usage; that
issue has since been resolved, so use whichever you prefer)

`nanomsg` needs the `libnanomsg` C library and has no prebuilt PyPI wheel, so
it compiles from source on install — only needed if you select
`--message-backend=nanomsg` (the default is ZMQ, which has no such
requirement).


You can also use the dockerfile included in this repository to run
mite.  In order to get a shell in a container with mite installed, run
these commands (assuming you have docker installed on your machine):
```
docker build -t mite .
docker run --rm -it mite sh
```

Run `mite --help` for a full list of commands

### Optional install extras

As of mite 3.0, `pip install mite` installs only the core framework.
Integrations are opt-in — install the extras for the ones you use:

| Extra | Covers |
|---|---|
| `kafka` | Kafka integration (`aiokafka`) |
| `amqp` | AMQP/RabbitMQ integration (`aio_pika`) |
| `finagle` | Finagle/Thrift integration (`thrift`) |
| `selenium` | Selenium WebDriver integration |
| `selenium_wire` | Selenium with request/response capture (`selenium-wire`) |
| `s3` | S3-backed datapools (`boto3`) |
| `db` | SQL-backed datapools (`sqlalchemy`) |
| `websocket` | WebSocket integration |
| `http` | HTTP integration (`acurl`) |
| `browser` | Browser/HTML-scraping integration (depends on `http`) |
| `nanomsg` | `nanomsg` message backend (ZMQ, the default, needs no extra) |
| `all` | Union of the above — reproduces the pre-3.0 default install |

```bash
pip install 'mite[kafka]'
pip install 'mite[all]'
```

(quote the brackets so your shell doesn't treat them as a glob)

**Upgrading from before mite 3.0?** Change `mite` to `mite[all]` in your
requirements file and nothing else changes.

This list doesn't include `playwright`, `otel`, `influxdb`, or `dev`.
`playwright` needs a separate `playwright install` step to download browser
binaries regardless of how it's installed, so no extra is offered for it —
install `playwright` directly. `otel` is a separate, pre-existing extra that
also now pulls in `mite[http]`, since mite's OpenTelemetry integration
instruments `mite_http`. `influxdb` and `dev` are likewise separate and
unrelated to this list.


## Your first scenario

A scenario combines three things: a set of journeys to run, a datapool
supplying test data to those journeys (if applicable), and a volume model
describing how much load to apply.

A journey is an async python function holding the logic of what you want to
do:

```python
import asyncio

async def journey(ctx, arg1, arg2):
    async with ctx.transaction('test1'):
        ctx.send('test_message', content=ctx.config.get('test_msg', 'Not set'), sum=arg1 + arg2)
        await asyncio.sleep(0.5)
```

A datapool supplies the journey's arguments, and a volume model says how many
copies of it to run in a given window of time:

```python
from mite.datapools import RecyclableIterableDataPool

datapool = RecyclableIterableDataPool([(i, i+2) for i in range(5000)])
volumemodel = lambda start, end: 10
```

A scenario packages them together:

```python
def scenario():
    return [
        ['mite.example:journey', datapool, volumemodel],
    ]
```

Test the journey on its own first, then run the whole scenario:

```sh
MITE_CONF_test_msg="Hello from mite" mite journey test mite.example:journey mite.example:datapool
MITE_CONF_test_msg="Hello from mite" mite scenario test mite.example:scenario
```

The full walkthrough — the journey context, custom datapools, debugging with
`--debugging`, and the volume model DSL — is in
[Your first scenario](https://sky-uk.github.io/mite/tutorial.html) in the
documentation.

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

| [<img src="https://avatars.githubusercontent.com/jb098" width=100 height=100 alt="Jordan Brennan" /><br />Jordan Brennan](https://github.com/jb098)<br /><sub>💻</sub> | [<img src="https://avatars.githubusercontent.com/aecay" width=100 height=100 alt="Aaron Ecay" /> <br />Aaron Ecay](https://github.com/aecay)<br /><sub>💻</sub> | [<img src="https://avatars.githubusercontent.com/DavAnnunz" width=100 height=100 alt="Davide Annunziata" /><br />Davide Annunziata](https://github.com/DavAnnunz)<br /><sub>💻</sub> | [<img src="https://avatars.githubusercontent.com/ryanlinnit-sky" width=100 height=100 alt="Ryan Linnit" /><br />Ryan Linnit](https://github.com/ryanlinnit-sky)<br /><sub>💻</sub> |
| :---: | :---: | :---: | :---: |

**Special thanks to the following contributors:**

* [Tony Simpson](https://github.com/tonysimpson)
