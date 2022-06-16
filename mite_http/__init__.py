import asyncio
import logging
from collections import deque
from contextlib import asynccontextmanager, suppress
from functools import wraps

import acurl

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

    @property
    def _response_callback(self):
        return self.__callback


class SessionPool:
    """No longer actually goes pooling as this is built into acurl. API just left in place.
    Will need a refactor"""

    # A memoization cache for instances of this class per event loop
    _session_pools = {}

    def __init__(self):
        self._wrapper = acurl.CurlWrapper(asyncio.get_event_loop())
        self._pool = deque()

    @asynccontextmanager
    async def session_context(self, context):
        context.http = await self._checkout(context)
        yield
        await self._checkin(context.http)
        del context.http

    @classmethod
    def decorator(cls, func):
        @wraps(func)
        async def wrapper(ctx, *args, **kwargs):
            loop = asyncio.get_event_loop()
            try:
                instance = cls._session_pools[loop]
            except KeyError:
                instance = cls()
                cls._session_pools[loop] = instance
            async with instance.session_context(ctx):
                return await func(ctx, *args, **kwargs)

        return wrapper

    async def _checkout(self, context):
        session = self._wrapper.session()
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
                **session_wrapper.additional_metrics,
            )

        session.set_response_callback(response_callback)
        return session_wrapper

    async def _checkin(self, session):
        pass


def mite_http(func):
    return SessionPool.decorator(func)


def create_http_cookie(ctx, *args, **kwargs):
    return acurl.Cookie(*args, **kwargs)
