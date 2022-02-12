import time

from mite_http import mite_http

# Mock Server
_API_URL = "http://apiserver:8000/"  # apiserver is for docker-compose. Change this to http://localhost:8000/ for local testing
# TODO make http://apiserver:8000/ env var for controller and runners and default _API_URL to localhost


@mite_http
async def get_req(ctx):
    async with ctx.transaction("Get request"):
        await ctx.http.get(_API_URL)


volumemodel = lambda start, end: 10


def scenario():
    return [
        ["local.demo:get_req", None, volumemodel],
    ]
