import asyncio

import pytest

import acurl


@pytest.fixture
async def acurl_session():
    w = acurl.CurlWrapper(asyncio.get_running_loop())
    yield w.session()
