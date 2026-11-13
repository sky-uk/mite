import asyncio
import logging
import shlex
import warnings
from collections.abc import Mapping
from contextlib import asynccontextmanager, suppress
from functools import wraps
from urllib.parse import urlparse

import httpperf
import ujson

warnings.warn(
    "mite_http will require 'pip install mite[http]' starting in mite 4.0; "
    "no functional change today.",
    FutureWarning,
    stacklevel=2,
)

logger = logging.getLogger(__name__)


def _to_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _to_verify(value):
    # True/False, or a path to a CA bundle
    if isinstance(value, str) and value.strip().lower() in (
        "0", "1", "true", "false", "yes", "no", "on", "off"
    ):
        return _to_bool(value)
    return value


def _to_optional_float(value):
    return None if value in (None, "") else float(value)


# Read from ctx.config (e.g. set as MITE_CONF_http_max_total_connections=100).
# (config key, httpperf Engine argument, converter, default)
_ENGINE_OPTIONS = (
    ("http_max_host_connections", "max_host_connections", int, 0),
    ("http_max_total_connections", "max_total_connections", int, 0),
    ("http_max_idle_connections", "max_idle_connections", int, 1000),
)

# (config key, httpperf Session argument, converter, default)
# The defaults keep the connection behaviour of mite's old acurl fork (one
# shared pool, TLS tickets per session), with HTTP/2 negotiated where offered.
_SESSION_OPTIONS = (
    ("http_connections", "connections", str, "shared"),
    ("http_tls", "tls", str, "session"),
    ("http_version", "http_version", str, "HTTP/2"),
    ("http_idle_timeout", "idle_timeout", int, 118),
    ("http_max_connection_age", "max_connection_age", int, 0),
    ("http_session_max_host_connections", "max_host_connections", int, 0),
    ("http_session_max_connections", "max_connections", int, 0),
    ("http_timeout", "timeout", _to_optional_float, None),
    ("http_connect_timeout", "connect_timeout", _to_optional_float, None),
    ("http_verify", "verify", _to_verify, False),
)


def _options_from_config(config, options):
    result = {}
    for key, argument, convert, default in options:
        value = config.get(key, None)
        result[argument] = default if value is None else convert(value)
    return result


def _json_dumps(obj):
    # Byte-for-byte the same bodies as the old acurl fork's json.dumps(obj): spaces
    # after separators, non-ASCII escaped, and "/" not escaped
    return ujson.dumps(obj, escape_forward_slashes=False, separators=(", ", ": "))


# The old acurl fork raised AcurlError for failed transfers
AcurlError = httpperf.RequestError


def _adapt_request_kwargs(kwargs):
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


class AcurlSessionWrapper:
    def __init__(self, session):
        self.__session = session
        self.__callback = None
        self.additional_metrics = {}

    def __getattr__(self, attrname):
        with suppress(AttributeError):
            return object.__getattr__(self, attrname)
        return getattr(self.__session, attrname)

    def set_response_callback(self, cb):
        self.__callback = cb

    async def request(self, method, url, **kwargs):
        return ResponseWrapper(await self.__session.request(method, url, **_adapt_request_kwargs(kwargs)), self.__session)

    async def get(self, url, **kwargs):
        return ResponseWrapper(await self.__session.get(url, **_adapt_request_kwargs(kwargs)), self.__session)

    async def post(self, url, **kwargs):
        return ResponseWrapper(await self.__session.post(url, **_adapt_request_kwargs(kwargs)), self.__session)

    async def put(self, url, **kwargs):
        return ResponseWrapper(await self.__session.put(url, **_adapt_request_kwargs(kwargs)), self.__session)

    async def patch(self, url, **kwargs):
        return ResponseWrapper(await self.__session.patch(url, **_adapt_request_kwargs(kwargs)), self.__session)

    async def delete(self, url, **kwargs):
        return ResponseWrapper(await self.__session.delete(url, **_adapt_request_kwargs(kwargs)), self.__session)

    async def head(self, url, **kwargs):
        # The old acurl fork followed redirects for HEAD too; httpperf doesn't by default
        kwargs.setdefault("allow_redirects", True)
        return ResponseWrapper(await self.__session.head(url, **_adapt_request_kwargs(kwargs)), self.__session)

    async def options(self, url, **kwargs):
        return ResponseWrapper(await self.__session.options(url, **_adapt_request_kwargs(kwargs)), self.__session)

    @property
    def _response_callback(self):
        return self.__callback


class SessionPool:
    """Holds one httpperf Engine per event loop and gives each journey its own Session.

    Connection pooling is done by httpperf, according to the http_* config options.
    """

    # A memoization cache for instances of this class per event loop
    _session_pools = {}

    def __init__(self):
        self._engine = None

    @asynccontextmanager
    async def session_context(self, context):
        context.http = await self._checkout(context)
        try:
            yield
        finally:
            await self._checkin(context.http)
            del context.http

    @classmethod
    def decorator(cls, func):
        @wraps(func)
        async def wrapper(ctx, *args, **kwargs):
            # Get the current running loop - we're in an async context so this should always work
            loop = asyncio.get_running_loop()
            try:
                instance = cls._session_pools[loop]
            except KeyError:
                instance = cls()
                cls._session_pools[loop] = instance
            async with instance.session_context(ctx):
                return await func(ctx, *args, **kwargs)

        return wrapper

    async def _checkout(self, context):
        if self._engine is None:
            # Engine options are fixed once the engine exists; session options
            # are re-read for every session, so config changes apply to new ones.
            self._engine = httpperf.Engine(
                json_dumps=_json_dumps,
                json_loads=ujson.loads,
                **_options_from_config(context.config, _ENGINE_OPTIONS),
            )
        session = httpperf.Session(
            engine=self._engine, **_options_from_config(context.config, _SESSION_OPTIONS)
        )
        session_wrapper = AcurlSessionWrapper(session)

        def response_callback(r):
            if session_wrapper._response_callback is not None:
                session_wrapper._response_callback(
                    ResponseWrapper(r, session), session_wrapper.additional_metrics
                )

            context.send(
                "http_metrics",
                start_time=r.start_time,
                effective_url=r.url,
                response_code=r.status_code,
                dns_time=r.namelookup_time,
                connect_time=r.connect_time,
                tls_time=r.appconnect_time,
                transfer_start_time=r.pretransfer_time,
                first_byte_time=r.starttransfer_time,
                total_time=r.total_time,
                primary_ip=r.primary_ip,
                method=r.request.method,
                download_size=r.download_size,
                upload_size=r.upload_size,
                queue_time=r.queue_time,
                client_lag=r.client_lag,
                # None with libcurl older than 8.10
                posttransfer_time=r.posttransfer_time,
                http_version=r.http_version,
                **session_wrapper.additional_metrics,
            )

        session.set_response_callback(response_callback)
        return session_wrapper

    async def _checkin(self, session):
        session.close()


def mite_http(func):
    return SessionPool.decorator(func)


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
