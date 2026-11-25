"""HTTP response status checks that raise ``MiteError`` on mismatch.

Plain ``if``/``raise`` is used throughout so checks still run under ``python -O``.
"""

from collections.abc import Callable, Iterable

from mite.exceptions import MiteError

__all__ = [
    "UnexpectedResponseCodeError",
    "check_status_code",
    "check_status_code_in_groups",
    "is_error_status_code",
]

OnFailure = Callable[[object], None]


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


def is_error_status_code(status_code: int | Iterable[int]) -> bool:
    """Return True if the status code (or any code in an iterable) is 4xx or 5xx."""
    if isinstance(status_code, int):
        return status_code >= 400
    return any(s >= 400 for s in status_code)


def check_status_code(
    resp, expected: int | Iterable[int], *, on_failure: OnFailure | None = None
) -> None:
    """Raise ``UnexpectedResponseCodeError`` unless ``resp.status_code`` matches exactly.

    ``expected`` is an int, or an iterable of ints for any-of matching.
    ``on_failure(resp)`` is called before raising, e.g. for logging.
    """
    if isinstance(expected, int):
        matched = resp.status_code == expected
    elif isinstance(expected, Iterable) and not isinstance(expected, (str, bytes)):
        expected = list(expected)
        matched = resp.status_code in expected
    else:
        raise ValueError(f"Unknown type of expected: {type(expected)}")
    if not matched:
        if on_failure is not None:
            on_failure(resp)
        raise UnexpectedResponseCodeError(expected, resp)


def check_status_code_in_groups(
    resp, *groups: int, on_failure: OnFailure | None = None
) -> None:
    """Raise unless the status code's hundreds digit matches one of ``groups``.

    Groups are representative codes, e.g. 200 for 2xx, 400 for 4xx.
    """
    if int(resp.status_code) // 100 not in {g // 100 for g in groups}:
        if on_failure is not None:
            on_failure(resp)
        raise UnexpectedResponseCodeError(
            ", ".join(f"{str(g)[0]}**" for g in groups), resp
        )
