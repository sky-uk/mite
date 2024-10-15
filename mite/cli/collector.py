import asyncio

from ..collector import Collector
from ..utils import _msg_backend_module, spec_import


def _collector_receiver(opts):
    socket = opts["--collector-socket"]
    receiver = _msg_backend_module(opts).Receiver()
    receiver.connect(socket)
    return receiver


def collector(opts):
    receiver = _collector_receiver(opts)
    filter_fn = None
    if filter_fn_spec := opts["--collector-filter"]:
        filter_fn = spec_import(filter_fn_spec)
    collector = Collector(
        target_dir=opts["--collector-dir"],
        roll_after=int(opts["--collector-roll"]),
        filter_fn=filter_fn,
        use_json=opts["--collector-use-json"],
    )
    receiver.add_raw_listener(collector.process_raw_message)
    asyncio.get_event_loop().run_until_complete(receiver.run())
