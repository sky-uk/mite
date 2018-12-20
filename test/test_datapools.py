from mite.datapools import create_iterable_data_pool_with_recycling, create_iterable_data_pool, DataPoolExhausted


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
