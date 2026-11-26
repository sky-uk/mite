from collections.abc import Iterable

from mite.exceptions import MiteError

__all__ = [
    "UnexpectedResponseCodeError",
    "check_status_code",
]


def _response_url(resp):
    url = getattr(resp, "url", None)
    if url is None:
        # mite_browser.Page wraps the underlying response
        url = getattr(getattr(resp, "response", None), "url", None)
    return url


class UnexpectedResponseCodeError(MiteError):
    """Raised when an HTTP response has an unexpected status code."""

    def __init__(self, expected_code, resp):
        url = _response_url(resp)
        message = f"Expected HTTP response code of {expected_code} returned code was {resp.status_code}"
        if url:
            message += f" for {url}"
        super().__init__(
            message,
            body=getattr(resp, "text", None),
            status_code=resp.status_code,
            headers=getattr(resp, "headers", None),
            expected_status=expected_code,
            actual_status=resp.status_code,
            url=url,
        )


def check_status_code(resp, expected: int | Iterable[int]) -> None:
    """Raise ``UnexpectedResponseCodeError`` unless ``resp.status_code`` matches exactly.

    ``expected`` is an int, or an iterable of ints for any-of matching.
    """
    if isinstance(expected, int):
        matched = resp.status_code == expected
    elif isinstance(expected, Iterable) and not isinstance(expected, (str, bytes)):
        expected = list(expected)
        matched = resp.status_code in expected
    else:
        raise ValueError(f"Unknown type of expected: {type(expected)}")
    if not matched:
        raise UnexpectedResponseCodeError(expected, resp)
