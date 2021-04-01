"""
.. module:: mite
   :synopsis: Functions for use with Mite

"""

import random
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from pkg_resources import DistributionNotFound, get_distribution

import mite.utils

from .context import Context
from .exceptions import MiteError as MiteError  # noqa: F401

try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    # package is not installed
    pass


# TODO: move to test.py?
def test_context(extensions=("http",), **config):
    runner_config: dict[str, Any] = {}
    runner_config.update(config.items())
    c = Context(print, runner_config)
    return c


@asynccontextmanager
async def _ensure_separation(total_time: float) -> AsyncIterator[None]:
    start = time.time()
    yield
    sleep_time = total_time - (time.time() - start)
    if sleep_time > 0:
        await mite.utils.sleep(sleep_time)


@asynccontextmanager
async def ensure_fixed_separation(separation: float) -> AsyncIterator[None]:
    """Context manager which will ensure calls to a callable are separated by a fixed wait time of separation value

    Args:
        separation: integer or float value for how far to space callables

    Kwargs:
        loop: Event loop to apply the wait to, defaults to asyncio.get_event_loop()

    Example usage:
    >>> async with ensure_fixed_separation(5):
    >>>     do_something()
    """

    async with _ensure_separation(separation):
        yield


@asynccontextmanager
async def ensure_average_separation(
    mean_separation: float, plus_minus: float = None
) -> AsyncIterator[None]:
    """Context manager which will ensure calls to a callable are separated by an average wait time of separation value

    Args:
        separation: integer or float value for how far to space callables

    Kwargs:
        loop:       Event loop to apply the wait to, defaults to asyncio.get_event_loop()
        plus_minus: integer or float threshold to vary the wait by

    Example usage:
    >>> with ensure_average_separation(5):
    >>>     do_something()
    """
    if plus_minus is None:
        plus_minus = mean_separation * 0.25
    separation = mean_separation + (random.random() * plus_minus * 2) - plus_minus
    async with _ensure_separation(separation):
        yield
