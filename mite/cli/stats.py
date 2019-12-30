import asyncio

from ..stats import Stats
from ..utils import _msg_backend_module


def _create_sender(opts):
    socket = opts['--stats-out-socket']
    sender = _msg_backend_module(opts).Sender()
    sender.connect(socket)
    return sender


def _create_receiver(opts):
    socket = opts['--stats-in-socket']
    receiver = _msg_backend_module(opts).Receiver()
    receiver.connect(socket)
    return receiver


def stats(opts):
    receiver = _create_receiver(opts)
    agg_sender = _create_sender(opts)
    stats = Stats(sender=agg_sender.send)
    receiver.add_listener(stats.process)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(receiver.run())
