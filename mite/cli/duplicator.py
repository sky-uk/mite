import asyncio
import os
import signal

from ..utils import _msg_backend_module


def _create_duplicator(opts):
    return _msg_backend_module(opts).Duplicator(
        opts['--message-socket'], opts['OUT_SOCKET']
    )


def duplicator(opts):
    duplicator = _create_duplicator(opts)

    def handler(_signum, _stack_frame):
        messages_to_dump = 100
        if "MITE_DEBUG_MESSAGES_TO_DUMP" in os.environ:
            try:
                messages_to_dump = int(os.environ["MITE_DEBUG_MESSAGES_TO_DUMP"])
            except ValueError:
                pass
        else:
            try:
                with open(os.environ.get("MITE_DEBUG_MESSAGES_TO_DUMP_FILE",
                                         "/tmp/mite_messages_to_dump")) as fin:
                    messages_to_dump = int(fin.read().strip())
            except (FileNotFoundError, ValueError):
                pass
        duplicator._debug_messages_to_dump = messages_to_dump

    signal.signal(signal.SIGUSR1, handler)
    asyncio.get_event_loop().run_until_complete(duplicator.run())
