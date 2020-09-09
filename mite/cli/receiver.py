import asyncio
import logging

from ..utils import _msg_backend_module, spec_import

logger = logging.getLogger(__name__)


def generic_receiver(opts):
    loop = asyncio.get_event_loop()

    receiver = _msg_backend_module(opts).Receiver()
    receiver.connect(opts['RECEIVE_SOCKET'])

    for processor_spec in opts['--processor']:
        handler_class = spec_import(processor_spec)

        try:
            handler = handler_class()
            process_message = getattr(handler, 'process_message', None)
            process_raw_message = getattr(handler, 'process_raw_message', None)
            assert process_message or process_raw_message
            assert not process_message or callable(process_message)
            assert not process_raw_message or callable(process_raw_message)
        except (TypeError, AssertionError):
            logger.error(f"Error with processor '{processor_spec}'")
            logger.error(
                "Processors must have one or both of 'process_message' and 'process_raw_message' methods"
            )
            return

        if process_message:
            receiver.add_listener(process_message)

        if process_raw_message:
            receiver.add_listener(process_raw_message)

    loop.run_until_complete(receiver.run())
