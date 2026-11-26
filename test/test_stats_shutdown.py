"""mite stats and mite exporter shut down cleanly on SIGINT and SIGTERM,
sending everything aggregated since the last dump. Runs the real commands."""

import signal
import socket
import subprocess
import sys
import time

import pytest
import zmq

from mite.utils import pack_msg, unpack_msg

TXN = {"type": "txn", "test": "t", "journey": "j", "transaction": "x", "had_error": False}


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _mite(tmp_path, *args):
    # Run outside the repo, so the working directory mite adds to sys.path
    # can't shadow the installed package
    return subprocess.Popen(
        [sys.executable, "-m", "mite", *args],
        cwd=tmp_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def _send_when_connected(sock, msg, timeout=20):
    deadline = time.monotonic() + timeout
    while True:
        try:
            return sock.send(pack_msg(msg), zmq.NOBLOCK)
        except zmq.Again:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.05)


def _stop(proc, sig):
    proc.send_signal(sig)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail(f"still running 10s after {sig.name}: {proc.stderr.read().decode()}")


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
def test_mite_stats_sends_everything_before_exiting(tmp_path, sig):
    stats_in, stats_out = _free_port(), _free_port()
    context = zmq.Context()
    to_stats = context.socket(zmq.PUSH)
    to_stats.bind(f"tcp://127.0.0.1:{stats_in}")
    from_stats = context.socket(zmq.PULL)
    from_stats.bind(f"tcp://127.0.0.1:{stats_out}")
    proc = _mite(
        tmp_path,
        "stats",
        f"--stats-in-socket=tcp://127.0.0.1:{stats_in}",
        f"--stats-out-socket=tcp://127.0.0.1:{stats_out}",
        "--stats-include-processors=mite",
    )
    try:
        # The first message after the 0.25s dump interval flushes; the second
        # comes straight after, so only the final dump on shutdown carries it
        _send_when_connected(to_stats, TXN)
        to_stats.send(pack_msg(TXN))
        time.sleep(0.1)
        _stop(proc, sig)
        assert proc.returncode == 0

        total = 0
        while from_stats.poll(1000):
            for summary in unpack_msg(from_stats.recv()):
                if summary["name"] == "mite_transaction_total":
                    total += sum(summary["metrics"].values())
        assert total == 2
    finally:
        if proc.poll() is None:
            proc.kill()
        context.destroy(linger=0)


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
def test_mite_exporter_exits(tmp_path, sig):
    proc = _mite(
        tmp_path,
        "exporter",
        f"--stats-out-socket=tcp://127.0.0.1:{_free_port()}",
        f"--stats-output=prometheus://127.0.0.1:{_free_port()}",
    )
    time.sleep(2)
    assert proc.poll() is None, proc.stderr.read().decode()
    _stop(proc, sig)
    assert proc.returncode == 0
