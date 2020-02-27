from .common import _create_config_manager, _create_scenario_manager, _create_sender
from ..utils import spec_import, _msg_backend_module
from ..controller import Controller
import asyncio
import os
import logging


def _create_controller_server(opts):
    socket = opts['--controller-socket']
    return _msg_backend_module(opts).ControllerServer(socket)


def controller(opts):
    config_manager = _create_config_manager(opts)
    scenario_spec = opts['SCENARIO_SPEC']
    scenarios_fn = spec_import(scenario_spec)
    scenario_manager = _create_scenario_manager(scenario_spec, opts)
    try:
        scenarios = scenarios_fn(config_manager)
    except TypeError:
        scenarios = scenarios_fn()
    for journey_spec, datapool, volumemodel in scenarios:
        scenario_manager.add_scenario(journey_spec, datapool, volumemodel)
    controller = Controller(scenario_manager, config_manager)
    server = _create_controller_server(opts)
    sender = _create_sender(opts)
    loop = asyncio.get_event_loop()
    # logging_id = None
    # logging_url = opts["--logging-webhook"]
    # if logging_url is None:
    #     try:
    #         logging_url = os.environ["MITE_LOGGING_URL"]
    #     except KeyError:
    #         pass
    # if logging_url is not None:
    #     logging_id = _controller_log_start(scenario_spec, logging_url)

    start_event = asyncio.Event()
    end_event = asyncio.Event()

    async def run_time_function():
        time_fn = getattr(scenarios_fn, "_mite_time_function", None)
        if time_fn is not None:
            await time_fn(scenario_spec, config_manager, start_event, end_event)
            if not end_event.is_set():
                logging.error(
                    "The time function exited before the scenario ended, which seems like a bug"
                )
        else:
            start_event.set()
            await end_event.wait()

    async def controller_report():
        while True:
            if controller.should_stop():
                return
            await asyncio.sleep(1)
            controller.report(sender.send)

    async def run_controller():
        await start_event.wait()
        await server.run(controller, controller.should_stop)
        end_event.set()

    run_time_fn_task = asyncio.create_task(run_time_function())

    try:
        loop.run_until_complete(
            asyncio.gather(
                controller_report(), run_controller(), run_time_fn_task
            )
        )
    except KeyboardInterrupt:
        # TODO: kill runners, do other shutdown tasks
        logging.info("Received interrupt signal, shutting down")
        if not end_event.is_set():
            run_time_fn_task.cancel()
            loop.stop()
            loop.run_until_complete(run_time_fn_task)
    finally:
        _controller_log_end(logging_id, logging_url)
        # TODO: cancel all loop tasks?  Something must be done to stop this
        # from hanging
        loop.close()
