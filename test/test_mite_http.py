import asyncio
import os
from unittest.mock import patch

import pytest
from mocks.mock_context import MockContext

import mite_http.stats as mite_http_stats
from mite_http import SessionPool, mite_http


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
    with patch("asyncio.get_event_loop", side_effect=Exception("oops")):

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
