import logging
from collections import deque


from mite.datapools import DataPoolExhausted, DataPoolItem
from sqlalchemy import text

logger = logging.getLogger(__name__)

class DBIterableDataPool:
    def __init__(
        self,
        db_engine,
        query,
        preload_minimum=None,
    ):
        self.db_engine = db_engine
        self.query = query
        self._data = []
        self.item_index = 0
        self.populating = False
        self.exhausted = False
        self.preload_minimum = preload_minimum

        if preload_minimum:
            while len(self._data) < preload_minimum and not self.exhausted:
                self.populate()
        else:
            while not self.exhausted:
                self.populate()

    def populate(self):
        with self.db_engine.connect() as conn:
            result = conn.execute(text(self.query))
            rows = result.fetchall()
            if not rows:
                self.exhausted = True
                return
            for row in rows:
                self._data.append((self.item_index, dict(row._mapping)))
                self.item_index += 1
            self.exhausted = True  # Only one batch for now; adjust for pagination if needed

    async def checkout(self, config):
        if not self.exhausted and not self.populating:
            self.populating = True
            self.populate()
            self.populating = False

        try:
            item_id, row = self._data.pop(0)
            data = row
        except IndexError as e:
            raise DataPoolExhausted() from e
        return DataPoolItem(item_id, data)

    async def checkin(self, item_id):
        pass


class DBRecyclableIterableDataPool(DBIterableDataPool):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._available = deque(range(len(self._data)))

    async def checkout(self, config):
        if not self.exhausted and not self.populating:
            self.populating = True
            starting_id = self.item_index
            self.populate()
            self._available.extend(range(starting_id, self.item_index))
            self.populating = False

        if self._available:
            item_id = self._available.popleft()
            row = self._data[item_id][1]
            data = row
            return DataPoolItem(item_id, data)
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
        



