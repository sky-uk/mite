import ast
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from mite.context import Context
from mite.exceptions import MiteError
from mite.har_to_mite import (
    HarConversionError,
    Secrets,
    _extract_and_sort_requests,
    collect_secrets,
    har_convert_to_mite,
    host_allowed,
    is_static,
    select_requests,
    set_expected_status_code,
    set_request_headers_dict,
)

def _e(url, status, redirect="", started="2026-01-01T00:00:00.000Z"):
    return {
        "startedDateTime": started,
        "request": {"url": url},
        "response": {"status": status, "redirectURL": redirect},
    }


@pytest.mark.parametrize(
    "entries,expected,remaining",
    [
        ([_e("a", 200)], 200, 1),
        ([_e("a", 304)], (200, 304), 1),
        ([_e("a", 302, "b"), _e("b", 200)], 200, 1),
        ([_e("a", 302, "b"), _e("b", 302, "c"), _e("c", 200)], 200, 1),
        ([_e("a", 303, "b"), _e("b", 200)], 200, 1),
    ],
)
def test_set_expected_status_code(entries, expected, remaining):
    assert set_expected_status_code(entries[0], entries) == expected
    # redirect targets are collapsed into the first request
    assert len(entries) == remaining


def test_extract_and_sort_requests():
    har = {
        "log": {
            "entries": [
                _e("c", 200, started="2026-01-01T00:00:02.000Z"),
                _e("a", 200, started="2026-01-01T00:00:00.000Z"),
                _e("b", 200, started="2026-01-01T00:00:01.000Z"),
            ]
        }
    }
    assert [e["request"]["url"] for e in _extract_and_sort_requests(har)] == [
        "a",
        "b",
        "c",
    ]


def test_set_headers_drops_cookie_length_and_pseudo_headers():
    page = {
        "request": {
            "headers": [
                {"name": ":authority", "value": "x"},
                {"name": "Accept", "value": "*/*"},
                {"name": "Cookie", "value": "session=abc"},
                {"name": "content-length", "value": "3"},
                {"name": "X-Custom", "value": "kept"},
            ]
        }
    }
    assert set_request_headers_dict(page) == {"Accept": "*/*", "X-Custom": "kept"}


@pytest.mark.parametrize(
    "url,patterns,allowed",
    [
        ("https://shop.example/a", ["shop.example"], True),
        ("https://api.shop.example/a", ["*.shop.example"], True),
        ("https://shop.example.evil.test/a", ["shop.example"], False),
        ("http://mon.example:8000/x", ["mon.example"], True),
        ("http://mon.example:8000/x", ["mon.example:8000"], True),
        ("http://mon.example:8000/x", ["mon.example:9000"], False),
        ("https://SHOP.example/a", ["shop.EXAMPLE"], True),
    ],
)
def test_host_allowed(url, patterns, allowed):
    assert host_allowed(url, patterns) is allowed


@pytest.mark.parametrize(
    "entry,static",
    [
        ({"_resourceType": "image", "response": {}}, True),
        ({"_resourceType": "preflight", "response": {}}, True),
        ({"_resourceType": "xhr", "response": {"content": {"mimeType": "image/png"}}}, False),
        ({"response": {"content": {"mimeType": "text/css; charset=utf-8"}}}, True),
        ({"response": {"content": {"mimeType": "application/json"}}}, False),
        ({"response": {}}, False),
    ],
)
def test_is_static(entry, static):
    assert is_static(entry) is static


def test_secrets_expression_and_redact():
    secrets = Secrets()
    secrets.add("x-api-token", "tok_abcdef123456")
    secrets.add("email", "a.b@example.com")
    secrets.add("short", "stream")  # too short, would match ordinary text
    assert secrets.keys == {"tok_abcdef123456": "x_api_token", "a.b@example.com": "email"}
    assert secrets.expression("plain") == "'plain'"
    assert secrets.expression("tok_abcdef123456") == "_config(ctx, 'x_api_token')"
    assert secrets.expression("u=a.b%40example.com&s=stream") == (
        "'u=' + quote(_config(ctx, 'email'), safe=\"\") + '&s=stream'"
    )
    assert secrets.redact("/x?t=tok_abcdef123456") == "/x?t=<x_api_token>"


