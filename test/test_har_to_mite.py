import ast
import importlib.util
import json
import sys
from copy import deepcopy
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

# page with status_code=0
SIMPLE_PAGE = {
    "startedDateTime": "date-time",
    "request": {"method": "", "url": "", "headers": [], "postData": "body"},
    "response": {"redirectURL": "", "status": 200},
}

# page with status_code=304
PAGE_304 = {
    "startedDateTime": "date-time",
    "request": {"method": "", "url": "", "headers": [], "postData": "body"},
    "response": {"redirectURL": "", "status": 304},
}

# list for the page with status_code=302
PAGES_200 = {
    "log": {
        "entries": [
            # page with status code = 302 -> index 0
            {
                "startedDateTime": "2019-08-16T13:00:00.000Z",
                "request": {
                    "method": "",
                    "url": "a_page.url",
                    "headers": [],
                    "postData": "body",
                },
                "response": {"redirectURL": "302_redirection.url", "status": 302},
            },
            # page with status code = 304 -> index 1
            {
                "startedDateTime": "2019-08-16T12:59:00.000Z",
                "request": {
                    "method": "",
                    "url": "random_page.url",
                    "headers": [],
                    "postData": "body",
                },
                "response": {"redirectURL": "", "status": 304},
            },
            # page with the redirection url for the 302 status code -> index 2
            {
                "startedDateTime": "2019-08-16T12:59:30.000Z",
                "request": {
                    "method": "",
                    "url": "302_redirection.url",
                    "headers": [],
                    "postData": "body",
                },
                "response": {"redirectURL": "", "status": 200},
            },
        ]
    }
}

# list for the page with multiple redirections
PAGES_MULTIPLE_REDIRECTS = [
    # page with status code = 302 -> index 0
    {
        "startedDateTime": "date-time",
        "request": {"method": "", "url": "", "headers": [], "postData": "body"},
        "response": {"redirectURL": "302_first_redirection.url", "status": 302},
    },
    # page with status code = 302 -> index 1
    {
        "startedDateTime": "date-time",
        "request": {
            "method": "",
            "url": "302_first_redirection.url",
            "headers": [],
            "postData": "body",
        },
        "response": {"redirectURL": "302_second_redirection.url", "status": 302},
    },
    # page with the redirection url for the 302 status code -> index 2
    {
        "startedDateTime": "date-time",
        "request": {
            "method": "",
            "url": "302_second_redirection.url",
            "headers": [],
            "postData": "body",
        },
        "response": {"redirectURL": "", "status": 200},
    },
]

# page with headers
PAGE_HEADERS = {
    "request": {
        "headers": [
            {"name": "Name0", "value": "value0"},
            {"name": "Name1", "value": "value1"},
            {"name": "Cookie", "value": "cookie_value"},
            {"name": "Name3", "value": "value3"},
        ]
    }
}

def test_status_code_is_not_3xx():
    status = set_expected_status_code(SIMPLE_PAGE, [SIMPLE_PAGE])
    assert status == 200


def test_status_code_304_behaviour():
    status = set_expected_status_code(PAGE_304, [PAGE_304])
    assert status == (200, 304)


def test_status_code_after_redirect():
    entries = deepcopy(PAGES_200)["log"]["entries"]  # Create a copy
    status = set_expected_status_code(entries[0], entries)
    assert status == 200


def test_multi_redirect():
    status = set_expected_status_code(
        PAGES_MULTIPLE_REDIRECTS[0], PAGES_MULTIPLE_REDIRECTS
    )
    assert status == 200


def test_set_headers():
    assert len(set_request_headers_dict(PAGE_HEADERS)) == 3


def test_cookie_not_in_headers():
    assert "Cookie" not in set_request_headers_dict(PAGE_HEADERS)


def test_pseudo_and_length_headers_dropped():
    page = {
        "request": {
            "headers": [
                {"name": ":authority", "value": "x"},
                {"name": "content-length", "value": "3"},
                {"name": "Accept", "value": "*/*"},
            ]
        }
    }
    assert set_request_headers_dict(page) == {"Accept": "*/*"}


def test_other_3xx_redirects_are_collapsed():
    entries = [
        {"request": {"url": "a"}, "response": {"status": 303, "redirectURL": "b"}},
        {"request": {"url": "b"}, "response": {"status": 200, "redirectURL": ""}},
    ]
    assert set_expected_status_code(entries[0], entries) == 200
    assert len(entries) == 1


