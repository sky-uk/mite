import pytest
from pytest import raises

from mite.datapools import (
    DataPoolExhausted,
    IterableDataPool,
    IterableFactoryDataPool,
    RecyclableIterableDataPool,
)
from mite.scenario import ScenarioManager


@pytest.mark.asyncio
class TestRecyclabeIterableDataPool:
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
class TestIterableFactoryDataPool:
    async def test_recycling(self):
        scenario_manager = ScenarioManager()
        iterable_factory = lambda: "abcdefgh"
        dp = IterableFactoryDataPool(iterable_factory)
        for _ in range(8 * 20):
            dpi = await dp.checkout(scenario_manager)
            await dp.checkin(dpi.id)
        assert (await dp.checkout(scenario_manager)).data == "a"

    async def test_raises_when_exhausted(self):
        scenario_manager = ScenarioManager()
        iterable = lambda: "ab"
        dp = IterableFactoryDataPool(iterable)
        await dp.checkout(scenario_manager)
        await dp.checkout(scenario_manager)
        with raises(Exception, match="Iterable factory data pool lapped itself"):
            await dp.checkout(scenario_manager)

    async def test_checkin(self):
        scenario_manager = ScenarioManager()
        iterable = lambda: "ab"
        dp = IterableFactoryDataPool(iterable)
        xa = await dp.checkout(scenario_manager)
        await dp.checkout(scenario_manager)
        await dp.checkin(xa.id)
        x = await dp.checkout(scenario_manager)
        assert x.data == "a"

    async def test_checkin_with_lapping(self):
        # I (AWE) am not sure if this is what we want, but it does describe
        # the behavior as it exists now.  In general, with a factory, we can't
        # guarantee that if it produced a "b" on one call that it's ever going
        # to produce a "b" again.  There are a couple of ways we could handle
        # this: one is to just hand out the results forever (don't have any
        # handling of lapping/exhaustion).  The second, which we have adopted,
        # is to ensure that the iterator doesn't lap itself, that is that by
        # the time we are consuming item I from generation N+1, item I from
        # generation N has already been checked back in.  This still makes
        # possibly false assumptions about the structure of the return value
        # of the factory, though.
        #
        # Our test code (ab)used iterable factory data pools for laziness, not
        # for the ability to vary the return value from call to call.  If it
        # was up to me entirely, I'd deprecate iterable factories now that we
        # provide laziness by default you can either use a recyclable iterable
        # (which consumes its iterable), or just use a plain iterable and set
        # up whatever cycling behavior you want (with no built-in exhaustion
        # detection -- you provide that too).
        scenario_manager = ScenarioManager()
        iterable = lambda: "ab"
        dp = IterableFactoryDataPool(iterable)
        await dp.checkout(scenario_manager)
        xb = await dp.checkout(scenario_manager)
        await dp.checkin(xb.id)
        with raises(Exception, match="Iterable factory data pool lapped itself"):
            await dp.checkout(scenario_manager)

    async def test_does_not_consume_until_checkout_called(self):
        def my_iterable():
            raise Exception("oops")
            yield None

        scenario_manager = ScenarioManager()
        dp = IterableFactoryDataPool(my_iterable)
        with raises(Exception, match="oops"):
            await dp.checkout(scenario_manager)


@pytest.mark.asyncio
async def test_iterable():
    scenario_manager = ScenarioManager()
    iterable = "abcdefgh"
    dp = IterableDataPool(iterable)
    for _ in range(len(iterable)):
        dpi = await dp.checkout(scenario_manager)
        await dp.checkin(dpi.id)
    with raises(DataPoolExhausted):
        await dp.checkout(scenario_manager)
