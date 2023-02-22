import os
from copy import deepcopy
from tempfile import NamedTemporaryFile

import pytest

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
    "request": {"postData": {"name0": "value0", "name1": "value1; subname1=value11"}}
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
    status, _ = set_expected_status_code(SIMPLE_PAGE, [SIMPLE_PAGE])
    assert status == 200


def test_status_code_304_behaviour():
    status, groups = set_expected_status_code(PAGE_304, [PAGE_304])
    assert status == "200, 304"
    assert groups == "_in_groups"


def test_status_code_after_redirect():
    entries = deepcopy(PAGES_200)["log"]["entries"]  # Create a copy
    status, _ = set_expected_status_code(entries[0], entries)
    assert status == 200


def test_multi_redirect():
    status, _ = set_expected_status_code(
        PAGES_MULTIPLE_REDIRECTS[0], PAGES_MULTIPLE_REDIRECTS
    )
    assert status == 200


def test_set_headers():
    assert len(set_request_headers_dict(PAGE_HEADERS)) == 3


def test_cookie_not_in_headers():
    assert "Cookie" not in set_request_headers_dict(PAGE_HEADERS)


def test_set_body():
    assert "name0" in set_request_body("post", PAGE_WITH_BODY)


def test_body_empty_for_get():
    assert set_request_body("get", PAGE_WITH_BODY) == ""


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


@pytest.mark.skip(reason="unfinished")
def test_render_transaction():
    assert (
        _render_journey_transaction(
            PAGES_MULTIPLE_REDIRECTS[0], "get", "_in_groups", "200", 1
        )
        == '    async with ctx.transaction("Request get {{url}}"):\n'
        "        resp = await ctx.browser.get(\n"
        "            '{{url}}',\n"
        "            headers={{headers}},\n"
        "            {{json}}"
        "            )\n"
        "        check_status_code{{check_groups}}(resp, {{expected_status}})\n"
        "    await sleep({{sleep}})\n\n\n"
    )
