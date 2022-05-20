
import asyncio
from mite_http import mite_http
from mite import ensure_fixed_separation

@mite_http
async def journey(ctx):
    async with ctx.transaction('test1'):
        async with ensure_fixed_separation(1):
            ctx.send("test_message")
            await asyncio.sleep(0.5)
            resp = await ctx.http.get('http://example.com')
            breakpoint()

        return resp


volumemodel = lambda start, end: 10


def scenario():
    return [
        ['mite.example:journey', None, volumemodel],
    ]
