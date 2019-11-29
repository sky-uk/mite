import asyncio

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


def stats(opts):
    scenario_spec = opts.get("--scenario-spec")
    if scenario_spec is not None:
        scenario_fn = spec_import(scenario_spec)
        for _ in scenario_fn({}):  # FIXME: hack for passing the actual config object...want a better way
            # What we're doing here is a little weird.  We have arranged so
            # that the mite_* driver modules (http, selenium, amqp) will, as a
            # side effect of being imported, register their specific stats
            # (in the sense of `Stats.register` in mite/stats.py, q.v.)  So
            # here, we want to import the scenario function and (if it's a
            # generator) consume it all, so that any side effects of
            # importation are triggered.  This sort of relies on scenarios
            # being otherwise side-effect free (FIXME: document this
            # assumption).  As to why do this at all: it comes from the fact
            # that the controller and the stats are separate processes.  An
            # alternative architecture would be to have the controller tell
            # the stats processor what stats to use...but that means stats
            # need to be serializable, and it adds a new message type to the
            # mite IPC zoo, so I think I disperfer that choice
            pass
    # We'll also unconditionally import mite_http, because the HTTP stats are
    # judged important enough to be always available
    import mite_http  # noqa

    # Now for the "real" body of the function
    receiver = _create_receiver(opts)
    agg_sender = _create_sender(opts)
    stats = Stats(sender=agg_sender.send)
    receiver.add_listener(stats.process)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(receiver.run())
