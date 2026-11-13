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

    with patch("mite_http.httpperf") as httpperf_mock:
        pool = SessionPool()
        wrapper = await pool._checkout(context)
        await pool._checkout(context)
        await pool._checkin(wrapper)

    httpperf_mock.Engine.assert_called_once()
    assert httpperf_mock.Engine.call_args.kwargs["max_total_connections"] == 10
    assert httpperf_mock.Session.call_count == 2
    assert httpperf_mock.Session.call_args.kwargs["engine"] is httpperf_mock.Engine.return_value
    assert httpperf_mock.Session.call_args.kwargs["connections"] == "session"
    httpperf_mock.Session.return_value.close.assert_called_once()


@pytest.mark.asyncio
async def test_session_closed_when_journey_raises():
    context = MockContext()

    @mite_http
    async def journey(ctx):
        raise ValueError("boom")

    with patch("mite_http.httpperf") as httpperf_mock:
        SessionPool._session_pools.pop(asyncio.get_running_loop(), None)
        with pytest.raises(ValueError):
            await journey(context)
        SessionPool._session_pools.pop(asyncio.get_running_loop(), None)

    httpperf_mock.Session.return_value.close.assert_called_once()
    assert not hasattr(context, "http")


class _FakeCookie:
    pass


def test_adapt_request_kwargs_converts_header_pairs():
    from mite_http import _adapt_request_kwargs

    assert _adapt_request_kwargs({"headers": [("X-A", "1")]})["headers"] == {"X-A": "1"}
    headers = {"X-B": "2"}
    assert _adapt_request_kwargs({"headers": headers})["headers"] is headers
    assert "headers" not in _adapt_request_kwargs({})


def test_adapt_request_kwargs_swaps_cert():
    from mite_http import _adapt_request_kwargs

    assert _adapt_request_kwargs({"cert": ("key.pem", "cert.pem")})["cert"] == ("cert.pem", "key.pem")
    assert "cert" not in _adapt_request_kwargs({})


def test_adapt_request_kwargs_moves_cookie_objects_to_cookie_list():
    from mite_http import _adapt_request_kwargs

    cookie = _FakeCookie()
    with patch("mite_http.httpperf.Cookie", _FakeCookie):
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

    response = await wrapper.post("http://x", cert=("k", "c"), json={})
    assert response._response == "resp"
    session.post.assert_awaited_once_with("http://x", cert=("c", "k"), json={})


def _http_metrics_msg(**fields):
    msg = {"type": "http_metrics", "transaction": "t", "total_time": 0.5, "first_byte_time": 0.4}
    msg.update(fields)
    return msg


def _histogram(name):
    return next(s for s in mite_http_stats._generate_extended_stats() if s.name == name)


def test_default_stats_unchanged():
    assert [s.name for s in mite_http_stats.STATS] == [
        "mite_http_response_total",
        "mite_http_response_time_seconds",
    ]


def test_extended_stats_names():
    assert [s.name for s in mite_http_stats.EXTENDED_HTTP_STATS] == [
        "mite_http_dns_time_seconds",
        "mite_http_connect_time_seconds",
        "mite_http_tls_time_seconds",
        "mite_http_pretransfer_time_seconds",
        "mite_http_posttransfer_time_seconds",
        "mite_http_first_byte_time_seconds",
        "mite_http_queue_time_seconds",
        "mite_http_client_lag_seconds",
        "mite_http_download_size_bytes",
        "mite_http_upload_size_bytes",
    ]


def test_curl_timing_histograms():
    for name, field in (
        ("mite_http_dns_time_seconds", "dns_time"),
        ("mite_http_pretransfer_time_seconds", "transfer_start_time"),
        ("mite_http_posttransfer_time_seconds", "posttransfer_time"),
        ("mite_http_first_byte_time_seconds", "first_byte_time"),
    ):
        histogram = _histogram(name)
        histogram.process(_http_metrics_msg(**{field: 0.25}))
        assert dict(histogram.sums) == {("t",): 0.25}


def test_connect_and_tls_histograms_skip_reused_connections():
    for name, field in (
        ("mite_http_connect_time_seconds", "connect_time"),
        ("mite_http_tls_time_seconds", "tls_time"),
    ):
        histogram = _histogram(name)
        histogram.process(_http_metrics_msg(**{field: 0.05}))
        histogram.process(_http_metrics_msg(**{field: 0}))  # reused connection
        histogram.process(_http_metrics_msg())
        assert dict(histogram.total_counts) == {("t",): 1}
        assert dict(histogram.sums) == {("t",): 0.05}


