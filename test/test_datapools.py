from mite.datapools import create_iterable_data_pool_with_recycling, create_iterable_data_pool, DataPoolExhausted
import mite.datapools as dps

def test_recycling():
    iterable = 'abcdefgh'
    dp = create_iterable_data_pool_with_recycling(iterable)
    for i in range(len(iterable) * 20):
        dpi = dp.checkout()
        print(dpi)
        dp.checkin(dpi.id)
    assert dp.checkout().data == 'a'


def test_iterable():
    iterable = 'abcdefgh'
    dp = create_iterable_data_pool(iterable)
    for i in range(len(iterable)):
        dpi = dp.checkout()
        print(dpi)
        dp.checkin(dpi.id)
    try:
        dp.checkout()
    except DataPoolExhausted:
        pass
    else:
        assert False, "Data pool should have been exhausted"


def test_recyclable_is_exhausted():
    iterable = "ab"
    dp = dps.RecyclableIterableDataPool(iterable)
    xa = dp.checkout()
    assert xa.data == "a"
    x = dp.checkout()
    assert x.data == "b"
    x = dp.checkout()
    assert x is None
    dp.checkin(xa.id)
    x = dp.checkout()
    assert x.data == "a"
    x = dp.checkout()
    assert x is None
