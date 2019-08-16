from collections import namedtuple, deque
from itertools import count
import logging


logger = logging.getLogger(__name__)


DataPoolItem = namedtuple('DataPoolItem', 'id data'.split())


class DataPoolExhausted(BaseException):
    pass


class RecyclableIterableDataPool:
    def __init__(self, iterable):
        self._checked_out = {}
        self._available = deque(DataPoolItem(id, data) for id, data in enumerate(iterable, 1))

    def checkout(self):
        if self._available:
            dpi = self._available.popleft()
            self._checked_out[dpi.id] = dpi.data
            return dpi
        else:
            # FIXME: should this raise a DataPoolExhausted exception?
            return None

    def checkin(self, id):
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

    def checkout(self):
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

    def checkin(self, id):
        self._checked_out.remove(id)


class IterableDataPool:
    def __init__(self, iterable):
        self._iter = iter(iterable)
        self._id_gen = count(1)

    def checkout(self):
        try:
            data = next(self._iter)
        except StopIteration:
            raise DataPoolExhausted()
        else:
            id = next(self._id_gen)
            dpi = DataPoolItem(id, data)
            return dpi

    def checkin(self, id):
        pass


def create_iterable_data_pool_with_recycling(iterable):
    return RecyclableIterableDataPool(iterable)


def create_iterable_data_pool(iterable):
    return IterableDataPool(iterable)


def iterable_factory_data_pool(fn):  # pragma: nocover
    return IterableFactoryDataPool(fn)
