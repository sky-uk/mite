from mite.scenario import StopVolumeModel
from mite_http import mite_http


def volume_model_factory(n):
    def vm(start, end):
        if start > 60 * 1:
            raise StopVolumeModel
        return n
    vm.__name__ = f"volume model {n}"
    return vm


@mite_http
async def journey(ctx):
    async with ctx.transaction("test"):
        await ctx.http.get("http://localhost:9898/")


def scenario1():
    return (
        ("mite_perftest:journey", None, volume_model_factory(1)),
    )


def scenario10():
    return (
        ("mite_perftest:journey", None, volume_model_factory(10)),
    )


def scenario100():
    return (
        ("mite_perftest:journey", None, volume_model_factory(100)),
    )


def scenario1000():
    return (
        ("mite_perftest:journey", None, volume_model_factory(1000)),
    )