def test_secret_keys_are_unique_per_value():
    secrets = Secrets()
    secrets.add("x-api-token", "first-token-value")
    secrets.add("x-api-token", "second-token-value")
    secrets.add("x-api-token", "first-token-value")
    assert list(secrets.keys.values()) == ["x_api_token", "x_api_token_2"]


SAMPLE_DIR = Path(__file__).parent / "har"
SAMPLE_HOSTS = ["*.shop.example"]
SAMPLE_CONFIG = {
    "email": "load.test@example.com",
    "password": "replayed-password",
    "x_api_token": "tok_replayed_000",
    "authorization": "Bearer replayed",
}


def _sample_har(tmp_path, base_url=None):
    """sample.har, with both shop hosts pointed at ``base_url`` if given."""
    if base_url is None:
        return SAMPLE_DIR / "sample.har"
    har = tmp_path / "sample.har"
    text = (SAMPLE_DIR / "sample.har").read_text()
    for host in ["https://www.shop.example", "https://api.shop.example"]:
        text = text.replace(host, base_url)
    har.write_text(text)
    return har


def _load(path):
    return json.loads(Path(path).read_text())


def _convert_sample(tmp_path, *args, **kwargs):
    out = tmp_path / "journey.py"
    kwargs.setdefault("hosts", SAMPLE_HOSTS)
    har_convert_to_mite(str(_sample_har(tmp_path)), str(out), *args, **kwargs)
    return out


def test_sample_har_matches_expected_journey(tmp_path):
    """test/har/sample_journey.py is the reference output for test/har/sample.har.

    Regenerate it if the converter output changes on purpose.
    """
    out = _convert_sample(tmp_path)
    assert out.read_text() == (SAMPLE_DIR / "sample_journey.py").read_text()


def test_sample_har_has_no_recorded_secrets(tmp_path):
    out = _convert_sample(tmp_path)
    source = out.read_text()
    for value in [
        "jane.doe@example.com",
        "jane.doe%40example.com",
        "hunter2-secret",
        "tok_abcdef123456",
        "eyJhbGciOi",
        "session=abc",
    ]:
        assert value not in source


def test_collect_secrets_from_headers_query_and_bodies(tmp_path):
    har = _load(_sample_har(tmp_path))
    requests, _, _ = select_requests(har, SAMPLE_HOSTS)
    assert collect_secrets(requests).keys == {
        "jane.doe@example.com": "email",
        "hunter2-secret": "password",
        "tok_abcdef123456": "x_api_token",
        "Bearer eyJhbGciOi.payload.sig": "authorization",
    }


def test_recorded_gaps_with_zero_sleep(tmp_path):
    out = _convert_sample(tmp_path, 0)
    separations = [
        line.strip() for line in out.read_text().splitlines() if "separation(" in line
    ]
    # gap to the next kept request; the last one has none
    assert separations == [
        f"async with ensure_fixed_separation({gap}):"
        for gap in [1.0, 1.0, 1.0, 1.0, 1.0, 0.5, 0.5, 1.0, 0]
    ]
    assert "SECONDS_PER_JOURNEY = 7.0" in out.read_text()


@pytest.mark.parametrize(
    "hosts,message",
    [
        (None, "No --host given; nothing written."),
        (["nope"], "No requests matched --host nope; nothing written."),
    ],
)
def test_host_errors_report_hosts_and_write_nothing(tmp_path, hosts, message):
    out = tmp_path / "journey.py"
    with pytest.raises(HarConversionError) as excinfo:
        har_convert_to_mite(str(_sample_har(tmp_path)), str(out), hosts=hosts)
    text = str(excinfo.value)
    assert message in text
    # the report lists every host with non-static requests and suggests the
    # busiest one
    for host in ["api.shop.example", "www.shop.example", "analytics.example-ads.test"]:
        assert host in text
    assert "cdn.example-cdn.test" not in text
    assert "--host=api.shop.example" in text
    assert not out.exists()


