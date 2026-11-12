import asyncio
import logging
import warnings
from contextlib import asynccontextmanager, suppress
from functools import wraps

import acurl

warnings.warn(
    "mite_http will require 'pip install mite[http]' starting in mite 3.0; "
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
# (config key, acurl Engine argument, converter, default)
_ENGINE_OPTIONS = (
    ("http_max_host_connections", "max_host_connections", int, 0),
    ("http_max_total_connections", "max_total_connections", int, 0),
    ("http_max_idle_connections", "max_idle_connections", int, 1000),
)

# (config key, acurl Session argument, converter, default)
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


# The old acurl fork raised AcurlError for failed transfers
AcurlError = acurl.RequestError


def _adapt_request_kwargs(kwargs):
    """Translate request arguments from the old acurl fork's API to upstream's."""
    cert = kwargs.get("cert")
    if cert is not None:
        # The old fork took (keyfile, certfile); upstream takes (certfile, keyfile)
        kwargs["cert"] = (cert[1], cert[0])
    cookies = kwargs.get("cookies")
    if cookies and any(isinstance(v, acurl.Cookie) for v in cookies.values()):
        # The old fork accepted Cookie objects as values of the cookies dict;
        # upstream only takes strings there, and Cookie objects in cookie_list
        cookie_list = list(kwargs.get("cookie_list") or ())
        plain = {}
        for name, value in cookies.items():
            if isinstance(value, acurl.Cookie):
                cookie_list.append(value)
            else:
                plain[name] = value
        kwargs["cookies"] = plain or None
        kwargs["cookie_list"] = cookie_list
    return kwargs


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
        return await self.__session.request(method, url, **_adapt_request_kwargs(kwargs))

    async def get(self, url, **kwargs):
        return await self.__session.get(url, **_adapt_request_kwargs(kwargs))

    async def post(self, url, **kwargs):
        return await self.__session.post(url, **_adapt_request_kwargs(kwargs))

    async def put(self, url, **kwargs):
        return await self.__session.put(url, **_adapt_request_kwargs(kwargs))

    async def patch(self, url, **kwargs):
        return await self.__session.patch(url, **_adapt_request_kwargs(kwargs))

    async def delete(self, url, **kwargs):
        return await self.__session.delete(url, **_adapt_request_kwargs(kwargs))

    async def head(self, url, **kwargs):
        return await self.__session.head(url, **_adapt_request_kwargs(kwargs))

    async def options(self, url, **kwargs):
        return await self.__session.options(url, **_adapt_request_kwargs(kwargs))

    @property
    def _response_callback(self):
        return self.__callback


class SessionPool:
    """Holds one acurl Engine per event loop and gives each journey its own Session.

    Connection pooling is done by acurl, according to the http_* config options.
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
            self._engine = acurl.Engine(**_options_from_config(context.config, _ENGINE_OPTIONS))
        session = acurl.Session(
            engine=self._engine, **_options_from_config(context.config, _SESSION_OPTIONS)
        )
        session_wrapper = AcurlSessionWrapper(session)

        def response_callback(r):
            if session_wrapper._response_callback is not None:
                session_wrapper._response_callback(r, session_wrapper.additional_metrics)

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
                **session_wrapper.additional_metrics,
            )

        session.set_response_callback(response_callback)
        return session_wrapper

    async def _checkin(self, session):
        session.close()


def mite_http(func):
    return SessionPool.decorator(func)


def create_http_cookie(ctx, *args, **kwargs):
    return acurl.Cookie(*args, **kwargs)
