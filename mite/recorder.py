import contextlib
import logging
import os

from .utils import pack_msg

logger = logging.getLogger(__name__)


class Recorder:
    def __init__(self, target_dir=None):
        logger.info("Starting recorder")
        if target_dir is None:
            target_dir = "recorded_data"
        self._target_dir = os.path.abspath(target_dir)
        with contextlib.suppress(FileExistsError):
            os.makedirs(self._target_dir)

    def process_message(self, msg):
        if "type" in msg and "name" in msg and msg["name"] is not None:
            msg_file = os.path.join(self._target_dir, msg["name"] + ".msgpack")
            if msg["type"] == "data_created":
                open(msg_file, "ab").write(pack_msg(msg["data"]))
            elif msg["type"] == "purge_data":
                try:
                    os.remove(msg_file)
                except FileNotFoundError:
                    logger.info("Tried to delete a file that didn't exist, continuing")