def test_cli_reports_hosts_and_exits_1(tmp_path, capsys):
    from docopt import docopt

    import mite.__main__ as main

    har = _sample_har(tmp_path)
    out = tmp_path / "journey.py"
    opts = docopt(main.__doc__, ["har", str(har), str(out)])
    with pytest.raises(SystemExit) as excinfo:
        main.har_converter(opts)
    assert excinfo.value.code == 1
    assert "nothing written" in capsys.readouterr().err
    assert not out.exists()


def test_cli_passes_hosts_and_flags(tmp_path, capsys):
    from docopt import docopt

    import mite.__main__ as main

    har = _sample_har(tmp_path)
    out = tmp_path / "journey.py"
    opts = docopt(
        main.__doc__,
        ["har", str(har), str(out), "--host=*.shop.example", "--host=x.test",
         "--include-static", "--sleep-time=0"],
    )
    main.har_converter(opts)
    # 9 requests plus site.css, app.js, tea.png and the preflight; CDN assets
    # are on another host
    assert "Wrote 13 requests" in capsys.readouterr().out
    assert "/static/site.css" in out.read_text()


def test_har_convert_to_mite_real_recording(tmp_path):
    out = tmp_path / "journey.py"
    har_convert_to_mite(
        str(Path(__file__).parent / "test.har"),
        str(out),
        10,
        hosts=["confluence.atlassian.com"],
    )
    source = out.read_text()
    ast.parse(source)
    assert source.count("ensure_fixed_separation(10.0):") == 21
    assert "SECONDS_PER_JOURNEY = 210.0" in source


def _context(config=None):
    messages = []
    return Context(lambda msg: messages.append(msg), dict(config or {})), messages


