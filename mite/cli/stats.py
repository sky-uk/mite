import asyncio
import logging

from ..stats import Aggregator
from ..utils import _msg_backend_module

logger = logging.getLogger(__name__)


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
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(receiver.run())
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down stats")
    finally:
        try:
            aggregator.close()
        finally:
            loop.close()
