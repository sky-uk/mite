import asyncio
from unittest import mock
from unittest.mock import call

import pytest
from mite.cli.controller import _run_time_function


@pytest.mark.asyncio
class TestRunTimeFunction:
    async def test_none(self):
        s = asyncio.Event()
        e = asyncio.Event()

        async def co():
            await asyncio.sleep(0.01)
            e.set()

        await asyncio.gather(co(), _run_time_function(None, s, e))
        assert s.is_set()

    async def test_time_fn(self):
        s = asyncio.Event()
        e = asyncio.Event()

        async def co():
            await asyncio.sleep(0.01)
            e.set()

        async def tf(s, e):
            assert not s.is_set()
            s.set()
            await e.wait()

        await asyncio.gather(co(), _run_time_function(tf, s, e))
        assert s.is_set()
        assert e.is_set()

    async def test_early_return(self):
        s = asyncio.Event()
        e = asyncio.Event()

        async def co():
            await asyncio.sleep(0.01)
            e.set()

        async def tf(s, e):
            assert not s.is_set()
            s.set()

        with mock.patch("logging.error") as m:
            await asyncio.gather(co(), _run_time_function(tf, s, e))
            assert s.is_set()
            assert e.is_set()
            assert m.call_args_list == [
                call(
                    'The time function exited before the scenario ended, which seems like a bug'
                ),
            ]