def test_client_lag_and_queue_time_histograms():
    for name, field in (
        ("mite_http_client_lag_seconds", "client_lag"),
        ("mite_http_queue_time_seconds", "queue_time"),
    ):
        histogram = _histogram(name)
        histogram.process(_http_metrics_msg(**{field: 0.25}))
        histogram.process(_http_metrics_msg())  # older sender without the field
        assert dict(histogram.total_counts) == {("t",): 1}
        assert dict(histogram.sums) == {("t",): 0.25}


def test_size_histograms():
    download = _histogram("mite_http_download_size_bytes")
    download.process(_http_metrics_msg(download_size=2000))
    download.process(_http_metrics_msg(download_size=0))  # e.g. HEAD or 204
    assert dict(download.total_counts) == {("t",): 2}
    assert dict(download.sums) == {("t",): 2000}
    assert download.bins[0] == 128

    upload = _histogram("mite_http_upload_size_bytes")
    upload.process(_http_metrics_msg(upload_size=500))
    upload.process(_http_metrics_msg(upload_size=0))  # no request body
    assert dict(upload.total_counts) == {("t",): 1}


def test_non_default_size_bins():
    with patch.dict(os.environ, {"MITE_HTTP_SIZE_HISTOGRAM_BUCKETS": "10,100"}):
        stats = mite_http_stats._generate_extended_stats()
    assert next(s for s in stats if s.name == "mite_http_upload_size_bytes").bins == [10, 100]


@pytest.mark.asyncio
async def test_response_callback_sends_new_fields():
    from unittest.mock import MagicMock

    context = MockContext()
    with patch("mite_http.httpperf") as httpperf_mock:
        await SessionPool()._checkout(context)
    callback = httpperf_mock.Session.return_value.set_response_callback.call_args.args[0]

    response = MagicMock()
    response.request.method = "GET"
    response.queue_time = 0.01
    response.client_lag = 0.02
    response.posttransfer_time = 0.03
    response.http_version = "HTTP/2"
    response.upload_size = 12
    callback(response)

    (name, fields), = context.messages
    assert name == "http_metrics"
    assert fields["method"] == "GET"
    assert fields["queue_time"] == 0.01
    assert fields["client_lag"] == 0.02
    assert fields["posttransfer_time"] == 0.03
    assert fields["http_version"] == "HTTP/2"
    assert fields["upload_size"] == 12


def test_create_http_cookie_uses_old_fork_defaults():
    from mite_http import create_http_cookie

    with patch("mite_http.httpperf.Cookie") as cookie_cls:
        create_http_cookie(None, ".example.com", "session", "abc")
    cookie_cls.assert_called_once_with(
        http_only=False,
        domain=".example.com",
        include_subdomains=True,
        path="/",
        is_secure=False,
        expiration=0,
        name="session",
        value="abc",
    )


@pytest.mark.asyncio
async def test_to_curl(httpserver):
    import shlex

    from mite_http import to_curl

    httpserver.expect_request("/login").respond_with_data(
        "ok", headers={"Set-Cookie": "session=abc; Path=/"}
    )
    httpserver.expect_request("/api").respond_with_data("ok")
    context = MockContext()
    commands = []

    @mite_http
    async def journey(ctx):
        await ctx.http.get(httpserver.url_for("/login"))
        resp = await ctx.http.post(
            httpserver.url_for("/api"),
            json={"a": "it's"},
            headers={"X-Test": "1"},
            cookies={"extra": "x"},
            auth=("user", "pw"),
        )
        commands.append(to_curl(resp))
        commands.append(resp.request.to_curl())

    await journey(context)
    assert commands[0] == commands[1]

    args = shlex.split(commands[0])
    assert args[:3] == ["curl", "-X", "POST"]
    assert args[args.index("--data-raw") + 1] == '{"a": "it\'s"}'
    headers = [args[i + 1] for i, a in enumerate(args) if a == "-H"]
    assert "X-Test: 1" in headers
    assert "Content-Type: application/json" in headers
    assert args[args.index("--cookie") + 1] == "session=abc; extra=x"
    assert args[args.index("--user") + 1] == "user:pw"
    assert args[-1] == httpserver.url_for("/api")


def test_to_curl_without_body_headers_or_cookies():
    from unittest.mock import MagicMock

    from mite_http import to_curl

    response = MagicMock()
    response.request.method = "GET"
    response.request.url = "https://example.com/x?a=1&b=2"
    response.request.data = None
    response.request.header_list = None
    response.request.cookie_list = None
    response.request.auth = None
    response.cookielist = []
    assert to_curl(response) == "curl -X GET 'https://example.com/x?a=1&b=2'"


