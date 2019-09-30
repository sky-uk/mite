from mite.scenario import StopScenario
from mite_http import mite_http


def volume_model_factory(n):
    def vm(start, end):
        if start > 60 * 1:
            raise StopScenario
        return n

    vm.__name__ = f"volume model {n}"
    return vm


@mite_http
async def journey(ctx):
    async with ctx.transaction("test"):
        await ctx.http.get("http://localhost:9898/")


def scenario():
    return (("scenarios:journey", None, volume_model_factory(1)),)