def _import_journey(path):
    tree = ast.parse(path.read_text())
    # python -O strips assert statements, so checks must not use them
    assert not any(isinstance(node, ast.Assert) for node in ast.walk(tree))
    spec = importlib.util.spec_from_file_location("generated_journey", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.pop("generated_journey", None)
    spec.loader.exec_module(module)
    return module


def _sample_module(tmp_path, httpserver):
    base_url = httpserver.url_for("").rstrip("/")
    out = tmp_path / "journey.py"
    # small fixed separation keeps the test fast
    har_convert_to_mite(
        str(_sample_har(tmp_path, base_url)), str(out), 0.001, hosts=["localhost"]
    )
    return _import_journey(out)


def _expect_sample_requests(httpserver, basket_status=304):
    login = '{"email":"load.test@example.com","password":"replayed-password"}'
    httpserver.expect_ordered_request("/", "GET").respond_with_data("<html></html>")
    httpserver.expect_ordered_request(
        "/api/login", "POST", data=login.encode()
    ).respond_with_data("{}")
    httpserver.expect_ordered_request(
        "/api/items",
        "GET",
        query_string={"session_token": "tok_replayed_000", "page": "1"},
        headers={"x-api-token": "tok_replayed_000", "authorization": "Bearer replayed"},
    ).respond_with_data("[]")
    httpserver.expect_ordered_request("/old", "GET").respond_with_data(
        "", status=302, headers={"Location": httpserver.url_for("/new")}
    )
    httpserver.expect_ordered_request("/new", "GET").respond_with_data("{}")
    httpserver.expect_ordered_request(
        "/basket", "GET", query_string="email=load.test%40example.com"
    ).respond_with_data("<html></html>")
    httpserver.expect_ordered_request(
        "/api/basket/1", "PUT", data=b"name=tea&n=2"
    ).respond_with_data("{}")
    httpserver.expect_ordered_request("/api/basket", "GET").respond_with_data(
        "", status=basket_status
    )
    httpserver.expect_ordered_request("/api/basket/1", "DELETE").respond_with_data(
        "", status=204
    )
    httpserver.expect_ordered_request("/health", "HEAD").respond_with_data("")


@pytest.mark.asyncio
async def test_sample_har_journey_runs(tmp_path, httpserver):
    module = _sample_module(tmp_path, httpserver)
    _expect_sample_requests(httpserver)
    ctx, messages = _context(SAMPLE_CONFIG)

    await module.journey(ctx)

    httpserver.check_assertions()
    requests = [request for request, _ in httpserver.log]
    assert [(r.method, r.path) for r in requests] == [
        ("GET", "/"),
        ("POST", "/api/login"),
        ("GET", "/api/items"),
        ("GET", "/old"),
        ("GET", "/new"),
        ("GET", "/basket"),
        ("PUT", "/api/basket/1"),
        ("GET", "/api/basket"),
        ("DELETE", "/api/basket/1"),
        ("HEAD", "/health"),
    ]
    home, login = requests[0], requests[1]
    assert home.headers["User-Agent"] == "Mozilla/5.0"
    assert "Cookie" not in home.headers
    assert login.content_type == "application/json"
    assert login.content_length == len(login.get_data())
    assert not any(m["type"] in ("error", "exception") for m in messages)


@pytest.mark.asyncio
async def test_sample_har_journey_fails_on_unexpected_status(tmp_path, httpserver):
    module = _sample_module(tmp_path, httpserver)
    # recorded 304 accepts 200 or 304 only
    _expect_sample_requests(httpserver, basket_status=404)
    ctx, messages = _context(SAMPLE_CONFIG)

    with pytest.raises(MiteError) as excinfo:
        await module.journey(ctx)

    assert excinfo.value.fields["status_code"] == 404
    assert excinfo.value.fields["expected_status"] == [200, 304]
    assert [m["status_code"] for m in messages if m["type"] == "error"] == [404]
    # the journey stops at the failing request, before the later DELETE and HEAD
    assert [r.path for r, _ in httpserver.log] == [
        "/",
        "/api/login",
        "/api/items",
        "/old",
        "/new",
        "/basket",
        "/api/basket/1",
        "/api/basket",
    ]


@pytest.mark.asyncio
async def test_sample_har_journey_needs_config(tmp_path, httpserver):
    module = _sample_module(tmp_path, httpserver)
    httpserver.expect_request("/").respond_with_data("<html></html>")
    ctx, _ = _context({k: v for k, v in SAMPLE_CONFIG.items() if k != "password"})

    with pytest.raises(MiteError, match="Missing config 'password': set MITE_CONF_password"):
        await module.journey(ctx)
    assert [r.path for r, _ in httpserver.log] == ["/"]


@pytest.mark.parametrize(
    "target_tps,seconds,journeys",
    [(1, None, 1), (5, None, 5), (0.5, None, 1), (12.5, None, 13), (5, 0, 1)],
)
def test_sample_scenario_volume_follows_target_tps(
    tmp_path, target_tps, seconds, journeys
):
    module = _import_journey(_convert_sample(tmp_path))
    # 9 requests at the default 1s separation
    assert module.REQUESTS_PER_JOURNEY == 9
    assert module.SECONDS_PER_JOURNEY == 9.0
    module.TARGET_TPS = target_tps
    if seconds is not None:
        # a journey with no separation can't be sized; it runs one at a time
        module.SECONDS_PER_JOURNEY = seconds

    ((spec, datapool, volume_model),) = module.scenario()

    assert spec == "generated_journey:journey"
    assert datapool is None
    assert volume_model.duration == module.DURATION_S
    assert volume_model(0, 1) == journeys


def _entry(url, method, status, started, post_data=None):
    request = {"method": method, "url": url, "headers": []}
    if post_data is not None:
        request["postData"] = post_data
    return {
        "_resourceType": "fetch",
        "startedDateTime": started,
        "request": request,
        "response": {"status": status, "redirectURL": ""},
    }


def _convert_and_import(tmp_path, entries):
    har = tmp_path / "in.har"
    out = tmp_path / "generated_journey.py"
    har.write_text(json.dumps({"log": {"pages": [], "entries": entries}}))
    har_convert_to_mite(str(har), str(out), 0.001, hosts=["localhost"])
    return _import_journey(out)


# compact form a browser sends; re-encoding through json= would add spaces
RAW_JSON_BODY = '{"k":1,"s":"\u00e9"}'


def _all_methods_entries(httpserver):
    entries = []
    for i, method in enumerate(["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]):
        post_data = None
        if method in ("POST", "PUT", "PATCH"):
            post_data = {"mimeType": "application/json", "text": RAW_JSON_BODY}
        entries.append(
            _entry(
                httpserver.url_for(f"/{method.lower()}"),
                method,
                200,
                f"2026-01-01T00:00:0{i}.000Z",
                post_data,
            )
        )
        if post_data:
            entries[-1]["request"]["headers"] = [
                {"name": "Content-Type", "value": "application/json"},
                # deliberately wrong; must not reach the server
                {"name": "Content-Length", "value": "999"},
            ]
    return entries


@pytest.mark.asyncio
async def test_generated_journey_runs_all_methods(tmp_path, httpserver):
    entries = _all_methods_entries(httpserver)
    for method in ["GET", "DELETE", "HEAD", "OPTIONS"]:
        httpserver.expect_request(f"/{method.lower()}", method).respond_with_data("ok")
    for method in ["POST", "PUT", "PATCH"]:
        httpserver.expect_request(
            f"/{method.lower()}", method, data=RAW_JSON_BODY.encode()
        ).respond_with_data("ok")
    module = _convert_and_import(tmp_path, entries)

    ctx, _ = _context()
    await module.journey(ctx)

    assert [r.method for r, _ in httpserver.log] == [
        "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"
    ]
    assert all(resp.status_code == 200 for _, resp in httpserver.log)
    for request, _ in httpserver.log:
        if request.method in ("POST", "PUT", "PATCH"):
            assert request.content_length == len(RAW_JSON_BODY.encode())
            assert request.content_type == "application/json"


@pytest.mark.parametrize(
    "recorded_status,replay_status,expected_status,ok",
    [
        (200, 500, 200, False),
        (304, 200, [200, 304], True),
        (304, 304, [200, 304], True),
        (304, 301, [200, 304], False),
        (304, 204, [200, 304], False),
    ],
)
@pytest.mark.asyncio
async def test_generated_journey_checks_expected_status(
    tmp_path, httpserver, recorded_status, replay_status, expected_status, ok
):
    checked_url = httpserver.url_for("/checked")
    after_url = httpserver.url_for("/after")
    httpserver.expect_request("/checked").respond_with_data("", status=replay_status)
    httpserver.expect_request("/after").respond_with_data("ok", status=200)
    module = _convert_and_import(
        tmp_path,
        [
            _entry(checked_url, "GET", recorded_status, "2026-01-01T00:00:00.000Z"),
            _entry(after_url, "GET", 200, "2026-01-01T00:00:01.000Z"),
        ],
    )

    ctx, messages = _context()
    if ok:
        await module.journey(ctx)
        assert [r.path for r, _ in httpserver.log] == ["/checked", "/after"]
    else:
        with pytest.raises(MiteError) as excinfo:
            await module.journey(ctx)
        assert excinfo.value.fields["status_code"] == replay_status
        assert excinfo.value.fields["expected_status"] == expected_status
        assert any(
            m["type"] == "error" and m["status_code"] == replay_status
            for m in messages
        )
        # the journey stops at the failing request; /after is never sent
        assert [r.path for r, _ in httpserver.log] == ["/checked"]
