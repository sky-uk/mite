import pytest

from mite.scenario import ScenarioManager

from mite.datapools import (
    create_iterable_data_pool_with_recycling,
    create_iterable_data_pool,
    DataPoolExhausted,
)
import mite.datapools as dps


@pytest.mark.asyncio
async def test_recycling():
    scenario_manager = ScenarioManager()
    iterable = 'abcdefgh'
    dp = create_iterable_data_pool_with_recycling(iterable)
    for i in range(len(iterable) * 20):
        dpi = await dp.checkout(scenario_manager)
        await dp.checkin(dpi.id)
    assert (await dp.checkout(scenario_manager)).data == 'a'


@pytest.mark.asyncio
async def test_iterable():
    scenario_manager = ScenarioManager()
    iterable = 'abcdefgh'
    dp = create_iterable_data_pool(iterable)
    for i in range(len(iterable)):
        dpi = await dp.checkout(scenario_manager)
        await dp.checkin(dpi.id)
    try:
        await dp.checkout(scenario_manager)
    except DataPoolExhausted:
        pass
    else:
        assert False, "Data pool should have been exhausted"


@pytest.mark.asyncio
async def test_recyclable_is_exhausted():
    scenario_manager = ScenarioManager()
    iterable = "ab"
    dp = dps.RecyclableIterableDataPool(iterable)
    xa = await dp.checkout(scenario_manager)
    assert xa.data == "a"
    x = await dp.checkout(scenario_manager)
    assert x.data == "b"
    x = await dp.checkout(scenario_manager)
    assert x is None
    await dp.checkin(xa.id)
    x = await dp.checkout(scenario_manager)
    assert x.data == "a"
    x = await dp.checkout(scenario_manager)
    assert x is None
