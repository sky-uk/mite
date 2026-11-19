"""Compatibility with mite's old acurl fork.

httpperf's API differs from the fork's in a few places. Everything here exists
only to keep journeys written against the fork working unchanged: argument
translation, the response wrappers (to_curl() and .cookies as the session jar),
the AcurlError alias and create_http_cookie().
"""

import shlex
from collections.abc import Mapping
from urllib.parse import urlparse

import httpperf

# The old acurl fork raised AcurlError for failed transfers
AcurlError = httpperf.RequestError


def adapt_request_kwargs(kwargs):
    """Translate request arguments from the old acurl fork's API to httpperf's."""
    headers = kwargs.get("headers")
    if headers is not None and not isinstance(headers, Mapping):
        # The old fork accepted any dict() input, e.g. a list of (name, value) pairs
        kwargs["headers"] = headers = dict(headers)
    if (
        isinstance(kwargs.get("data"), (str, bytes, bytearray))
        and kwargs.get("json") is None
        and kwargs.get("files") is None
        and not any(name.lower() == "content-type" for name in headers or ())
        and not any(
            line.partition(":")[0].strip().lower() == "content-type"
            for line in kwargs.get("headers_list") or ()
        )
    ):
        # The old fork let curl add its default form Content-Type to str/bytes
        # bodies; httpperf sends none
        kwargs["headers"] = {**(headers or {}), "Content-Type": "application/x-www-form-urlencoded"}
    cert = kwargs.get("cert")
    if cert is not None:
        # The old fork took (keyfile, certfile); upstream takes (certfile, keyfile)
        kwargs["cert"] = (cert[1], cert[0])
    cookies = kwargs.get("cookies")
    if cookies and any(isinstance(v, httpperf.Cookie) for v in cookies.values()):
        # The old fork accepted Cookie objects as values of the cookies dict;
        # upstream only takes strings there, and Cookie objects in cookie_list
        cookie_list = list(kwargs.get("cookie_list") or ())
        plain = {}
        for name, value in cookies.items():
            if isinstance(value, httpperf.Cookie):
                cookie_list.append(value)
            else:
                plain[name] = value
        kwargs["cookies"] = plain or None
        kwargs["cookie_list"] = cookie_list
    return kwargs


class RequestWrapper:
    """An httpperf Request, plus to_curl() as the old acurl fork's Request had."""

    __slots__ = ("_response",)

    def __init__(self, response):
        self._response = response

    def __getattr__(self, name):
        return getattr(self._response._response.request, name)

    def __repr__(self):
        return repr(self._response._response.request)

    def to_curl(self):
        return to_curl(self._response)


class ResponseWrapper:
    """An httpperf Response, with the old acurl fork's behaviour where it differs:
    .request has to_curl(), and .cookies is the session's whole cookie jar. Every
    other attribute is the httpperf Response's own."""

    __slots__ = ("_response", "_session")

    def __init__(self, response, session):
        self._response = response
        self._session = session

    def __getattr__(self, name):
        return getattr(self._response, name)

    def __repr__(self):
        return repr(self._response)

    @property
    def request(self):
        return RequestWrapper(self)

    @property
    def cookies(self):
        # httpperf's Response.cookies is only the cookies this response set; the
        # old fork returned the session's jar. Empty once the journey has ended.
        return self._session.cookies()

    @property
    def history(self):
        return [ResponseWrapper(r, self._session) for r in self._response.history]


def create_http_cookie(ctx, domain, name, value):
    """Build a session cookie for `domain`, to pass in cookie_list=[...] (or as a
    value in cookies={...}). Same defaults the old acurl fork used."""
    return httpperf.Cookie(
        http_only=False,
        domain=domain,
        include_subdomains=True,
        path="/",
        is_secure=False,
        expiration=0,
        name=name,
        value=value,
    )


def _cookie_matches(cookie, host, path, secure):
    domain = cookie.domain.lower()
    if domain.startswith("."):
        domain = domain[1:]
    if cookie.include_subdomains:
        if host != domain and not host.endswith("." + domain):
            return False
    elif host != domain:
        return False
    cookie_path = cookie.path or "/"
    if not (path == cookie_path or path.startswith(cookie_path.rstrip("/") + "/")):
        return False
    return secure or not cookie.is_secure


def to_curl(response):
    """Return a curl command line that repeats the request behind `response`.

    Includes the method, URL, headers, body, basic auth, and the cookies that
    would have been sent: those passed to the request plus those in the session's
    cookie jar for the URL. `response` is one returned by ctx.http (or passed to a
    response callback). The jar is read when this is called, so call it while the
    journey is running; once the journey has ended only the request's own cookies
    are included.
    """
    jar = response._session.get_cookie_list() if isinstance(response, ResponseWrapper) else []
    request = response.request
    parts = ["curl", "-X", request.method]
    data = request.data
    if data is not None:
        if isinstance(data, (bytes, bytearray)):
            data = bytes(data).decode("utf-8", errors="replace")
        parts += ["--data-raw", shlex.quote(data)]
    for header in request.header_list or ():
        parts += ["-H", shlex.quote(header)]

    parsed = urlparse(request.url)
    host = (parsed.hostname or "").lower()
    path = parsed.path or "/"
    secure = parsed.scheme == "https"
    cookies = {}
    for cookie in jar + list(request.cookie_list or ()):
        if not cookie.has_expired and _cookie_matches(cookie, host, path, secure):
            cookies[cookie.name] = cookie.value
    if cookies:
        parts += ["--cookie", shlex.quote("; ".join(f"{k}={v}" for k, v in cookies.items()))]

    if request.auth is not None:
        parts += ["--user", shlex.quote(f"{request.auth[0]}:{request.auth[1]}")]
    parts.append(shlex.quote(request.url))
    return " ".join(parts)
