from mf_utils import mite_ui_wrapper

from mite.datapools import RecyclableIterableDataPool


@mite_ui_wrapper("journey")
async def test_sample_journey():
    pass


@mite_ui_wrapper("journey")
async def test_another_journey():
    pass


@mite_ui_wrapper("scenario")
def scenario_sample_scenario():
    pass


@mite_ui_wrapper("scenario")
def scenario_another_scenario():
    pass


@mite_ui_wrapper("datapool")
def datapool_sample_datapool():
    pass


second_sample_datapool = mite_ui_wrapper.datapool(("1", "2"))


@mite_ui_wrapper("config")
def sample_config():
    pass


@mite_ui_wrapper("config")
def another_config():
    pass


@mite_ui_wrapper("journey")
async def actual_journey(ctx, num1, num2):
    async with ctx.transaction("Actual Journey"):
        result = num1 + num2
        print(result)


actual_datapool = mite_ui_wrapper.datapool(
    RecyclableIterableDataPool([(i, i + 2) for i in range(5000)])
)

volumemodel = lambda start, end: 10


@mite_ui_wrapper("scenario")
def actual_scenario():
    return [
        ["session_tests.session_test:actual_journey", actual_datapool, volumemodel],
    ]
