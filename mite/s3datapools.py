import logging
from collections import deque

import boto3

from mite.datapools import DataPoolExhausted, DataPoolItem

logger = logging.getLogger(__name__)


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
