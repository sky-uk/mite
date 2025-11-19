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

    def __init__(self, max_connects=None):
        # Allow programmatic configuration of max connections
        # If not provided, uses acurl's default (100)
        if max_connects is not None:
            self._wrapper = acurl.CurlWrapper(asyncio.get_event_loop(), max_connects)
        else:
            self._wrapper = acurl.CurlWrapper(asyncio.get_event_loop())
        self._pool = deque()

    @asynccontextmanager
    async def session_context(self, context):
        context.http = await self._checkout(context)
        yield
        await self._checkin(context.http)
        del context.http

    @classmethod
    def decorator(cls, func=None, max_connects=None):
        """
        Decorator to inject HTTP session into context.
        
        Can be used as:
            @mite_http
            def my_journey(ctx): ...
            
        Or with custom max_connects:
            @mite_http(max_connects=50)
            def my_journey(ctx): ...
        """
        def decorator_wrapper(f):
            @wraps(f)
            async def wrapper(ctx, *args, **kwargs):
                loop = asyncio.get_event_loop()
                try:
                    instance = cls._session_pools[loop]
                except KeyError:
                    instance = cls(max_connects=max_connects)
                    cls._session_pools[loop] = instance
                async with instance.session_context(ctx):
                    return await f(ctx, *args, **kwargs)

            return wrapper
        
        # Support both @mite_http and @mite_http(max_connects=50)
        if func is not None:
            return decorator_wrapper(func)
        return decorator_wrapper

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
                download_size=r.download_size,
                **session_wrapper.additional_metrics,
            )

        session.set_response_callback(response_callback)
        return session_wrapper

    async def _checkin(self, session):
        pass


def mite_http(func=None, max_connects=None):
    """
    Decorator to inject HTTP session into mite context.
    
    Usage:
        @mite_http
        async def my_journey(ctx):
            await ctx.http.get("https://example.com")
    
    Or with custom connection pool size:
        @mite_http(max_connects=50)
        async def my_journey(ctx):
            await ctx.http.get("https://example.com")
    
    Args:
        func: The function to decorate (when used without parentheses)
        max_connects: Connection pool/cache size (default: 100)
                     This is NOT a concurrency limit - it's how many idle
                     connections curl keeps alive. Set to at least the number
                     of unique hosts you access, or you'll see performance
                     degradation from constant reconnections.
                     
                     - Few hosts (1-10): max_connects=25-50
                     - Many hosts (10-100): max_connects=100 (default)
                     - Very many hosts (100+): max_connects=200-500
    """
    return SessionPool.decorator(func, max_connects=max_connects)


def create_http_cookie(ctx, *args, **kwargs):
    return acurl.Cookie(*args, **kwargs)
