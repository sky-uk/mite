import json
import sys

import msgpack

from mite.utils import pack_msg


def cat(opts):
    with open(opts['MSGPACK_FILE_PATH'], 'rb') as file_in:
        unpacker = msgpack.Unpacker(file_in, use_list=False)
        for row in unpacker:
            print(row)


def uncat(opts):
    for line in sys.stdin.readlines():
        value = json.loads(line)
        sys.stdout.write(pack_msg(value))
