import asyncio
import json
import logging
import shlex
from collections import deque
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from functools import wraps
from http.cookies import SimpleCookie
from io import StringIO
from typing import Any, Callable, Dict, Optional, Tuple

import attr
from aiohttp import BasicAuth, ClientSession, RequestInfo
from multidict import CIMultiDictProxy
from yarl import URL

import mite
from mite_http.aiohttp_trace import ResultsCollector, request_tracer

logger = logging.getLogger(__name__)


@dataclass
class Request:
    url: URL
    method: str
    headers: Dict
    real_url: URL = attr.ib()
    to_curl: Callable[[], str] = None


@dataclass
class Response:
    # content
    content_length: int
    content_type: str
    cookies: SimpleCookie
    # encoding: str
    headers: Dict
    aiohttp_headers: CIMultiDictProxy
    history: Tuple
    host: str
    links: Dict
    method: str
    ok: bool
    raise_for_status: Callable
    raw_headers: Tuple
    read: Callable
    real_url: URL
    reason: str
    status_code: int
    text: str
    url: URL
    json: Optional[Callable] = None
    request: Request = None
    total_time: float = 0.0


class CAClientSession(ClientSession):
    headers = {
        "User-Agent": f"Mite {mite.__version__}",
    }

    def __init__(self, **kwargs):
        super().__init__(headers=self.headers, **kwargs)

    def set_response_callback(self, callback):
        self._response_callback = callback

    def to_curl(self, request: RequestInfo, **kwargs):
        # [TODO] add cookies

        # Get the request method, URL, headers and body
        method = request.method.upper()
        url = str(request.url)
        headers = request.headers

        # Generate the curl command string using StringIO
        with StringIO() as curl_command:
            curl_command.write(f"curl -X {method} '{url}'")
            for key, value in headers.items():
                curl_command.write(f" -H '{key}: {value}'")

            if json_data := kwargs.get("json"):
                curl_command.write(f" -d '{json.dumps(json_data)}'")
            elif data := kwargs.get("data"):
                if isinstance(data, str):
                    curl_command.write(f" -d {shlex.quote(data)}")
                elif isinstance(data, dict):
                    curl_command.write(f" -d {shlex.quote(str(data))}")
                else:
                    curl_command.write(f" -d {shlex.quote(data.decode('utf-8'))}")

            if auth := kwargs.get("auth"):
                user_login = shlex.quote(f"{auth[0]}:{auth[1]}")
                curl_command.write(f" --user {user_login}")

            return curl_command.getvalue()

    async def _request(self, method: str, str_or_url, **kwargs):
        def curl():
            # bit of a hack to maintain backwards compatability
            return self.to_curl(_response.request_info, **kwargs)

        def json():
            # see above
            return json_data

        if kwargs.get("auth") and kwargs.get("headers", dict()).get("Authorization"):
            # https://github.com/aio-libs/aiohttp/blob/master/aiohttp/client.py#L434
            del kwargs["auth"]

        if kwargs.get("auth"):
            kwargs["auth"] = BasicAuth(*kwargs["auth"])

        # `version` isn't a parameter for the aiohttp `_request` method
        if kwargs.get("version"):
            del kwargs["version"]

        _response = await super()._request(method, str_or_url, **kwargs)

        response = Response(
            content_length=_response.content_length,
            content_type=_response.content_type,
            cookies=_response.cookies,
            # encoding=_response.get_encoding(),
            headers=dict(_response.headers),
            aiohttp_headers=_response.headers,
            history=_response.history,
            host=_response.host,
            links=_response.links,
            method=_response.method,
            ok=_response.ok,
            raise_for_status=_response.raise_for_status,
            raw_headers=_response.raw_headers,
            read=_response.read,
            real_url=_response.real_url,
            reason=_response.reason,
            status_code=_response.status,
            text=await _response.text(),
            url=_response.url,
        )

        if "json" in response.content_type:
            json_data = await _response.json()
            response.json = json

        response.request = Request(
            url=_response.request_info.url,
            method=_response.request_info.method,
            headers=dict(_response.request_info.headers),
            real_url=_response.request_info.real_url,
            to_curl=curl,  # bit of a hack to maintain backwards compatability
        )

        self._response_callback(response)

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

        self._wrapper = Wrapper(
            CAClientSession(trace_configs=[request_tracer(self.trace)])
        )
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

            r.total_time = trace.total

            context.send(
                "http_metrics",
                start_time=trace.start_time,
                effective_url=str(r.url),
                response_code=r.status_code,
                dns_time=trace.dns_lookup_and_dial,
                connect_time=trace.connect,
                # tls_time=r.appconnect_time,
                transfer_start_time=trace.transfer_start_time,
                first_byte_time=trace.first_byte,
                total_time=trace.total,
                # primary_ip=r.primary_ip,
                method=r.method,
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
