#!/usr/bin/env python3

import glob  # TODO: possibly not the most rigorous way of doing what we want
import logging
import re
import signal
import subprocess
import time
from shutil import rmtree

import msgpack

import pipeline
import psutil


def do_test():
    logging.info("Deleting collector_data")
    rmtree("collector_data")
    processes = pipeline.create(collector=True, stats=True, debug=True)

    logging.info("Starting controller")
    out = open("controller.log", "w")
    controller = psutil.Popen(
        ("mite", "controller", "scenarios:scenario"), stdout=out, stderr=subprocess.STDOUT
    )
    logging.info("Controller started")

    while controller.status() not in (psutil.STATUS_DEAD, psutil.STATUS_ZOMBIE):
        # FIXME: why zombie?
        time.sleep(5)

    time.sleep(5)  # One last time, make sure all msgs are through

    http_server = processes["http_server"]
    http_server.send_signal(signal.SIGINT)

    for process in processes.values():
        if hasattr(process, "send_signal"):
            process.send_signal(signal.SIGKILL)

    server_out = http_server.stdout.read().decode("utf-8")
    requests = list(re.findall("served ([0-9]+) requests", server_out))
    total_requests = int(requests[-1])

    logging.info(f"requests is {total_requests}")

    txn_count = 0
    curl_count = 0

    for collector_file in glob.glob("collector_data/*"):
        if collector_file == "current_start_time":
            continue
        with open(collector_file, "rb") as fin:
            unpacker = msgpack.Unpacker(fin, raw=False, use_list=False)
            for row in unpacker:
                if row.get("type", None) == "txn":
                    txn_count += 1
                elif row.get("type", None) == "http_curl_metrics":
                    curl_count += 1

    logging.info(f"journey ends: {txn_count}")
    logging.info(f"curl stats: {curl_count}")

    # assert total_requests > 0
    # assert total_requests == txn_count
    # assert total_requests == curl_count
    # TODO: pull from prometheus and assert equality

    logging.info("All done, sleep forever")
    while True:
        pass


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(asctime)s] %(levelname)s [%(module)s:%(lineno)d]: %(message)s",
    )

    do_test()

    # 9/30/19: issues to fix:
    # - prometheus can't find its config file (from piepline.py)
    # - iterating over the recorder data fails
    # - should refactor tyo use the pipeline creation stuff from the
    #   provisioning changes to id-mite-nft
