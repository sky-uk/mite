import asyncio
import inspect
import logging
import signal
import threading

from ..config import ConfigManager
from ..runner import Runner
from ..scenario import ScenarioManager
from ..utils import _msg_backend_module, spec_import

logger = logging.getLogger(__name__)


def _create_config_manager(opts):
    config_manager = ConfigManager()
    config = spec_import(opts["--config"])()
    for k, v in config.items():
        config_manager.set(k, v)
    for value in opts["--add-to-config"]:
        k, v = value.split(":", 1)
        config_manager.set(k, v)
    return config_manager


def _create_scenario_manager(opts):
    return ScenarioManager(
        start_delay=float(opts["--delay-start-seconds"]),
        period=float(opts["--max-loop-delay"]),
        spawn_rate=int(opts["--spawn-rate"]),
    )


def _create_sender(opts):
    socket = opts["--message-socket"]
    sender = _msg_backend_module(opts).Sender()
    sender.connect(socket)
    return sender


def _create_runner(opts, transport, msg_sender):
    loop_wait_max = float(opts["--max-loop-delay"])
    loop_wait_min = float(opts["--min-loop-delay"])
    max_work = None
    if opts["--runner-max-journeys"]:
        max_work = int(opts["--runner-max-journeys"])
    return Runner(
        transport,
        msg_sender,
        loop_wait_min=loop_wait_min,
        loop_wait_max=loop_wait_max,
        max_work=max_work,
        debug=opts["--debugging"],
    )


def _get_scenario_with_kwargs(scenario_spec, config_manager, sender):
    scenarios_fn = spec_import(scenario_spec)
    # Inject arguments into the scenario
    scenarios_kwargs = {}
    scenarios_signature = inspect.signature(scenarios_fn)
    for param_name in scenarios_signature.parameters:
        if param_name == "config":
            scenarios_kwargs["config"] = config_manager
        elif param_name == "sender":
            scenarios_kwargs["sender"] = sender
        else:
            raise ValueError(
                f"Don't know how to inject {param_name} into a scenario function!"
            )
    return scenarios_fn(**scenarios_kwargs)


def run_receiver_until_stopped(receiver):
    """Run ``receiver`` until the process gets SIGINT or SIGTERM.

    Returns once the receiver has handled its last message, so the caller
    can then flush and close what the receiver was feeding without racing
    the receiver's thread.
    """
    stop = threading.Event()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def on_signal(sig):
        logger.info("Received %s, shutting down", sig.name)
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, on_signal, sig)
    try:
        loop.run_until_complete(receiver.run(stop.is_set))
    finally:
        loop.close()

