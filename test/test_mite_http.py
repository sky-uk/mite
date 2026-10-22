import asyncio
import importlib
import os
import subprocess
import sys
from unittest.mock import patch

import pytest
from mocks.mock_context import MockContext

import mite_http as mite_http_pkg
import mite_http.stats as mite_http_stats
from mite_http import SessionPool, mite_http

# Runs in a subprocess, not via importlib.reload() in-process: reloading
# mite_http here would mutate the live SessionPool class other tests in
# this file depend on (its _session_pools memoization dict), since
# reload() always creates a fresh class object bound into the module's
# (shared, mutated-in-place) namespace.
_BLOCK_ACURL_AND_IMPORT = """
import builtins
real_import = builtins.__import__
def fake_import(name, *args, **kwargs):
    if name == "acurl":
        raise ModuleNotFoundError(name)
    return real_import(name, *args, **kwargs)
builtins.__import__ = fake_import
import mite_http
"""


def test_raises_when_acurl_missing():
    result = subprocess.run(
        [sys.executable, "-c", _BLOCK_ACURL_AND_IMPORT],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "pip install mite[http]" in result.stderr


@pytest.mark.asyncio
async def test_get(httpserver):
    httpserver.expect_oneshot_request("/test", "GET").respond_with_data("hi")
    context = MockContext()

    @mite_http
    async def test(ctx):
        await ctx.http.get(httpserver.url_for("/test"))

    await test(context)
    assert len(httpserver.log) == 1
    assert len(context.messages) == 1


@pytest.mark.asyncio
async def test_additional_metrics(httpserver):
    httpserver.expect_oneshot_request("/test", "GET").respond_with_data("hi")
    context = MockContext()

    @mite_http
    async def test(ctx):
        ctx.http.additional_metrics = {"test_metric_name": 1}
        await ctx.http.get(httpserver.url_for("/test"))

    await test(context)
    assert len(context.messages) == 1
    assert "test_metric_name" in context.messages[0][1]
    assert not hasattr(context, "additional_http_metrics")


def test_default_histogram_bins():
    if "MITE_HTTP_HISTOGRAM_BUCKETS" in os.environ:
        del os.environ["MITE_HTTP_HISTOGRAM_BUCKETS"]

    stats = mite_http_stats._generate_stats()
    assert stats[1].bins == [
        0.0001,
        0.001,
        0.01,
        0.05,
        0.1,
        0.2,
        0.4,
        0.8,
        1,
        2,
        4,
        8,
        16,
        32,
        64,
    ]


def test_non_default_bins():
    os.environ["MITE_HTTP_HISTOGRAM_BUCKETS"] = "1,2,3"
    stats = mite_http_stats._generate_stats()
    assert stats[1].bins == [1, 2, 3]


def test_decorator_without_async_loop_running():
    with patch("asyncio.get_running_loop", side_effect=Exception("oops")):

        @mite_http
        async def foo():
            pass

        # This test just wants to ensure we can execute the decorator without
        # calling get_event_loop, so there are no assertions; the lack of the
        # exception is enough


@pytest.mark.asyncio
async def test_decorator_eventloop_memoization():
    @mite_http
    async def foo(ctx):
        pass

    class MockContext:
        config = {}

    await foo(MockContext())

    assert asyncio.get_running_loop() in SessionPool._session_pools


# Deliberately last in the file - importlib.reload() rebinds module
# attributes and creates new class objects, so anything defined after it
# could be affected.
def test_warns_on_import():
    with pytest.warns(FutureWarning, match="mite_http will require"):
        importlib.reload(mite_http_pkg)
