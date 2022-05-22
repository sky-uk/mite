from mite_http import mite_http
from mite import ensure_fixed_separation
from mite.scenario import StopScenario

@mite_http
async def journey(ctx):
    async with ctx.transaction("test1"):
        async with ensure_fixed_separation(1):
            await ctx.http.get("http://localhost:8000")

async def message_journey(ctx):
    async with ctx.transaction("test2"):
        async with ensure_fixed_separation(1):
            ctx.send("test_message")


def volume_model_factory(n, duration=60 * 5):
    def vm(start, end):
        if start > duration:
            raise StopScenario
        return n

    vm.__name__ = f"volume model {n}"
    return vm


scenarios = [
    (10, "testjourney:journey", None),
]

message_scenarios = [
    (10, "testjourney:message_journey", None),
]


# Peak scenario running at full TPS for 1 hour
def peak_scenario():
    for peak, journey, datapool in scenarios:
        yield journey, datapool, volume_model_factory(peak, duration=12 * 60 * 60)

def message_scenario():
    for peak, journey, datapool in message_scenarios:
        yield journey, datapool, volume_model_factory(peak, duration=12 * 60 * 60)