def test_extract_and_sort_requests():
    urls = [page["request"]["url"] for page in _extract_and_sort_requests(PAGES_200)]
    assert urls == ["random_page.url", "302_redirection.url", "a_page.url"]


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
SAMPLE_BASE_URL = "https://shop.example"
SAMPLE_CONFIG = {
    "email": "load.test@example.com",
    "password": "replayed-password",
    "x_api_token": "tok_replayed_000",
    "authorization": "Bearer replayed",
}


def _sample_har(tmp_path, base_url):
    har = tmp_path / "sample.har"
    har.write_text(
        (SAMPLE_DIR / "sample.har").read_text().replace("__BASE_URL__", base_url)
    )
    return har


def _load(path):
    return json.loads(Path(path).read_text())


def test_sample_har_matches_expected_journey(tmp_path):
    """test/har/sample_journey.py is the reference output for test/har/sample.har.

    Regenerate it if the converter output changes on purpose.
    """
    out = tmp_path / "journey.py"
    har_convert_to_mite(
        str(_sample_har(tmp_path, SAMPLE_BASE_URL)), str(out), hosts=["shop.example"]
    )
    assert out.read_text() == (SAMPLE_DIR / "sample_journey.py").read_text()


def test_sample_har_has_no_recorded_secrets(tmp_path):
    out = tmp_path / "journey.py"
    har_convert_to_mite(
        str(_sample_har(tmp_path, SAMPLE_BASE_URL)), str(out), hosts=["shop.example"]
    )
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


def test_selection_drops_static_other_hosts_and_unsupported(tmp_path):
    har = _load(_sample_har(tmp_path, SAMPLE_BASE_URL))
    requests, dropped_hosts, dropped_static = select_requests(har, ["shop.example"])
    assert [(r.method, r.url.split("shop.example")[1]) for r in requests] == [
        ("get", "/"),
        ("post", "/api/login"),
        ("get", "/api/items?session_token=tok_abcdef123456&page=1"),
        ("get", "/old"),
        ("get", "/basket?email=jane.doe%40example.com"),
        ("put", "/api/basket/1"),
        ("get", "/api/basket"),
        ("delete", "/api/basket/1"),
        ("head", "/health"),
    ]
    # css, cdn logo, preflight, and a png found by MIME type
    assert dropped_static == 4
    assert dict(dropped_hosts) == {"analytics.example-ads.test": 1}


def test_include_static_keeps_assets_on_allowed_hosts(tmp_path):
    har = _load(_sample_har(tmp_path, SAMPLE_BASE_URL))
    requests, _, dropped_static = select_requests(
        har, ["shop.example"], include_static=True
    )
    paths = [r.url.split("shop.example")[1] for r in requests]
    assert "/static/site.css" in paths and "/img/tea.png" in paths
    assert dropped_static == 0


def test_collect_secrets_from_headers_query_and_bodies(tmp_path):
    har = _load(_sample_har(tmp_path, SAMPLE_BASE_URL))
    requests, _, _ = select_requests(har, ["shop.example"])
    assert collect_secrets(requests).keys == {
        "jane.doe@example.com": "email",
        "hunter2-secret": "password",
        "tok_abcdef123456": "x_api_token",
        "Bearer eyJhbGciOi.payload.sig": "authorization",
    }


def test_recorded_gaps_with_zero_sleep(tmp_path):
    out = tmp_path / "journey.py"
    har_convert_to_mite(
        str(_sample_har(tmp_path, SAMPLE_BASE_URL)), str(out), 0, hosts=["shop.example"]
    )
    separations = [
        line.strip() for line in out.read_text().splitlines() if "separation(" in line
    ]
    # gap to the next kept request; the last one has none
    assert separations == [
        f"async with ensure_fixed_separation({gap}):"
        for gap in [1.0, 1.0, 1.0, 1.0, 1.0, 0.5, 0.5, 1.0, 0]
    ]
    assert "SECONDS_PER_JOURNEY = 7.0" in out.read_text()


def test_without_hosts_reports_and_writes_nothing(tmp_path):
    out = tmp_path / "journey.py"
    with pytest.raises(HarConversionError) as excinfo:
        har_convert_to_mite(str(_sample_har(tmp_path, SAMPLE_BASE_URL)), str(out))
    message = str(excinfo.value)
    assert "No --host given; nothing written." in message
    assert "shop.example" in message
    assert "analytics.example-ads.test" in message
    assert "--host=shop.example" in message
    assert not out.exists()


