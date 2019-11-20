import logging
import os
import subprocess
import tempfile

import psutil


def start_mite(job_name, debug, *args, log_file=None):
    if log_file is None:
        log_file = job_name
    if not log_file.endswith(".log"):
        log_file += ".log"
    if debug:
        out = open(log_file, "w")
        cmd = ("mite", job_name, "--log-level=DEBUG", *args)
        kwargs = {'stdout': out, 'stderr': subprocess.STDOUT}
    else:
        cmd = ("mite", job_name, *args)
        kwargs = {}
    p = psutil.Popen(cmd, **kwargs)
    if debug:
        out.close()
    return p


def create(n_runners=1, collector=True, stats=False, debug=False):
    for key in os.environ:
        if key.startswith("MITE_CONF"):
            del os.environ[key]

    processes = {}
    processes["http_server"] = psutil.Popen(
        ("python", "./http_server.py"), stdout=subprocess.PIPE
    )

    args = []
    if collector:
        args.append("tcp://127.0.0.1:14303")
    if stats:
        args.append("tcp://127.0.0.1:14304")
    if not collector and not stats:
        raise Exception("Must have either collector or stats!")
    processes["duplicator"] = start_mite("duplicator", debug, *args)

    runners = [
        start_mite("runner", debug, log_file=f"runner{i}") for i in range(n_runners)
    ]
    processes["runners"] = runners

    if collector:
        processes["collector"] = start_mite("collector", debug)

    if stats:
        processes["stats"] = start_mite("stats", debug)
        processes["prometheus_exporter"] = start_mite("prometheus_exporter", debug)
        td = tempfile.TemporaryDirectory()
        processes["tempdir"] = td
        with open(os.path.join(td.name, "prometheus.yml"), "w") as tf:
            tf.write(
                """\
global:
  scrape_interval: 1s

scrape_configs:
  - job_name: 'mite'
    static_configs:
       - targets: ['127.0.0.1:9301']
"""
            )
        logging.info("wrote " + os.path.join(td.name, "prometheus.yml"))
        os.makedirs(os.path.join(td.name, "prometheus"), exist_ok=True)
        prom_log = open("prometheus.log", "w")
        processes["prometheus"] = psutil.Popen(
            (
                "prometheus",
                # Note: won't work on Windows, because on that platform you can't
                # reopen a tempfile object by name
                "--config.file=" + os.path.join(td.name, "prometheus.yml"),
                "--web.listen-address=127.0.0.1:9090",
                "--storage.tsdb.path=" + os.path.join(td.name, "prometheus"),
            ),
            stdout=prom_log,
            stderr=subprocess.STDOUT,
        )

    return processes
