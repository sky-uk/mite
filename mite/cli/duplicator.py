import asyncio
import signal

from ..utils import _msg_backend_module


def _create_duplicator(opts):
    return _msg_backend_module(opts).Duplicator(
        opts['--message-socket'], opts['OUT_SOCKET']
    )


def duplicator(opts):
    duplicator = _create_duplicator(opts)

    def handler(_signum, _stack_frame):
        duplicator._debug_messages = 100

    signal.signal(signal.SIGUSR1, handler)
    asyncio.get_event_loop().run_until_complete(duplicator.run())
