import os

from mite.scenario import StopVolumeModel
from mite_http import mite_http


def volume_model_factory(n):
    def vm(start, end):
        if start > 60 * 15:  # Will run for 15 mins
            raise StopVolumeModel
        return n

    vm.__name__ = f"volume model {n}"
    return vm


# Mock Server
_API_URL = os.environ.get("API_URL", "http://localhost:8000/")


@mite_http
async def demo_req(ctx):
    async with ctx.transaction("Get request"):
        await ctx.http.get(_API_URL)


# volumemodel = lambda start, end: 10  # alternate way to define volume model


def scenario():
    return [
        ["local.demo:demo_req", None, volume_model_factory(2)],
    ]
