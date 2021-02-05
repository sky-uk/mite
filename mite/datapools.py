import logging
from collections import deque, namedtuple

logger = logging.getLogger(__name__)


DataPoolItem = namedtuple("DataPoolItem", "id data".split())


class DataPoolExhausted(BaseException):
    pass


class RecyclableIterableDataPool:
    def __init__(self, iterable):
        self._data = iterable
        self._available = deque(range(len(self._data)))
        self._initialized = False

    def _initialize_once(self):
        if self._initialized:
            return
        self._data = tuple(self._data)
        self._initialized = True

    async def checkout(self, config):
        self._initialize_once()
        if self._available:
            id = self._available.popleft()
            return DataPoolItem(id, self._data[id])
        else:
            raise Exception("Recyclable iterable datapool was emptied!")

    async def checkin(self, id):
        self._available.append(id)


class IterableFactoryDataPool:
    def __init__(self, iterable_factory):
        self._iterable_factory = iterable_factory
        self._checked_out = set()
        self._initialized = False

    def _initialize_once(self):
        if self._initialized:
            return
        self._iter = self._cycle()
        self._initialized = True

    def _cycle(self):
        while True:
            iterable = enumerate(self._iterable_factory(), 1)
            for id, data in iterable:
                yield id, data

    async def checkout(self, config):
        _id, data = next(self._iter)
        if _id in self._checked_out:
            raise Exception("Iterable factory data pool lapped itself")
        self._checked_out.add(_id)
        return DataPoolItem(_id, data)

    async def checkin(self, id):
        self._checked_out.remove(id)


class IterableDataPool:
    def __init__(self, iterable):
        self._iter = enumerate(iterable, 1)

    async def checkout(self, config):
        try:
            id, data = next(self._iter)
        except StopIteration:
            raise DataPoolExhausted()
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