def test_unmatched_hosts_report_and_write_nothing(tmp_path):
    out = tmp_path / "journey.py"
    with pytest.raises(HarConversionError, match="No requests matched --host nope"):
        har_convert_to_mite(
            str(_sample_har(tmp_path, SAMPLE_BASE_URL)), str(out), hosts=["nope"]
        )
    assert not out.exists()


def test_cli_reports_hosts_and_exits_1(tmp_path, capsys):
    from docopt import docopt

    import mite.__main__ as main

    har = _sample_har(tmp_path, SAMPLE_BASE_URL)
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

    har = _sample_har(tmp_path, SAMPLE_BASE_URL)
    out = tmp_path / "journey.py"
    opts = docopt(
        main.__doc__,
        ["har", str(har), str(out), "--host=shop.example", "--host=x.test",
         "--include-static", "--sleep-time=0"],
    )
    main.har_converter(opts)
    assert "Wrote 12 requests" in capsys.readouterr().out
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
    # checks must survive python -O
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
    # the journey stops at the failing request
    assert [r.path for r, _ in httpserver.log][-1] == "/api/basket"


@pytest.mark.asyncio
async def test_sample_har_journey_needs_config(tmp_path, httpserver):
    module = _sample_module(tmp_path, httpserver)
    httpserver.expect_request("/").respond_with_data("<html></html>")
    ctx, _ = _context({k: v for k, v in SAMPLE_CONFIG.items() if k != "password"})

    with pytest.raises(MiteError, match="Missing config 'password': set MITE_CONF_password"):
        await module.journey(ctx)
    assert [r.path for r, _ in httpserver.log] == ["/"]


@pytest.mark.parametrize(
    "target_tps,journeys", [(1, 1), (5, 5), (0.5, 1), (12.5, 13)]
)
def test_sample_scenario_volume_follows_target_tps(tmp_path, httpserver, target_tps, journeys):
    module = _sample_module(tmp_path, httpserver)
    module.TARGET_TPS = target_tps
    ((spec, datapool, volume_model),) = module.scenario()
    assert spec == "generated_journey:journey"
    assert datapool is None
    assert volume_model.duration == module.DURATION_S
    # 10 requests a run at 0.001s each: one journey gives ~10000 req/s, so
    # use the recorded default of 1s per request for a realistic check
    module.SECONDS_PER_JOURNEY = module.REQUESTS_PER_JOURNEY * 1.0
    ((_, _, volume_model),) = module.scenario()
    assert volume_model(0, 1) == journeys


def test_scenario_with_zero_length_journey_runs_one(tmp_path, httpserver):
    module = _sample_module(tmp_path, httpserver)
    module.SECONDS_PER_JOURNEY = 0
    ((_, _, volume_model),) = module.scenario()
    assert volume_model(0, 1) == 1


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


@pytest.mark.asyncio
async def test_generated_journey_raises_on_status_mismatch(tmp_path, httpserver):
    url = httpserver.url_for("/x")
    httpserver.expect_request("/x").respond_with_data("nope", status=500)
    module = _convert_and_import(
        tmp_path, [_entry(url, "GET", 200, "2026-01-01T00:00:00.000Z")]
    )

    ctx, messages = _context()
    with pytest.raises(MiteError) as excinfo:
        await module.journey(ctx)
    assert excinfo.value.fields["status_code"] == 500
    assert excinfo.value.fields["expected_status"] == 200
    assert any(m["type"] == "error" and m["status_code"] == 500 for m in messages)


@pytest.mark.parametrize("status,ok", [(200, True), (304, True), (301, False), (204, False)])
@pytest.mark.asyncio
async def test_generated_journey_304_is_exact(tmp_path, httpserver, status, ok):
    url = httpserver.url_for("/cached")
    httpserver.expect_request("/cached").respond_with_data("", status=status)
    module = _convert_and_import(
        tmp_path, [_entry(url, "GET", 304, "2026-01-01T00:00:00.000Z")]
    )

    ctx, _ = _context()
    if ok:
        await module.journey(ctx)
    else:
        with pytest.raises(MiteError):
            await module.journey(ctx)
