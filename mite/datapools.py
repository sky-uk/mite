import asyncio
import boto3
import logging
import time
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


class S3IterableDataPool:
    def __init__(
        self,
        bucket_name,
        prefix="",
        access_key_id=None,
        secret_access_key=None,
        preload_minimum=None,
    ):
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.list_obj_kwargs = {"Bucket": self.bucket_name, "Prefix": self.prefix}
        self._data = []
        self.item_index = 0
        self.populating = False
        self.exhausted = False

        if preload_minimum:
            while len(self._data) < preload_minimum and not self.exhausted:
                self.populate()
        else:
            while not self.exhausted:
                self.populate()

    def populate(self):
        response = self.s3_client.list_objects_v2(**self.list_obj_kwargs)

        for obj in response["Contents"]:
            self._data.append((self.item_index, obj["Key"]))
            self.item_index += 1

        if response.get("IsTruncated"):
            self.list_obj_kwargs.update(
                {"ContinuationToken": response["NextContinuationToken"]}
            )
        else:
            self.exhausted = True

    async def checkout(self, config):
        if not self.exhausted and not self.populating:
            self.populating = True
            self.populate()
            self.populating = False

        try:
            item_id, file_key = self._data.pop(0)
            file_obj = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_key)
            file_content = file_obj["Body"].read().decode("utf-8")
            data = (file_key, file_content)

        except IndexError as e:
            raise DataPoolExhausted() from e
        return DataPoolItem(item_id, data)

    async def checkin(self, item_id):
        pass


class S3RecyclableIterableDataPool(S3IterableDataPool):
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

            file_key = self._data[item_id][1]
            file_obj = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_key)
            file_content = file_obj["Body"].read().decode("utf-8")
            data = (file_key, file_content)

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
