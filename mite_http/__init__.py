import asyncio
import logging
import time
from collections import deque
from contextlib import asynccontextmanager
from functools import wraps

# from aiohttp import ClientSession
from blacksheep.client import ClientSession

logger = logging.getLogger(__name__)


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
        start_time = time.time()

        response = await super().send(request)


        # breakpoint()

        response.url = request.url
        response.method = request.method
        response.status_code = response.status
        response.start_time = start_time

        self._response_callback(response)


        return response

    # aiohttp
    async def _request(self, method: str, str_or_url, **kwargs):
        start_time = time.time()
        response = await super()._request(method, str_or_url, **kwargs)
        self._response_callback(response)

        return response

class SessionPool:
    """No longer actually goes pooling as this is built into acurl. API just left in place.
    Will need a refactor"""

    # A memoization cache for instances of this class per event loop
    _session_pools = {}

    def __init__(self, use_new_acurl_implementation=False):

        self._wrapper = CAClientSession()
        # if use_new_acurl_implementation:
        # import acurl_ng

        # self._wrapper = acurl_ng.CurlWrapper(asyncio.get_event_loop())
        # else:
        #     import acurl

        #     self._wrapper = acurl.EventLoop()
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
                use_new_acurl_implementation = ctx.config.get(
                    "enable_new_acurl_implementation", False
                )
                instance = cls(use_new_acurl_implementation)
                cls._session_pools[loop] = instance
            async with instance.session_context(ctx):
                return await func(ctx, *args, **kwargs)

        return wrapper

    async def _checkout(self, context):
        session = self._wrapper # .session()
        # session = self._wrapper.session()
        session_wrapper = AcurlSessionWrapper(session)

        def response_callback(r):
            if session_wrapper._response_callback is not None:
                session_wrapper._response_callback(r, session_wrapper.additional_metrics)

            context.send(
                "http_metrics",
                start_time=r.start_time,
                effective_url=str(r.url),
                # response_code=r.status,
                response_code=r.status_code,
                # dns_time=r.namelookup_time,
                # connect_time=r.connect_time,
                # tls_time=r.appconnect_time,
                # transfer_start_time=r.pretransfer_time,
                # first_byte_time=r.starttransfer_time,
                total_time=0.2,
                # primary_ip=r.primary_ip,
                method=r.method,
                # method=r.request.method,
                **session_wrapper.additional_metrics,
            )

        session.set_response_callback(response_callback)
        return session_wrapper

    async def _checkin(self, session):
        pass


def mite_http(func):
    return SessionPool.decorator(func)
