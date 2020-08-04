import asyncio
import logging
from collections import deque
from contextlib import asynccontextmanager

from acurl import EventLoop

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _session_pool_context_manager(session_pool, context):
    context.http = await session_pool._checkout(context)
    yield
    await session_pool._checkin(context.http)
    del context.http


class SessionPool:
    """No longer actually goes pooling as this is built into acurl. API just left in place.
    Will need a refactor"""

    # A memoization cache for instances of this class per event loop
    _session_pools = {}

    def __init__(self):
        self._el = EventLoop()
        self._pool = deque()

    def session_context(self, context):
        return _session_pool_context_manager(self, context)

    @classmethod
    def decorator(cls, func):
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
        session = self._el.session()
        session.additional_metrics = {}

        def response_callback(r):
            additional_metrics = session.additional_metrics
            session.additional_metrics = {}

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


def mite_http(func):
    return SessionPool.decorator(func)
