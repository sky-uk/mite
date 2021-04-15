import asyncio
import os
import sys

from . import FinagleMessageFactory, mite_finagle

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "gen_py"))

from tenancies.ttypes import ServiceType, TenancyRequest, TenancyResponse  # noqa: E402

msg_factory = FinagleMessageFactory("lookup", TenancyRequest, TenancyResponse)


@mite_finagle
async def journey(ctx):
    async with ctx.finagle.connect("127.0.0.1", 5000) as finagle:
        for _ in range(10):
            await finagle.send(msg_factory, ServiceType.SHARED, "foo")
        async for reply in finagle.replies():
            print("got reply")
            await reply.chained_wait(1)
            print("done waiting")
            await finagle.send(msg_factory, ServiceType.SHARED, "foo")


if __name__ == "__main__":
    # asyncio.run(run())
    pass
