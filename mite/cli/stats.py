import asyncio
import logging
from importlib import import_module

import mite_http

from ..stats import Stats
from ..utils import _msg_backend_module, spec_import


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


def _register_stats(opts):
    scenario_spec = opts.get("--scenario-spec")
    if scenario_spec is not None:
        scenario_fn = spec_import(scenario_spec)
        required_stats = scenario_fn.__dict__.get("mite_required_stats", ())
        for stat_module_name in required_stats:
            stat_module = import_module(stat_module_name)
            to_register = stat_module.__dict__.get("_MITE_STATS", ())
            logging.debug(f"Adding {len(to_register)} stats from {stat_module_name}")
            Stats.register()

    # We'll also unconditionally add the mite_http stats, because they are
    # important enough to be always available
    Stats.register(mite_http._MITE_STATS)


def stats(opts):
    _register_stats(opts)
    receiver = _create_receiver(opts)
    agg_sender = _create_sender(opts)
    stats = Stats(sender=agg_sender.send)
    receiver.add_listener(stats.process)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(receiver.run())
