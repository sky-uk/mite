import ast
import importlib.util
import json
import os
import sys
from copy import deepcopy
from tempfile import NamedTemporaryFile

import pytest
from mite.context import Context
from mite.exceptions import MiteError
from mite.har_to_mite import (
    _extract_and_sort_requests,
    _parse_urls,
    _render_journey_transaction,
    har_convert_to_mite,
    set_expected_status_code,
    set_request_body,
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

# page with body
PAGE_WITH_BODY = {
    "request": {
        "postData": {"mimeType": "application/json", "text": '{"name0": "value0"}'}
    }
}

PAGE_WITH_FORM_BODY = {
    "request": {
        "postData": {
            "mimeType": "application/x-www-form-urlencoded",
            "text": "a=1&b='2'",
        }
    }
}

PAGE_WITH_BAD_JSON_BODY = {
    "request": {"postData": {"mimeType": "application/json", "text": "not json"}}
}


# Block in the har where request urls are pulled from
PAGE_TITLES = {
    "log": {
        "pages": [
            {
                "startedDateTime": "2019-08-16T13:24:36.702Z",
                "id": "page_3",
                "title": "https://search.mysite.co.uk/search?q=sport&scope=",
                "pageTimings": {
                    "onContentLoad": 1718.2020000182092,
                    "onLoad": 2711.600000038743,
                },
            },
            {
                "startedDateTime": "2019-08-16T13:24:27.717Z",
                "id": "page_2",
                "title": "https://www.mysite.co.uk/news",
                "pageTimings": {
                    "onContentLoad": 1239.6070000249892,
                    "onLoad": 3207.3920000111684,
                },
            },
            {
                "startedDateTime": "2019-08-16T13:24:18.491Z",
                "id": "page_1",
                "title": "https://www.mysite.co.uk/news/england1",
                "pageTimings": {
                    "onContentLoad": 1093.1039999704808,
                    "onLoad": 1693.9799999818206,
                },
            },
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


def test_json_body_sent_verbatim():
    assert set_request_body(PAGE_WITH_BODY) == "            data='{\"name0\": \"value0\"}',\n"


def test_set_form_body():
    assert set_request_body(PAGE_WITH_FORM_BODY) == '            data="a=1&b=\'2\'",\n'


def test_invalid_json_body_sent_verbatim():
    assert set_request_body(PAGE_WITH_BAD_JSON_BODY) == "            data='not json',\n"


def test_body_empty_without_post_data():
    assert set_request_body({"request": {}}) == ""


def test_parse_urls():
    assert _parse_urls(PAGE_TITLES) == [
        "https://search.mysite.co.uk/search?q=sport&scope=",
        "https://www.mysite.co.uk/news",
        "https://www.mysite.co.uk/news/england1",
    ]


def test_extract_and_sort_requests():
    urls = [page["request"]["url"] for page in _extract_and_sort_requests(PAGES_200)]
    assert urls == ["random_page.url", "302_redirection.url", "a_page.url"]


def test_har_convert_to_mite():
    with NamedTemporaryFile() as test_har:
        testinputfile = os.path.join(os.path.dirname(__file__), "test.har")
        testoutputfile = test_har.name

        har_convert_to_mite(testinputfile, testoutputfile, 0)

        with open(testoutputfile, "r") as testharoutfile:
            testharstr = testharoutfile.read()
        assert "await sleep(0)" in testharstr
        assert "await sleep(49)" in testharstr
        assert "await sleep(4)" in testharstr


def test_har_convert_to_mite_10secs():
    with NamedTemporaryFile() as test_har:
        testinputfile = os.path.join(os.path.dirname(__file__), "test.har")
        testoutputfile = test_har.name

        har_convert_to_mite(testinputfile, testoutputfile, 10)

        with open(testoutputfile, "r") as testharoutfile:
            testharstr = testharoutfile.read()
        assert "await sleep(10)" in testharstr


def test_render_transaction():
    page = {
        "request": {
            "url": "http://h/a?q='x'",
            "headers": [{"name": "Accept", "value": "*/*"}],
        }
    }
    assert _render_journey_transaction(page, "get", 200, 1) == (
        "    async with ctx.transaction(\"Request get http://h/a?q='x'\"):\n"
        "        resp = await ctx.browser.get(\n"
        "            \"http://h/a?q='x'\",\n"
        "            headers={'Accept': '*/*'},\n"
        "        )\n"
        "        check_status_code(resp, 200)\n"
        "    await sleep(1)\n\n"
    )


def _context():
    messages = []
    return Context(lambda msg: messages.append(msg), {}), messages


def _entry(url, method, status, started, post_data=None):
    request = {"method": method, "url": url, "headers": []}
    if post_data is not None:
        request["postData"] = post_data
    return {
        "startedDateTime": started,
        "request": request,
        "response": {"status": status, "redirectURL": ""},
    }


def _write_har(path, entries):
    pages = [
        {"startedDateTime": "2026-01-01T00:00:00.000Z", "title": e["request"]["url"]}
        for e in entries
    ]
    path.write_text(json.dumps({"log": {"pages": pages, "entries": entries}}))


def _convert_and_import(tmp_path, entries):
    har = tmp_path / "in.har"
    out = tmp_path / "generated_journey.py"
    _write_har(har, entries)
    har_convert_to_mite(str(har), str(out), 0)
    source = out.read_text()
    tree = ast.parse(source)
    # checks must survive python -O
    assert not any(isinstance(node, ast.Assert) for node in ast.walk(tree))
    spec = importlib.util.spec_from_file_location("generated_journey", out)
    module = importlib.util.module_from_spec(spec)
    sys.modules.pop("generated_journey", None)
    spec.loader.exec_module(module)
    return module


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
