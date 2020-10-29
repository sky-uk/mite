import logging
from collections import deque, namedtuple
from itertools import count

logger = logging.getLogger(__name__)


DataPoolItem = namedtuple('DataPoolItem', 'id data'.split())


class DataPoolExhausted(BaseException):
    pass


class RecyclableIterableDataPool:
    def __init__(self, iterable):
        self._checked_out = {}
        self._available = deque(
            DataPoolItem(id, data) for id, data in enumerate(iterable, 1)
        )

    async def checkout(self, config):
        if self._available:
            dpi = self._available.popleft()
            self._checked_out[dpi.id] = dpi.data
            return dpi
        else:
            # FIXME: should this raise a DataPoolExhausted exception?
            return None

    async def checkin(self, id):
        data = self._checked_out[id]
        self._available.append(DataPoolItem(id, data))


class IterableFactoryDataPool:
    def __init__(self, iterable_factory):
        self._iterable_factory = iterable_factory
        self._checked_out = set()

    def _cycle(self):
        counter = count(1)
        _iter = iter(self._iterable_factory())
        while True:
            try:
                data = next(_iter)
            except StopIteration:
                counter = count(1)
                _iter = iter(self._iterable_factory())
                data = next(_iter)
            _id = next(counter)
            yield _id, data

    async def checkout(self, config):
        if not hasattr(self, '_cycle_gen_iter'):
            self._cycle_gen_iter = self._cycle()
        last_id = 0
        while True:
            _id, data = next(self._cycle_gen_iter)
            if _id not in self._checked_out:
                self._checked_out.add(_id)
                return DataPoolItem(_id, data)
            if _id <= last_id:
                return None
            last_id = _id

    async def checkin(self, id):
        self._checked_out.remove(id)


class IterableDataPool:
    def __init__(self, iterable):
        self._iter = iter(iterable)
        self._id_gen = count(1)

    async def checkout(self, config):
        try:
            data = next(self._iter)
        except StopIteration:
            raise DataPoolExhausted()
        else:
            id = next(self._id_gen)
            dpi = DataPoolItem(id, data)
            return dpi

    async def checkin(self, id):
        pass


def create_iterable_data_pool_with_recycling(iterable):
    return RecyclableIterableDataPool(iterable)


def create_iterable_data_pool(iterable):
    return IterableDataPool(iterable)


def iterable_factory_data_pool(fn):  # pragma: no cover
    return IterableFactoryDataPool(fn)


class SingleRunDataPool:
    def __init__(self, data_item):
        self.has_ran = False
        self.data_item = data_item

    async def checkin(self, id):
        pass

    async def checkout(self, config):
        if not self.has_ran:
            self.has_ran = True
            return DataPoolItem(1, (self.data_item,))
        raise DataPoolExhausted()


class SingleRunDataPoolWrapper:
    def __init__(self, data_pool):
        self.has_ran = False
        self.data_pool = data_pool

    async def checkin(self, id):
        pass

    async def checkout(self, config):
        if not self.has_ran:
            self.has_ran = True
            return await self.data_pool.checkout(config)
        raise DataPoolExhausted()


class MetaDataPoolWrapper:
    """
    Extend a datapool to provide additional context. This is useful
    when driving a single journey from multiple datapools and can be
    used to pass fixed labelling parameters to the journey function.

    ```
    small_datapool = MetaDataPoolWrapper(_small_datapool, "small")
    large_datapool = MetaDataPoolWrapper(_small_datapool, "large")

    def scenario(config):
        return [
            (1, "journey", small_datapool),
            (1, "journey", large_datapool)
        ]

    def journey(ctx, datapool_name, datapool_item):
        assert(datapool_name in ("small", "large"))
    ```
    """
    def __init__(self, data_pool, *context):
        self._data_pool = data_pool
        self._context = context

    async def checkin(self, id):
        return await self._data_pool.checkin(id)

    async def checkout(self, config):
        _id, data = await self._data_pool.checkout(config)
        print(self._context)
        return DataPoolItem(_id, (*self._context, *data))


def add_datapool_metadata(datapool, *metadata):
    return MetaDataPoolWrapper(datapool, *metadata)
