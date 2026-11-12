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


def test_options_from_config_defaults():
    from mite_http import _ENGINE_OPTIONS, _SESSION_OPTIONS, _options_from_config

    assert _options_from_config({}, _ENGINE_OPTIONS) == {
        "max_host_connections": 0,
        "max_total_connections": 0,
        "max_idle_connections": 1000,
    }
    assert _options_from_config({}, _SESSION_OPTIONS) == {
        "connections": "shared",
        "tls": "session",
        "http_version": "HTTP/2",
        "idle_timeout": 118,
        "max_connection_age": 0,
        "max_host_connections": 0,
        "max_connections": 0,
        "timeout": None,
        "connect_timeout": None,
        "verify": False,
    }


def test_options_from_config_converts_strings():
    from mite_http import _ENGINE_OPTIONS, _SESSION_OPTIONS, _options_from_config

    config = {
        "http_max_total_connections": "100",
        "http_connections": "session",
        "http_version": "HTTP/1.1",
        "http_session_max_host_connections": "6",
        "http_timeout": "2.5",
        "http_connect_timeout": "",
        "http_verify": "true",
    }
    engine = _options_from_config(config, _ENGINE_OPTIONS)
    session = _options_from_config(config, _SESSION_OPTIONS)
    assert engine["max_total_connections"] == 100
    assert session["connections"] == "session"
    assert session["http_version"] == "HTTP/1.1"
    assert session["max_host_connections"] == 6
    assert session["timeout"] == 2.5
    assert session["connect_timeout"] is None
    assert session["verify"] is True
    assert _options_from_config({"http_verify": "/etc/ca.pem"}, _SESSION_OPTIONS)["verify"] == "/etc/ca.pem"


@pytest.mark.asyncio
async def test_engine_per_pool_and_session_closed_on_checkin():
    context = MockContext()
    context.config = {"http_max_total_connections": "10", "http_connections": "session"}

    with patch("mite_http.acurl") as acurl_mock:
        pool = SessionPool()
        wrapper = await pool._checkout(context)
        await pool._checkout(context)
        await pool._checkin(wrapper)

    acurl_mock.Engine.assert_called_once()
    assert acurl_mock.Engine.call_args.kwargs["max_total_connections"] == 10
    assert acurl_mock.Session.call_count == 2
    assert acurl_mock.Session.call_args.kwargs["engine"] is acurl_mock.Engine.return_value
    assert acurl_mock.Session.call_args.kwargs["connections"] == "session"
    acurl_mock.Session.return_value.close.assert_called_once()


@pytest.mark.asyncio
async def test_session_closed_when_journey_raises():
    context = MockContext()

    @mite_http
    async def journey(ctx):
        raise ValueError("boom")

    with patch("mite_http.acurl") as acurl_mock:
        SessionPool._session_pools.pop(asyncio.get_running_loop(), None)
        with pytest.raises(ValueError):
            await journey(context)
        SessionPool._session_pools.pop(asyncio.get_running_loop(), None)

    acurl_mock.Session.return_value.close.assert_called_once()
    assert not hasattr(context, "http")


class _FakeCookie:
    pass


def test_adapt_request_kwargs_swaps_cert():
    from mite_http import _adapt_request_kwargs

    assert _adapt_request_kwargs({"cert": ("key.pem", "cert.pem")})["cert"] == ("cert.pem", "key.pem")
    assert "cert" not in _adapt_request_kwargs({})


def test_adapt_request_kwargs_moves_cookie_objects_to_cookie_list():
    from mite_http import _adapt_request_kwargs

    cookie = _FakeCookie()
    with patch("mite_http.acurl.Cookie", _FakeCookie):
        kwargs = _adapt_request_kwargs({"cookies": {"a": "1", "b": cookie}})
        assert kwargs["cookies"] == {"a": "1"}
        assert kwargs["cookie_list"] == [cookie]

        kwargs = _adapt_request_kwargs({"cookies": {"b": cookie}, "cookie_list": ["x"]})
        assert kwargs["cookies"] is None
        assert kwargs["cookie_list"] == ["x", cookie]

        kwargs = _adapt_request_kwargs({"cookies": {"a": "1"}})
        assert kwargs == {"cookies": {"a": "1"}}


@pytest.mark.asyncio
async def test_wrapper_adapts_kwargs_before_calling_session():
    from unittest.mock import AsyncMock, MagicMock

    from mite_http import AcurlSessionWrapper

    session = MagicMock()
    session.post = AsyncMock(return_value="resp")
    wrapper = AcurlSessionWrapper(session)

    assert await wrapper.post("http://x", cert=("k", "c"), json={}) == "resp"
    session.post.assert_awaited_once_with("http://x", cert=("c", "k"), json={})