def test_to_curl_only_includes_matching_cookies():
    from unittest.mock import MagicMock

    import httpperf

    from mite_http import to_curl

    def cookie(domain, name, path="/", subdomains=True, secure=False, expiration=0):
        return httpperf.Cookie(False, domain, subdomains, path, secure, expiration, name, "v")

    response = MagicMock()
    response.request.method = "GET"
    response.request.url = "http://api.example.com/v1/users"
    response.request.data = None
    response.request.header_list = None
    response.request.cookie_list = None
    response.request.auth = None
    response.cookielist = [
        cookie(".example.com", "parent"),
        cookie("api.example.com", "exact", subdomains=False),
        cookie("other.com", "other_domain"),
        cookie("example.com", "host_only_parent", subdomains=False),
        cookie(".example.com", "wrong_path", path="/v2"),
        cookie(".example.com", "right_path", path="/v1"),
        cookie(".example.com", "secure_only", secure=True),
        cookie(".example.com", "expired", expiration=1),
    ]
    assert to_curl(response).split("--cookie ")[1].startswith("'parent=v; exact=v; right_path=v'")


@pytest.mark.asyncio
async def test_response_callback_gets_request_to_curl(httpserver):
    httpserver.expect_request("/x").respond_with_data("ok")
    context = MockContext()
    seen = []

    @mite_http
    async def journey(ctx):
        def callback(resp, additional_metrics):
            additional_metrics["curl-request"] = resp.request.to_curl()
            seen.append(resp.request.url)

        ctx.http.set_response_callback(callback)
        resp = await ctx.http.get(httpserver.url_for("/x"))
        assert resp.status_code == 200
        assert resp.text == "ok"

    await journey(context)
    assert seen == [httpserver.url_for("/x")]
    (_, fields), = context.messages
    assert fields["curl-request"] == f"curl -X GET {httpserver.url_for('/x')}"


@pytest.mark.asyncio
async def test_redirect_history_is_wrapped(httpserver):
    httpserver.expect_request("/from").respond_with_data("", status=302, headers={"Location": "/to"})
    httpserver.expect_request("/to").respond_with_data("ok")
    context = MockContext()

    @mite_http
    async def journey(ctx):
        resp = await ctx.http.get(httpserver.url_for("/from"))
        assert resp.status_code == 200
        (first,) = resp.history
        assert first.status_code == 302
        assert first.request.to_curl().endswith(httpserver.url_for("/from"))

    await journey(context)


def test_json_dumps_matches_old_fork_output():
    import json

    from mite_http import _json_dumps

    obj = {"url": "http://a/b", "u": "é", "n": [1, 2.5, None, True], "nested": {"k": "v"}}
    assert _json_dumps(obj) == json.dumps(obj)


@pytest.mark.asyncio
async def test_json_request_body_and_response_use_ujson(httpserver):
    httpserver.expect_request(
        "/json", method="POST", data='{"url": "http://a/b", "n": [1, 2]}'
    ).respond_with_json({"ok": True, "path": "/x"})
    context = MockContext()
    results = []

    @mite_http
    async def journey(ctx):
        resp = await ctx.http.post(httpserver.url_for("/json"), json={"url": "http://a/b", "n": [1, 2]})
        results.append(resp.json())

    with patch("mite_http.ujson.loads", wraps=__import__("ujson").loads) as loads:
        SessionPool._session_pools.pop(asyncio.get_running_loop(), None)
        await journey(context)
        SessionPool._session_pools.pop(asyncio.get_running_loop(), None)

    assert results == [{"ok": True, "path": "/x"}]
    loads.assert_called_once()


@pytest.mark.asyncio
async def test_head_follows_redirects_by_default(httpserver):
    httpserver.expect_request("/from").respond_with_data("", status=302, headers={"Location": "/to"})
    httpserver.expect_request("/to").respond_with_data("ok")
    context = MockContext()
    statuses = []

    @mite_http
    async def journey(ctx):
        statuses.append((await ctx.http.head(httpserver.url_for("/from"))).status_code)
        statuses.append(
            (await ctx.http.head(httpserver.url_for("/from"), allow_redirects=False)).status_code
        )

    await journey(context)
    assert statuses == [200, 302]


def test_journeys_on_event_loops_in_several_threads(httpserver):
    import threading

    httpserver.expect_request("/x").respond_with_data("ok")
    errors = []
    statuses = []

    @mite_http
    async def journey(ctx):
        statuses.append((await ctx.http.get(httpserver.url_for("/x"))).status_code)

    async def run_journeys():
        await asyncio.gather(*(journey(MockContext()) for _ in range(20)))
        # Each loop gets its own SessionPool and engine
        pool = SessionPool._session_pools.pop(asyncio.get_running_loop())
        return pool._engine

    engines = []

    def thread():
        try:
            engines.append(asyncio.run(run_journeys()))
        except Exception as e:  # pragma: no cover - reported below
            errors.append(e)

    threads = [threading.Thread(target=thread) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors
    assert statuses == [200] * 80
    assert len({id(e) for e in engines}) == 4
