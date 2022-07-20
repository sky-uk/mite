#!/usr/bin/env python

import datetime
import math
import os
import re
import signal
import subprocess
import time

import altair as alt
import pandas as pd
import psutil

if os.path.dirname(__file__) != "":
    os.chdir(os.path.dirname(__file__))


def run_test(scenario):
    try:
        http_server = psutil.Popen(("python", "./http_server.py"), stdout=subprocess.PIPE)
        runner = psutil.Popen(
            (
                "mite",
                "runner",
                # "--log-level=DEBUG"
            )
        )
        duplicator = psutil.Popen(("mite", "duplicator", "tcp://127.0.0.1:14303"))
        # TODO: we should make sure that the collector has a tmpfs in RAM to
        # run in, so that disk performance doesn't get into the mix...
        collector = psutil.Popen(("mite", "collector"))
        controller = psutil.Popen(
            (
                "mite",
                "controller",
                "--spawn-rate=1000000",
                # "--log-level=DEBUG",
                scenario,
            )
        )
        # TODO: prometheus exporter

        # TODO: make sure all have started happily, none have errored

        rows = []
        start = time.time()

        while True:
            with runner.oneshot(), duplicator.oneshot(), controller.oneshot():
                #  TODO: why does it go zombie?
                if controller.status() in (psutil.STATUS_DEAD, psutil.STATUS_ZOMBIE):
                    break
                elapsed = math.floor(time.time() - start)
                rows += (
                    {
                        "elapsed": elapsed,
                        "process": "runner",
                        "cpu": runner.cpu_percent(),
                        "mem": runner.memory_info().rss,
                    },
                    {
                        "elapsed": elapsed,
                        "process": "duplicator",
                        "cpu": duplicator.cpu_percent(),
                        "mem": duplicator.memory_info().rss,
                    },
                    {
                        "elapsed": elapsed,
                        "process": "controller",
                        "cpu": controller.cpu_percent(),
                        "mem": controller.memory_info().rss,
                    },
                )
                time.sleep(5)

        http_server.send_signal(signal.SIGINT)

        for secs, requests in re.findall(
            "([0-9.]+): served ([0-9]+) requests",
            http_server.stdout.read().decode("utf-8"),
        ):
            rows.append(
                {
                    "elapsed": math.floor(float(secs) - start),
                    "process": "http",
                    "requests": int(requests),
                }
            )

        for d in rows:
            d["scenario"] = scenario

        return rows
    finally:
        for process in (runner, collector, duplicator, http_server):
            if process is not None:
                process.terminate()


if __name__ == "__main__":
    now = datetime.datetime.now()

    data = []
    scenarios = (
        "mite_perftest:scenario1",
        "mite_perftest:scenario10",
        "mite_perftest:scenario100",
        "mite_perftest:scenario1000",
    )
    for scenario in scenarios:
        data += run_test(scenario)

    outdir = os.path.join(
        f"{os.environ['MITE_PERFTEST_OUT']}",
        f"{now.year}-{now.month:02d}-{now.day:02d}",
        f"{now.hour:02d}-{now.minute:02d}",
    )
    os.makedirs(outdir, exist_ok=True)
    os.chdir(outdir)

    df = pd.DataFrame(data)

    df.to_csv("samples.csv")

    chart = alt.vconcat()
    for scenario in scenarios:
        subdata = df.loc[df.scenario == scenario]
        base = alt.Chart(subdata).encode(x=alt.X("elapsed", axis=alt.Axis(tickMinStep=5)))
        cpu = base.mark_line(point=True).encode(
            y="cpu", color="process", tooltip=["process", "cpu"]
        )
        mem = base.mark_line(point=True, strokeDash=[5, 5]).encode(
            y=alt.Y("mem", axis=alt.Axis(format="~s", title="memory")),
            color="process",
            tooltip=[alt.Tooltip("process"), alt.Tooltip("mem", format="~s")],
        )
        requests = base.mark_line(point=True, strokeDash=[10, 2, 2, 2]).encode(
            y=alt.Y("requests", axis=None), color="process", tooltip=["requests"]
        )
        subchart = (
            alt.layer(cpu, mem, requests)
            .interactive()
            .resolve_scale(y="independent")
            .properties(title=scenario)
        )

        chart &= subchart

    chart.save("chart.html")
