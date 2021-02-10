import pytest
from pytest import raises

from mite.datapools import (
    DataPoolExhausted,
    IterableDataPool,
    RecyclableIterableDataPool,
)
from mite.scenario import ScenarioManager


@pytest.mark.asyncio
class TestRecyclableIterableDataPool:
    async def test_recycling(self):
        scenario_manager = ScenarioManager()
        iterable = "abcdefgh"
        dp = RecyclableIterableDataPool(iterable)
        for _ in range(len(iterable) * 20):
            dpi = await dp.checkout(scenario_manager)
            await dp.checkin(dpi.id)
        assert (await dp.checkout(scenario_manager)).data == "a"

    async def test_raises_when_exhausted(self):
        scenario_manager = ScenarioManager()
        iterable = "ab"
        dp = RecyclableIterableDataPool(iterable)
        await dp.checkout(scenario_manager)
        await dp.checkout(scenario_manager)
        with raises(Exception, match="Recyclable iterable datapool was emptied!"):
            await dp.checkout(scenario_manager)

    async def test_checkin(self):
        scenario_manager = ScenarioManager()
        iterable = "ab"
        dp = RecyclableIterableDataPool(iterable)
        xa = await dp.checkout(scenario_manager)
        await dp.checkout(scenario_manager)
        await dp.checkin(xa.id)
        x = await dp.checkout(scenario_manager)
        assert x.data == "a"

    async def test_does_not_consume_until_checkout_called(self):
        def my_iterable():
            raise Exception("oops")
            yield None

        scenario_manager = ScenarioManager()
        dp = RecyclableIterableDataPool(my_iterable())
        with raises(Exception, match="oops"):
            await dp.checkout(scenario_manager)


@pytest.mark.asyncio
class TestIterableDataPool:
    async def test_raises_when_exhausted(self):
        scenario_manager = ScenarioManager()
        iterable = "abcdefgh"
        dp = IterableDataPool(iterable)
        for _ in range(len(iterable)):
            dpi = await dp.checkout(scenario_manager)
            await dp.checkin(dpi.id)
        with raises(DataPoolExhausted):
            await dp.checkout(scenario_manager)

    async def test_does_not_consume_until_checkout_called(self):
        def my_iterable():
            raise Exception("oops")
            yield None

        scenario_manager = ScenarioManager()
        dp = IterableDataPool(my_iterable())
        with raises(Exception, match="oops"):
            await dp.checkout(scenario_manager)
