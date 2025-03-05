import logging
from collections import deque, namedtuple

logger = logging.getLogger(__name__)


DataPoolItem = namedtuple("DataPoolItem", "id data".split())


class DataPoolExhausted(BaseException):
    pass


class RecyclableIterableDataPool:
    def __init__(self, iterable):
        self._data = iterable
        self._initialized = False
        self._available = None

    def _initialize_once(self):
        if self._initialized:
            return
        self._data = tuple(self._data)
        self._available = deque(range(len(self._data)))
        self._initialized = True

    async def checkout(self, config):
        self._initialize_once()
        if self._available:
            item_id = self._available.popleft()
            return DataPoolItem(item_id, self._data[item_id])
        else:
            raise Exception("Recyclable iterable datapool was emptied!")

    async def checkin(self, item_id):
        if self._available is None:
            logger.error(
                f"{repr(self)}: checkin called for {item_id} before the datapool "
                "was initialized!  Maybe a stale runner is hanging around"
            )
            return
        self._available.append(item_id)


class IterableDataPool:
    def __init__(self, iterable):
        self._iter = enumerate(iterable, 1)

    async def checkout(self, config):
        try:
            item_id, data = next(self._iter)
        except StopIteration as e:
            raise DataPoolExhausted() from e
        return DataPoolItem(item_id, data)

    async def checkin(self, item_id):
        pass


def iterable_datapool(fn):
    return IterableDataPool(fn())


def recyclable_iterable_datapool(fn):
    return RecyclableIterableDataPool(fn())


class SingleRunDataPool:
    def __init__(self, data_item):
        self.has_ran = False
        self.data_item = data_item

    async def checkin(self, item_id):
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

    async def checkin(self, item_id):
        pass

    async def checkout(self, config):
        if not self.has_ran:
            self.has_ran = True
            return await self.data_pool.checkout(config)
        raise DataPoolExhausted()
