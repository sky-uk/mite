from mite_http import mite_http
from mite.scenario import StopScenario


def volume_model_factory(n):
    def vm(start, end):
        if start > 60 * 15: # Will run for 15 mins
            raise StopScenario
        return n
    vm.__name__ = f"volume model {n}"
    return vm

# Mock Server
_API_URL = "http://apiserver:8000/"  # apiserver is for docker-compose. Change this to http://localhost:8000/ for local testing
# TODO make http://apiserver:8000/ env var for controller and runners and default _API_URL to localhost


@mite_http
async def demo_req(ctx):
    async with ctx.transaction("Get request"):
        await ctx.http.get(_API_URL)


volumemodel = lambda start, end: 10


def scenario():
    return [
        ["local.demo:demo_req", None, volume_model_factory(10)],
    ]
