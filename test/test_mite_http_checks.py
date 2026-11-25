from types import SimpleNamespace

import pytest

from mite.exceptions import MiteError
from mite_http.checks import (
    UnexpectedResponseCodeError,
    check_status_code,
    check_status_code_in_groups,
    is_error_status_code,
)


def _resp(status_code, url="http://h/x"):
    return SimpleNamespace(status_code=status_code, text="body", headers={}, url=url)


def test_exact_match_passes():
    check_status_code(_resp(200), 200)


def test_iterable_match_passes():
    check_status_code(_resp(304), (200, 304))


@pytest.mark.parametrize("expected", [200, (200, 304)])
def test_mismatch_raises_mite_error(expected):
    with pytest.raises(MiteError) as excinfo:
        check_status_code(_resp(500), expected)
    assert isinstance(excinfo.value, UnexpectedResponseCodeError)
    assert excinfo.value.fields["status_code"] == 500
    assert excinfo.value.fields["url"] == "http://h/x"
    assert "http://h/x" in str(excinfo.value)


def test_iterable_is_not_group_match():
    with pytest.raises(UnexpectedResponseCodeError):
        check_status_code(_resp(204), (200, 304))


def test_unknown_expected_type():
    with pytest.raises(ValueError):
        check_status_code(_resp(200), "200")


def test_on_failure_called_only_on_mismatch():
    calls = []
    check_status_code(_resp(200), 200, on_failure=calls.append)
    assert calls == []
    resp = _resp(404)
    with pytest.raises(UnexpectedResponseCodeError):
        check_status_code(resp, 200, on_failure=calls.append)
    assert calls == [resp]


def test_url_read_from_wrapped_response():
    page = SimpleNamespace(
        status_code=500, text="", headers={}, response=SimpleNamespace(url="http://p")
    )
    with pytest.raises(UnexpectedResponseCodeError) as excinfo:
        check_status_code(page, 200)
    assert excinfo.value.fields["url"] == "http://p"


def test_groups_match_hundreds_digit():
    check_status_code_in_groups(_resp(201), 200, 400)
    check_status_code_in_groups(_resp(404), 200, 400)


def test_groups_mismatch_raises_and_calls_hook():
    calls = []
    with pytest.raises(UnexpectedResponseCodeError) as excinfo:
        check_status_code_in_groups(_resp(500), 200, 300, on_failure=calls.append)
    assert excinfo.value.fields["expected_status"] == "2**, 3**"
    assert len(calls) == 1


@pytest.mark.parametrize(
    "code,expected", [(200, False), (399, False), (400, True), ([200, 503], True)]
)
def test_is_error_status_code(code, expected):
    assert is_error_status_code(code) is expected
