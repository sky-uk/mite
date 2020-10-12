import json
import sys
from datetime import datetime

import msgpack

from mite.utils import pack_msg


def prettify_timestamps(d):
    for key in ("time", "start_time", "end_time"):
        if key in d:
            d[key] = datetime.fromtimestamp(float(d[key])).isoformat()


def cat(opts):
    with open(opts['MSGPACK_FILE_PATH'], 'rb') as file_in:
        unpacker = msgpack.Unpacker(
            file_in, use_list=False, raw=False, strict_map_key=False
        )
        for row in unpacker:
            if opts["--prettify-timestamps"]:
                prettify_timestamps(row)
            json.dump(row, sys.stdout)
            sys.stdout.write("\n")


def uncat(opts):
    for line in sys.stdin.readlines():
        value = json.loads(line)
        sys.stdout.buffer.write(pack_msg(value))
