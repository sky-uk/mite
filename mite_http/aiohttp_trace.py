from dataclasses import dataclass

import aiohttp


@dataclass
class ResultsCollector:
    dns_lookup_and_dial: float = 0
    connect: float = 0
    first_byte: float = 0
    transfer: float = 0
    total: float = 0
    is_redirect: bool = False


def request_tracer(results_collector):

    async def on_request_start(session, context, params):
        context.on_request_start = session.loop.time()
        context.is_redirect = False

    async def on_connection_create_start(session, context, params):
        since_start = session.loop.time() - context.on_request_start
        context.on_connection_create_start = since_start

    async def on_request_redirect(session, context, params):
        since_start = session.loop.time() - context.on_request_start
        context.on_request_redirect = since_start
        context.is_redirect = True

    async def on_dns_resolvehost_start(session, context, params):
        since_start = session.loop.time() - context.on_request_start
        context.on_dns_resolvehost_start = since_start

    async def on_dns_resolvehost_end(session, context, params):
        since_start = session.loop.time() - context.on_request_start
        context.on_dns_resolvehost_end = since_start

    async def on_connection_create_end(session, context, params):
        since_start = session.loop.time() - context.on_request_start
        context.on_connection_create_end = since_start

    async def on_request_chunk_sent(session, context, params):
        since_start = session.loop.time() - context.on_request_start
        context.on_request_chunk_sent = since_start

    async def on_request_end(session, context, params):
        total = session.loop.time() - context.on_request_start
        context.on_request_end = total

        breakpoint()

        if hasattr(context, "on_dns_resolvehost_end"):
            dns_lookup_and_dial = context.on_dns_resolvehost_end - context.on_dns_resolvehost_start
        else:
            dns_lookup_and_dial = 0

        if hasattr(context, "on_connection_create_end"):
            connect = context.on_connection_create_end - dns_lookup_and_dial
        else:
            connect = 0

        transfer = total - connect
        is_redirect = context.is_redirect

        results_collector.dns_lookup_and_dial = round(dns_lookup_and_dial * 1000, 2)
        results_collector.connect = round(connect * 1000, 2)
        results_collector.first_byte = context.on_connection_create_end
        results_collector.transfer = round(transfer * 1000, 2)
        results_collector.total = round(total * 1000, 2)
        results_collector.is_redirect = is_redirect

    trace_config = aiohttp.TraceConfig()

    trace_config.on_request_start.append(on_request_start)
    trace_config.on_request_redirect.append(on_request_redirect)
    trace_config.on_dns_resolvehost_start.append(on_dns_resolvehost_start)
    trace_config.on_dns_resolvehost_end.append(on_dns_resolvehost_end)
    trace_config.on_connection_create_start.append(on_connection_create_start)
    trace_config.on_connection_create_end.append(on_connection_create_end)
    trace_config.on_request_end.append(on_request_end)
    trace_config.on_request_chunk_sent.append(on_request_chunk_sent)

    return trace_config
