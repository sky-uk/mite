import asyncio
import logging
from functools import partial

from ..controller import Controller
from ..utils import _msg_backend_module, spec_import
from .common import (_create_config_manager, _create_scenario_manager,
                     _create_sender)


def _create_controller_server(opts):
    socket = opts['--controller-socket']
    return _msg_backend_module(opts).ControllerServer(socket)


async def _run_time_function(time_fn, start_event, end_event):
    if time_fn is not None:
        await time_fn(start_event, end_event)
        if not end_event.is_set():
            logging.error(
                "The time function exited before the scenario ended, which seems like a bug"
            )
    else:
        start_event.set()
        await end_event.wait()


async def _send_controller_report(sender):
    while True:
        if controller.should_stop():
            return
        await asyncio.sleep(1)
        controller.report(sender.send)


async def _run_controller(server, controller, start_event, end_event):
    await start_event.wait()
    await server.run(controller, controller.should_stop)
    end_event.set()


def _run(scenario_spec, opts, scenarios_fn, server, sender, get_controller=Controller, extra_tasks=()):
    config_manager = _create_config_manager(opts)
    scenario_manager = _create_scenario_manager(scenario_spec, opts)
    try:
        scenarios = scenarios_fn(config_manager)
    except TypeError:
        scenarios = scenarios_fn()
    for journey_spec, datapool, volumemodel in scenarios:
        scenario_manager.add_scenario(journey_spec, datapool, volumemodel)
    controller_object = get_controller(scenario_manager, config_manager)

    time_fn = getattr(scenarios_fn, "_mite_time_function", None)
    if time_fn is not None:
        time_fn = partial(time_fn, scenario_spec, config_manager)

    loop = asyncio.get_event_loop()
    start_event = asyncio.Event()
    end_event = asyncio.Event()

    time_fn_task = asyncio.create_task(_run_time_function(
        time_fn, start_event, end_event
    ))

    try:
        loop.run_until_complete(
            asyncio.gather(
                _send_controller_report(sender),
                _run_controller(server, controller_object, start_event, end_event),
                time_fn_task,
                *extra_tasks,
            )
        )
    except KeyboardInterrupt:
        # TODO: kill runners, do other shutdown tasks
        logging.info("Received interrupt signal, shutting down")
        if not end_event.is_set():
            time_fn_task.cancel()
            loop.run_until_complete(time_fn_task)
    finally:
        # TODO: cancel all loop tasks?  Something must be done to stop this
        # from hanging
        loop.close()


def controller(opts):
    server = _create_controller_server(opts)
    sender = _create_sender(opts)
    scenario_spec = opts['SCENARIO_SPEC']
    scenarios_fn = spec_import(scenario_spec)

    _run(scenario_spec, opts, scenarios_fn, server, sender)
