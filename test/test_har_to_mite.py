from mite.har_to_mite import (
    set_expected_status_code,
    set_request_headers_dict,
    set_request_body,
)


# page with status_code=0
SIMPLE_PAGE = {
    'startedDateTime': 'date-time',
    'request': {'method': '', 'url': '', 'headers': [], 'postData': 'body'},
    'response': {'redirectURL': '', 'status': 200},
}

# page with status_code=304
PAGE_304 = {
    'startedDateTime': 'date-time',
    'request': {'method': '', 'url': '', 'headers': [], 'postData': 'body'},
    'response': {'redirectURL': '', 'status': 304},
}

# list for the page with status_code=302
PAGES_200 = [
    # page with status code = 302 -> index 0
    {
        'startedDateTime': 'date-time',
        'request': {'method': '', 'url': '', 'headers': [], 'postData': 'body'},
        'response': {'redirectURL': '302_redirection.url', 'status': 302},
    },
    # page with status code = 304 -> index 1
    {
        'startedDateTime': 'date-time',
        'request': {
            'method': '',
            'url': 'random_page.url',
            'headers': [],
            'postData': 'body',
        },
        'response': {'redirectURL': '', 'status': 304},
    },
    # page with the redirection url for the 302 status code -> index 2
    {
        'startedDateTime': 'date-time',
        'request': {
            'method': '',
            'url': '302_redirection.url',
            'headers': [],
            'postData': 'body',
        },
        'response': {'redirectURL': '', 'status': 200},
    },
]

# list for the page with multiple redirections
PAGES_MULTIPLE_REDIRECTS = [
    # page with status code = 302 -> index 0
    {
        'startedDateTime': 'date-time',
        'request': {'method': '', 'url': '', 'headers': [], 'postData': 'body'},
        'response': {'redirectURL': '302_first_redirection.url', 'status': 302},
    },
    # page with status code = 302 -> index 1
    {
        'startedDateTime': 'date-time',
        'request': {
            'method': '',
            'url': '302_first_redirection.url',
            'headers': [],
            'postData': 'body',
        },
        'response': {'redirectURL': '302_second_redirection.url', 'status': 302},
    },
    # page with the redirection url for the 302 status code -> index 2
    {
        'startedDateTime': 'date-time',
        'request': {
            'method': '',
            'url': '302_second_redirection.url',
            'headers': [],
            'postData': 'body',
        },
        'response': {'redirectURL': '', 'status': 200},
    },
]

# page with headers
PAGE_HEADERS = {
    'request': {
        'headers': [
            {"name": "Name0", "value": "value0"},
            {"name": "Name1", "value": "value1"},
            {"name": "Cookie", "value": "cookie_value"},
            {"name": "Name3", "value": "value3"},
        ]
    }
}

# page with body
PAGE_WITH_BODY = {
    'request': {'postData': {"name0": "value0", "name1": "value1; subname1=value11"}}
}


def test_status_code_is_not_3xx():
    status, _ = set_expected_status_code(SIMPLE_PAGE, [SIMPLE_PAGE])
    assert status == 200


def test_status_code_304_behaviour():
    status, groups = set_expected_status_code(PAGE_304, [PAGE_304])
    assert status == "200, 304"
    assert groups == "_in_groups"


def test_status_code_after_redirect():
    status, _ = set_expected_status_code(PAGES_200[0], PAGES_200)
    assert status == 200


def test_multi_redirect():
    status, _ = set_expected_status_code(
        PAGES_MULTIPLE_REDIRECTS[0], PAGES_MULTIPLE_REDIRECTS
    )
    assert status == 200


def test_set_headers():
    assert len(set_request_headers_dict(PAGE_HEADERS)) == 3


def test_cookie_not_in_headers():
    assert 'Cookie' not in set_request_headers_dict(PAGE_HEADERS)


def test_set_body():
    assert "name0" in set_request_body('post', PAGE_WITH_BODY)


def test_body_empty_for_get():
    assert set_request_body('get', PAGE_WITH_BODY) == ""
