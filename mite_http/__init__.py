import asyncio
import logging
import json
import shlex
from collections import deque
from contextlib import asynccontextmanager, suppress
from functools import wraps

from aiohttp import ClientSession

from .aiohttp_trace import request_tracer, ResultsCollector

import mite


logger = logging.getLogger(__name__)


class CAClientSession(ClientSession):
    headers = {
        "User-Agent": f"Mite {mite.__version__}",
    }

    def __init__(self, **kwargs):
        super().__init__(headers=self.headers, **kwargs)

    def set_response_callback(self, callback):
        self._response_callback = callback

    async def to_curl(self, request, **kwargs):
        # Get the request method, URL, headers and body
        method = request.method.upper()
        url = str(request.url)
        headers = request.headers

        # Generate the curl command string
        curl_command = f"curl -X {method} '{url}'"
        for key, value in headers.items():
            curl_command += f" -H '{key}: {value}'"

        if kwargs.get("json"):
            curl_command += f" -d '{json.dumps(kwargs.get('json'))}'"
        if kwargs.get("data"):
            curl_command += f" -d {shlex.quote(kwargs.get('data').decode('utf-8'))}"

        return curl_command

    async def _request(self, method: str, str_or_url, **kwargs):
        response = await super()._request(method, str_or_url, **kwargs)
        self._response_callback(response)

        response.curl = await self.to_curl(response.request_info, **kwargs)

        return response


class Wrapper:
    def __init__(self, session):
        self._session = session

    def session(self):
        return self._session


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
        self.trace = ResultsCollector()

        self._wrapper = Wrapper(CAClientSession(trace_configs=[request_tracer(self.trace)]))
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
        trace = self.trace

        def response_callback(r):
            if session_wrapper._response_callback is not None:
                session_wrapper._response_callback(r, session_wrapper.additional_metrics)

            context.send(
                "http_metrics",
                # start_time=r.start_time,
                effective_url=str(r.url),
                response_code=r.status,
                dns_time=trace.dns_lookup_and_dial,
                connect_time=trace.connect,
                # tls_time=r.appconnect_time,
                # transfer_start_time=r.pretransfer_time,
                first_byte_time=trace.first_byte,
                total_time=trace.total,
                # primary_ip=r.primary_ip,
                method=r.request_info.method,
                **session_wrapper.additional_metrics,
            )

        session.set_response_callback(response_callback)
        return session_wrapper

    async def _checkin(self, session):
        pass


def mite_http(func):
    return SessionPool.decorator(func)


# [TODO]
# def create_http_cookie(ctx, *args, **kwargs):
#     return acurl.Cookie(*args, **kwargs)
