import logging
from collections import deque

from sqlalchemy import text

from mite.datapools import DataPoolExhausted, DataPoolItem

logger = logging.getLogger(__name__)


class DBIterableDataPool:
    def __init__(
        self,
        db_engine,
        query,
        preload_minimum=None,
        max_size=None,
    ):
        self.db_engine = db_engine
        self.query = query
        self.max_size = max_size
        self._data = []
        self.item_index = 0
        self.db_exhausted = False
        self.preload_minimum = preload_minimum

        # Adjust preload_minimum if needed
        if max_size and preload_minimum and preload_minimum > max_size:
            self.preload_minimum = max_size

        # Load initial data
        if preload_minimum:
            while len(self._data) < self.preload_minimum and not self.db_exhausted:
                self.populate()
        else:
            while not self.db_exhausted:
                self.populate()

    def populate(self):
        # Stop if at max_size
        if self.max_size is not None and len(self._data) >= self.max_size:
            return

        with self.db_engine.connect() as conn:
            result = conn.execute(text(self.query))
            rows = result.fetchall()

            if not rows:
                self.db_exhausted = True
                return

            # Add rows up to max_size
            rows_added = 0
            for row in rows:
                if self.max_size is not None and len(self._data) >= self.max_size:
                    break
                self._data.append((self.item_index, dict(row._mapping)))
                self.item_index += 1
                rows_added += 1

            # Only mark as exhausted if we processed all available rows
            # If we only processed some rows due to max_size limit, don't mark as exhausted
            if rows_added == len(rows):
                self.db_exhausted = True

    async def checkout(self, config):
        try:
            item_id, row = self._data.pop(0)
            return DataPoolItem(item_id, row)
        except IndexError as e:
            raise DataPoolExhausted() from e

    async def checkin(self, item_id):
        pass


class DBRecyclableIterableDataPool(DBIterableDataPool):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._available = deque(range(len(self._data)))
        self._checked_out = set()

    async def checkout(self, config):
        if self._available:
            item_id = self._available.popleft()
            self._checked_out.add(item_id)
            row = self._data[item_id][1]
            return DataPoolItem(item_id, row)
        else:
            raise DataPoolExhausted("Recyclable iterable datapool was emptied!")

    async def checkin(self, item_id):
        if item_id in self._checked_out:
            self._checked_out.remove(item_id)
            self._available.append(item_id)
