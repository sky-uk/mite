import asyncio
import logging
from collections import deque

from acurl import EventLoop
from mite.stats import Counter, Histogram, extractor, matcher_by_type

logger = logging.getLogger(__name__)


_MITE_STATS = (
    Counter(
        name='mite_http_response_total',
        matcher=matcher_by_type('http_curl_metrics'),
        extractor=extractor('test journey transaction method response_code'.split()),
    ),
    Histogram(
        name='mite_http_response_time_seconds',
        matcher=matcher_by_type('http_curl_metrics'),
        extractor=extractor(['transaction'], 'total_time'),
        bins=[0.0001, 0.001, 0.01, 0.05, 0.1, 0.2, 0.4, 0.8, 1, 2, 4, 8, 16, 32, 64],
    ),
)


class _SessionPoolContextManager:
    def __init__(self, session_pool, context):
        self._session_pool = session_pool
        self._context = context

    async def __aenter__(self):
        self._context.http = await self._session_pool._checkout(self._context)

    async def __aexit__(self, *args):
        await self._session_pool._checkin(self._context.http)
        del self._context.http


class SessionPool:
    """No longer actually goes pooling as this is built into acurl. API just left in place.
    Will need a refactor"""

    def __init__(self):
        self._el = EventLoop()
        self._pool = deque()

    def session_context(self, context):
        return _SessionPoolContextManager(self, context)

    def decorator(self, func):
        async def wrapper(ctx, *args, **kwargs):
            async with self.session_context(ctx):
                return await func(ctx, *args, **kwargs)

        return wrapper

    async def _checkout(self, context):
        session = self._el.session()

        def response_callback(r):
            additional_metrics = getattr(context, "additional_http_metrics", {})
            delattr(context, "additional_http_metrics")
            context.send(
                'http_metrics',
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
                **additional_metrics,
            )

        session.set_response_callback(response_callback)
        return session

    async def _checkin(self, session):
        pass


def get_session_pool():
    # We memoize the function by event loop.  This is because, in unit tests,
    # there are multiple event loops in circulation.
    try:
        return get_session_pool._session_pools[asyncio.get_event_loop()]
    except KeyError:
        sp = SessionPool()
        get_session_pool._session_pools[asyncio.get_event_loop()] = sp
        return sp


get_session_pool._session_pools = {}  # noqa: E305


def mite_http(func):
    return get_session_pool().decorator(func)
