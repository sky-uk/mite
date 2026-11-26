from ..stats import Aggregator
from ..utils import _msg_backend_module
from .common import run_receiver_until_stopped


def _create_sender(opts):
    socket = opts["--stats-out-socket"]
    sender = _msg_backend_module(opts).Sender()
    sender.connect(socket)
    return sender


def _create_receiver(opts):
    socket = opts["--stats-in-socket"]
    receiver = _msg_backend_module(opts).Receiver()
    receiver.connect(socket)
    return receiver


def stats(opts):
    receiver = _create_receiver(opts)
    agg_sender = _create_sender(opts)
    include = opts["--stats-include-processors"]
    if include is not None:
        include = include.split(",")
    exclude = opts["--stats-exclude-processors"]
    if exclude is not None:
        exclude = exclude.split(",")
    aggregator = Aggregator([agg_sender], include=include, exclude=exclude)
    receiver.add_listener(aggregator.process)
    try:
        run_receiver_until_stopped(receiver)
    finally:
        aggregator.close()
