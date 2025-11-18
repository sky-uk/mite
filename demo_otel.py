from mite.otel import mite_http_traced
from mite import ensure_average_separation

@mite_http_traced
async def demo_req(ctx):
    async with ensure_average_separation(1):
        async with ctx.transaction("Get request"):
            await ctx.http.get("https://example.com/")

scenario = lambda: [("demo_otel:demo_req", None, lambda s, e: 2)]
