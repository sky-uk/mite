<p align="center">
  <picture>
    <img src="docs_new/docs/source/_static/mite.png/" alt="Sky-UK Mite" width="210" height="210" /><br>
  </picture>
  <br>
  <a href="https://www.python.org/downloads/release/python-3100/"><img src="https://img.shields.io/badge/python-3.10-blue.svg" alt="Python 3.10"></a>
  <a href="https://www.python.org/downloads/release/python-3110/"><img src="https://img.shields.io/badge/python-3.11-blue.svg" alt="Python 3.11"></a>
  <a href="https://github.com/sky-uk/mite/blob/master/LICENSE/"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT license"></a>
  <a href="https://github.com/ambv/black/"><img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code style: black"></a>
  <a href="https://sky-uk.github.io/mite/"><img src="https://img.shields.io/badge/docs-read-blue" alt="Docs"></a>
</p>

## What is Mite?
Mite is a load testing framework with distributed components written in Python.
Requests are executed asynchronously, allowing large throughput from relatively small infrastructure.

## Installation and usage

```bash
pip install mite
```

This requires that you have libcurl installed on your system (including C header files for development, which are often distributed separately from the shared libraries).  On Ubuntu, this can be accomplished with the command:

```
sudo apt install libcurl4 libcurl4-openssl-dev
```

You can also use the dockerfile included in this repository to run
mite.  In order to get a shell in a container with mite installed, run
these commands (assuming you have docker installed on your machine):
```
docker build -t mite .
docker run --rm -it mite sh
```

## Script example

```python
import asyncio
from .datapools import RecyclableIterableDataPool


async def journey(ctx, arg1, arg2):
    async with ctx.transaction('test1'):
        ctx.send('test_message', content=ctx.config.get('test_msg', 'Not set'))
        await asyncio.sleep(0.5)


datapool = RecyclableIterableDataPool([(i, i + 2) for i in range(5000)])
volumemodel = lambda start, end: 10

def scenario():
    return [
        ['mite.example:journey', datapool, volumemodel],
    ]
```
You can find more information about the example above in the [documentation](https://sky-uk.github.io/mite/design-deployment.html).


## Documentation

You can find the documentation [here](https://sky-uk.github.io/mite/index.html).
In the documentation you can find:
- How to set up Mite
- A quick start guide
- Information regarding the design and deployment of mite
- How to visualise the results with Prometheus and Grafana
- Some advance examples using mite modules

## Maintainers

If you run into any trouble or need support getting to grips with Mite,
reach out on [Slack](https://sky.slack.com/messages/mite) if you work at Sky,
 or contact one of the maintainers if you're an external contributer:

| [<img src="https://avatars.githubusercontent.com/jb098" width=100 height=100 alt="Jordan Brennan" /><br />Jordan Brennan](https://github.com/jb098)<br /><sub>💻</sub> | [<img src="https://avatars.githubusercontent.com/aecay" width=100 height=100 alt="Aaron Ecay" /> <br />Aaron Ecay](https://github.com/aecay)<br /><sub>💻</sub> | [<img src="https://avatars.githubusercontent.com/DavAnnunz" width=100 height=100 alt="Davide Annunziata" /><br />Davide Annunziata](https://github.com/DavAnnunz)<br /><sub>💻</sub> | [<img src="https://avatars.githubusercontent.com/ryanlinnit-sky" width=100 height=100 alt="Ryan Linnit" /><br />Ryan Linnit](https://github.com/ryanlinnit-sky)<br /><sub>💻</sub> | [<img src="https://avatars.githubusercontent.com/cosmaprc" width=100 height=100 alt="Cosmin Purcherea" /><br />Cosmin Purcherea](https://github.com/cosmaprc)<br /><sub>💻</sub> |
| :---: | :---: | :---: | :---: | :---: |

**Special thanks to the following contributors:**

* [Tony Simpson](https://github.com/tonysimpson)
