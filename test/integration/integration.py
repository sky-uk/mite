#!/usr/bin/env python3

import pipeline
import psutil
import re
import time
import msgpack
import glob  # TODO: possibly not the most rigorous way of doing what we want
import signal
import subprocess


def do_test():
    processes = pipeline.create(collector=True, stats=True, debug=True)

    out = open("controller.log", "w")
    controller = psutil.Popen(
        ("mite", "controller", "scenarios:scenario"), stdout=out, stderr=subprocess.STDOUT
    )

    while controller.status() not in (psutil.STATUS_DEAD, psutil.STATUS_ZOMBIE):
        # FIXME: why zombie?
        time.sleep(5)

    time.sleep(5)  # One last time, make sure all msgs are through

    http_server = processes["http_server"]
    http_server.send_signal(signal.SIGINT)
    server_out = http_server.stdout.read().decode("utf-8")
    requests = list(re.findall("served ([0-9]+) requests", server_out))
    total_requests = int(requests[-1])

    print(f"requests is {total_requests}")

    txn_count = 0
    curl_count = 0

    for collector_file in glob.glob("collector_data/*"):
        # TODO: need to make sure that old collector data is blown away
        if collector_file == "current_start_time":
            continue
        with open(collector_file, "rb") as fin:
            unpacker = msgpack.Unpacker(fin, raw=False, use_list=False)
            for row in unpacker:
                if "type" in row:
                    if row["type"] == "txn":
                        txn_count += 1
                    elif row["type"] == "http_curl_metrics":
                        curl_count += 1

    print(f"journey ends: {txn_count}")
    print(f"curl stats: {curl_count}")

    assert total_requests > 0
    assert total_requests == txn_count
    assert total_requests == curl_count
    # TODO: pull from prometheus and assert equality


if __name__ == "__main__":
    do_test()
