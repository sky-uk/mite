import asyncio
import logging
import os
import time
import types
from collections import deque
from contextlib import asynccontextmanager
from functools import wraps

from mem_info import Meminfo

logger = logging.getLogger(__name__)

if os.environ.get("MITE_CONF_http_library") == "aiohttp":
    from aiohttp import ClientSession
elif os.environ.get("MITE_CONF_http_library") == "blacksheep":
    from blacksheep.client import ClientSession
else: # to silence an error
    from aiohttp import ClientSession

class AcurlSessionWrapper:
    def __init__(self, session):
        self.__session = session
        self.__callback = None
        self.additional_metrics = {}

    def __getattr__(self, attrname):
        try:
            r = object.__getattr__(self, attrname)
            return r
        except AttributeError:
            pass
        return getattr(self.__session, attrname)

    def set_response_callback(self, cb):
        self.__callback = cb

    @property
    def _response_callback(self):
        return self.__callback

class CAClientSession(ClientSession):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def set_response_callback(self, callback):
        self._response_callback = callback

    # blacksheep
    async def send(self, request):
        logger.info("BLACKSHEEP REQUEST")
        start_time = time.time()

        response = await super().send(request)

        end_time = time.time()

        response.url = request.url
        response.request = FakeRequest(request.method, request.url, (), (), None, None, None, None)
        response.start_time = start_time
        response.status_code = response.status
        response.total_time = end_time - start_time

        self._response_callback(response)

        return response

    # aiohttp
    async def _request(self, method: str, str_or_url, **kwargs):
        logger.info("AIOHTTP REQUEST")
        start_time = time.time()

        response = await super()._request(method, str_or_url, **kwargs)

        end_time = time.time()

        response.request = FakeRequest(method, str_or_url, (), (), None, None, None, None)
        response.start_time = start_time
        response.status_code = response.status
        response.total_time = end_time - start_time

        self._response_callback(response)

        return response

class Wrapper:
    def __init__(self, session):
        self._session = session

    def session(self):
        return self._session

class SessionPool:
    """No longer actually goes pooling as this is built into acurl. API just left in place.
    Will need a refactor"""

    # A memoization cache for instances of this class per event loop
    _session_pools = {}

    def __init__(self, http_library):
        self.meminfo = Meminfo()

        if http_library in ("aiohttp", "blacksheep"):
            # aiohttp / blacksheep
            self._wrapper = Wrapper(CAClientSession())
        elif http_library == "acurl_ng":
            import acurl_ng
            self._wrapper = acurl_ng.CurlWrapper(asyncio.get_event_loop())
        elif http_library == "acurl":
            import acurl
            self._wrapper = acurl.EventLoop()

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
                http_library = ctx.config.get(
                    "http_library", "acurl"
                )
                instance = cls(http_library)
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
                effective_url=str(r.url),
                response_code=r.status_code,
                # dns_time=r.namelookup_time,
                # connect_time=r.connect_time,
                # tls_time=r.appconnect_time,
                # transfer_start_time=r.pretransfer_time,
                # first_byte_time=r.starttransfer_time,
                total_time=r.total_time,
                # primary_ip=r.primary_ip,
                method=r.request.method,
                **session_wrapper.additional_metrics,
            )

            self.meminfo.stats()

        session.set_response_callback(response_callback)
        return session_wrapper

    async def _checkin(self, session):
        pass


def mite_http(func):
    return SessionPool.decorator(func)



class FakeRequest:
    def __init__(self, method, url, header_seq, cookie_seq, auth, data, cert, session):
        self._method = method
        self._url = url
        self._header_seq = tuple(header_seq)
        self._cookie_tuple = tuple(cookie_seq)
        self._auth = auth
        self._data = data
        self._cert = cert
        self._session_cookies = "tbc"

    @property
    def method(self):
        return self._method

    @property
    def url(self):
        return self._url

    @property
    def headers(self):
        return dict(header.split(": ", 1) for header in self._header_seq)

    @property
    def cookies(self):
        return "tbc"

    @property
    def auth(self):
        return self._auth

    @property
    def data(self):
        return self._data

    @property
    def cert(self):
        return self._cert

    def to_curl(self):
        return "tbc"
