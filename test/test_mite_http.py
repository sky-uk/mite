import os

import pytest

import mite_http as mite_http_module
from mite_http import mite_http

from .mocks.mock_context import MockContext


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

    stats = mite_http_module._generate_stats()
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
    stats = mite_http_module._generate_stats()
    assert stats[1].bins == [1, 2, 3]
