"""
.. module:: mite
   :synopsis: Functions for use with Mite

"""

import time
import asyncio
import random
from pkg_resources import get_distribution, DistributionNotFound

from .exceptions import MiteError  # noqa: F401
from .context import Context
import mite.utils


try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    # package is not installed
    pass


# TODO: move to test.py?
def test_context(extensions=('http',), **config):
    runner_config = {}
    runner_config.update(config.items())
    c = Context(print, runner_config)
    return c


class ensure_separation_from_callable:
    def __init__(self, sep_callable, loop=None):
        self._sep_callable = sep_callable
        self._loop = loop

    async def __aenter__(self):
        self._start = time.time()

    def _sleep_time(self):
        return self._sep_callable() - (time.time() - self._start)

    async def __aexit__(self, *args):
        if self._loop is None:
            self._loop = asyncio.get_event_loop()
        sleep_time = self._sleep_time()
        if sleep_time > 0:
            await mite.utils.sleep(sleep_time, loop=self._loop)


def ensure_fixed_separation(separation, loop=None):
    """Context manager which will ensure calls to a callable are separated by a fixed wait time of separation value

    Args:
        separation: integer or float value for how far to space callables

    Kwargs:
        loop: Event loop to apply the wait to, defaults to asyncio.get_event_loop()

    Example usage:
    >>> with ensure_fixed_separation(5):
    >>>     do_something()
   """
    def fixed_separation():
        return separation
    return ensure_separation_from_callable(fixed_separation, loop=loop)


def ensure_average_separation(mean_separation, plus_minus=None, loop=None):
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
        plus_minus = mean_separation * .25

    def average_separation():
        return mean_separation + (random.random() * plus_minus * 2) - plus_minus

    return ensure_separation_from_callable(average_separation, loop=loop)
