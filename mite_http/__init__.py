import asyncio
import logging
import warnings
from contextlib import asynccontextmanager, suppress
from functools import wraps

import httpperf

from .compat import (
    AcurlError,
    RequestWrapper,
    ResponseWrapper,
    adapt_request_kwargs,
    create_http_cookie,
    to_curl,
)
from .config import ENGINE_OPTIONS, SESSION_OPTIONS, json_dumps, json_loads, options_from_config

warnings.warn(
    "mite_http will require 'pip install mite[http]' starting in mite 4.0; "
    "no functional change today.",
    FutureWarning,
    stacklevel=2,
)

__all__ = [
    "AcurlError",
    "AcurlSessionWrapper",
    "RequestWrapper",
    "ResponseWrapper",
    "SessionPool",
    "create_http_cookie",
    "mite_http",
    "to_curl",
]

logger = logging.getLogger(__name__)


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
        return ResponseWrapper(await self.__session.request(method, url, **adapt_request_kwargs(kwargs)), self.__session)

    async def get(self, url, **kwargs):
        return ResponseWrapper(await self.__session.get(url, **adapt_request_kwargs(kwargs)), self.__session)

    async def post(self, url, **kwargs):
        return ResponseWrapper(await self.__session.post(url, **adapt_request_kwargs(kwargs)), self.__session)

    async def put(self, url, **kwargs):
        return ResponseWrapper(await self.__session.put(url, **adapt_request_kwargs(kwargs)), self.__session)

    async def patch(self, url, **kwargs):
        return ResponseWrapper(await self.__session.patch(url, **adapt_request_kwargs(kwargs)), self.__session)

    async def delete(self, url, **kwargs):
        return ResponseWrapper(await self.__session.delete(url, **adapt_request_kwargs(kwargs)), self.__session)

    async def head(self, url, **kwargs):
        # The old acurl fork followed redirects for HEAD too; httpperf doesn't by default
        kwargs.setdefault("allow_redirects", True)
        return ResponseWrapper(await self.__session.head(url, **adapt_request_kwargs(kwargs)), self.__session)

    async def options(self, url, **kwargs):
        return ResponseWrapper(await self.__session.options(url, **adapt_request_kwargs(kwargs)), self.__session)

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
                json_dumps=json_dumps,
                json_loads=json_loads,
                **options_from_config(context.config, ENGINE_OPTIONS),
            )
        session = httpperf.Session(
            engine=self._engine, **options_from_config(context.config, SESSION_OPTIONS)
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
