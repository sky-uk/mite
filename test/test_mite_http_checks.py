from types import SimpleNamespace

import pytest

from mite_http.checks import UnexpectedResponseCodeError, check_status_code


def _resp(status_code, url="http://h/x"):
    return SimpleNamespace(status_code=status_code, text="body", headers={}, url=url)


@pytest.mark.parametrize("status,expected", [(200, 200), (304, (200, 304))])
def test_match_passes(status, expected):
    check_status_code(_resp(status), expected)


# 204 shares a class with 200, so this shows the match is exact
@pytest.mark.parametrize("expected", [200, (200, 304)])
def test_mismatch_raises(expected):
    with pytest.raises(UnexpectedResponseCodeError) as excinfo:
        check_status_code(_resp(204), expected)
    assert excinfo.value.fields["status_code"] == 204
    assert excinfo.value.fields["url"] == "http://h/x"
    assert "http://h/x" in str(excinfo.value)


def test_unknown_expected_type():
    with pytest.raises(ValueError):
        check_status_code(_resp(200), "200")


def test_url_read_from_wrapped_response():
    page = SimpleNamespace(
        status_code=500, text="", headers={}, response=SimpleNamespace(url="http://p")
    )
    with pytest.raises(UnexpectedResponseCodeError) as excinfo:
        check_status_code(page, 200)
    assert excinfo.value.fields["url"] == "http://p"
