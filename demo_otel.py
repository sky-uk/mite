from mite_http import mite_http
from mite import ensure_average_separation

import mite.otel

@mite_http
async def demo_req(ctx):
    async with ensure_average_separation(1):
        async with ctx.transaction("Get request"):
            await ctx.http.get("https://example.com/")

scenario = lambda: [("demo_otel:demo_req", None, lambda s, e: 2)]