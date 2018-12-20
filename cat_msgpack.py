import msgpack
import sys

unpacker = msgpack.Unpacker(open(sys.argv[1], 'rb'), encoding='utf-8', use_list=False)
for row in unpacker:
    print(row)
