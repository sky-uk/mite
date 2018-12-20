from mite.har_to_mite import (
    set_expected_status_code,
    check_request_url,
    set_request_headers_dict,
    set_request_body,
)


# page with status_code=0
page_0 = {
    'startedDateTime': 'date-time',
    'request': {'method': '', 'url': '', 'headers': [], 'postData': 'body'},
    'response': {'redirectURL': '', 'status': 0}
}

# page with status_code=304
page_304 = {
    'startedDateTime': 'date-time',
    'request': {'method': '', 'url': '', 'headers': [], 'postData': 'body'},
    'response': {'redirectURL': '', 'status': 304}
}

# list for the page with status_code=302
pages_302 = [
    # page with status code = 302 -> index 0
    {'startedDateTime': 'date-time',
     'request': {'method': '', 'url': '', 'headers': [], 'postData': 'body'},
     'response': {'redirectURL': '302_redirection.url', 'status': 302}},
    # page with status code = 304 -> index 1
    {'startedDateTime': 'date-time',
     'request': {'method': '', 'url': 'random_page.url', 'headers': [], 'postData': 'body'},
     'response': {'redirectURL': '', 'status': 304}},
    # page with the redirection url for the 302 status code -> index 2
    {'startedDateTime': 'date-time',
     'request': {'method': '', 'url': '302_redirection.url', 'headers': [], 'postData': 'body'},
     'response': {'redirectURL': '', 'status': 345}},
]

# list for the page with multiple redirections
pages_multi_302 = [
    # page with status code = 302 -> index 0
    {'startedDateTime': 'date-time',
     'request': {'method': '', 'url': '', 'headers': [], 'postData': 'body'},
     'response': {'redirectURL': '302_first_redirection.url', 'status': 302}},
    # page with status code = 302 -> index 1
    {'startedDateTime': 'date-time',
     'request': {'method': '', 'url': '302_first_redirection.url', 'headers': [], 'postData': 'body'},
     'response': {'redirectURL': '302_second_redirection.url', 'status': 302}},
    # page with the redirection url for the 302 status code -> index 2
    {'startedDateTime': 'date-time',
     'request': {'method': '', 'url': '302_second_redirection.url', 'headers': [], 'postData': 'body'},
     'response': {'redirectURL': '', 'status': 345}},
]

# page with headers
page_headers = {
    'request': {
        'headers': [
            {"name": "Name0", "value": "value0"},
            {"name": "Name1", "value": "value1"},
            {"name": "Cookie", "value": "cookie_value"},
            {"name": "Name3", "value": "value3"}
        ]
    }
}

# page with body
page_body = {
    'request': {
        'postData': {
            "name0": "value0",
            "name1": "value1; subname1=value11",
        }
    }
}


def test_status_code_is_not_3xx():
    status, _ = set_expected_status_code(None, page_0, 0, 1, None)
    assert status == page_0['response']['status']


def test_status_code_is_304():
    status, groups = set_expected_status_code(None, page_304, 0, 1, None)
    assert status == "200, 304"
    assert groups == "_in_groups"


def test_status_code_is_302():
    p_list = list()
    page_302 = pages_302[0]
    status, _ = set_expected_status_code(pages_302, page_302, 0, 3, p_list)
    assert status == pages_302[2]['response']['status']
    assert pages_302[2]['request']['url'] in p_list


def test_multi_status_code_302():
    p_list = list()
    page_302 = pages_multi_302[0]
    status, _ = set_expected_status_code(pages_multi_302, page_302, 0, 3, p_list)
    assert status == pages_302[2]['response']['status']
    assert pages_multi_302[1]['request']['url'] in p_list
    assert pages_multi_302[2]['request']['url'] in p_list


def test_check_url():
    p_list = ['test.url']
    check_request_url('test.url', p_list)
    assert p_list == []


def test_set_headers():
    headers = set_request_headers_dict(page_headers)
    assert 'Cookie' not in headers


def test_set_body():
    body = set_request_body('post', page_body)
    assert "json" in body
