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

You can simply install mite using pip

```bash
pip install mite
```
For more information regarding requirements and how to use it just check 
the [installation](https://sky-uk.github.io/mite/installation.html) page in the documentation.


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
You can find more information about the example above in the
 [design](https://sky-uk.github.io/mite/design-deployment.html) info documentation page.


## Documentation

> [!IMPORTANT]  
> As we have some issues using the GitHub actions the Wiki github pages documentation is not updated. 
> Below you can find the link to the specific pages and the link to the rst files.

In the ~~[documentation](https://sky-uk.github.io/mite/index.html)~~ (Link currently out of date) you can find:
- [Introduction](https://github.com/sky-uk/mite/blob/new-documentation/docs/source/introduction.rst)
- [Installation](https://github.com/sky-uk/mite/blob/new-documentation/docs/source/installation.rst)
- [Quick Start](https://github.com/sky-uk/mite/blob/new-documentation/docs/source/quick-start.rst)
- [Design and Deployment](https://github.com/sky-uk/mite/blob/new-documentation/docs/source/design-deployment.rst)
- [Prometheus/Grafana and Mite](https://github.com/sky-uk/mite/blob/new-documentation/docs/source/data-visualization.rst)
- [Test Examples](https://github.com/sky-uk/mite/blob/new-documentation/docs/source/test-examples.rst)
- [Contributing Guidelines](https://github.com/sky-uk/mite/blob/new-documentation/docs/source/contributing-guidelines.rst)

## Maintainers

If you run into any trouble or need support getting to grips with Mite,
reach out on [Slack](https://sky.slack.com/messages/mite) if you work at Sky,
 or contact one of the maintainers if you're an external contributer:

| [<img src="https://avatars.githubusercontent.com/jb098" width=100 height=100 alt="Jordan Brennan" /><br />Jordan Brennan](https://github.com/jb098)<br /><sub>💻</sub> | [<img src="https://avatars.githubusercontent.com/aecay" width=100 height=100 alt="Aaron Ecay" /> <br />Aaron Ecay](https://github.com/aecay)<br /><sub>💻</sub> | [<img src="https://avatars.githubusercontent.com/DavAnnunz" width=100 height=100 alt="Davide Annunziata" /><br />Davide Annunziata](https://github.com/DavAnnunz)<br /><sub>💻</sub> | [<img src="https://avatars.githubusercontent.com/ryanlinnit-sky" width=100 height=100 alt="Ryan Linnit" /><br />Ryan Linnit](https://github.com/ryanlinnit-sky)<br /><sub>💻</sub> | [<img src="https://avatars.githubusercontent.com/cosmaprc" width=100 height=100 alt="Cosmin Purcherea" /><br />Cosmin Purcherea](https://github.com/cosmaprc)<br /><sub>💻</sub> |
| :---: | :---: | :---: | :---: | :---: |

**Special thanks to the following contributors:**

* [Tony Simpson](https://github.com/tonysimpson)
