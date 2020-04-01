import asyncio
import logging
import sys

from mite.logoutput import HttpStatsOutput

from ..collector import Collector
from ..controller import Controller
from ..recorder import Recorder
from ..utils import pack_msg, spec_import
from .common import _create_config_manager, _create_runner, _create_scenario_manager


class DirectRunnerTransport:
    def __init__(self, controller):
        self._controller = controller

    async def hello(self):
        return self._controller.hello()

    async def request_work(self, runner_id, current_work, completed_data_ids, max_work):
        return await self._controller.request_work(
            runner_id, current_work, completed_data_ids, max_work
        )

    async def bye(self, runner_id):
        return self._controller.bye(runner_id)


class DirectReciever:
    def __init__(self):
        self._listeners = []
        self._raw_listeners = []

    def add_listener(self, listener):
        self._listeners.append(listener)

    def filter_listeners(self, clazz):
        return list(
            filter(
                lambda listener: isinstance(listener.__self__, clazz), self._listeners,
            )
        )

    def add_raw_listener(self, raw_listener):
        self._raw_listeners.append(raw_listener)

    def recieve(self, msg):
        for listener in self._listeners:
            listener(msg)
        packed_msg = pack_msg(msg)
        for raw_listener in self._raw_listeners:
            raw_listener(packed_msg)


def _setup_msg_processors(receiver, opts):
    collector = Collector(opts['--collector-dir'], int(opts['--collector-roll']))
    recorder = Recorder(opts['--recorder-dir'])
    receiver.add_listener(recorder.process_message)
    receiver.add_raw_listener(collector.process_raw_message)

    extra_processors = [spec_import(x)() for x in opts["--message-processors"].split(",")]
    for processor in extra_processors:
        if hasattr(processor, "process_message"):
            receiver.add_listener(processor.process_message)
        elif hasattr(processor, "process_raw_message"):
            receiver.add_raw_listener(processor.process_raw_message)
        else:
            logging.error(
                f"Class {processor.__name__} does not have a process(_raw)_message method!"
            )


def _get_http_stats_output(receiver):
    listeners = receiver.filter_listeners(HttpStatsOutput)
    assert len(listeners) == 1
    return listeners[0].__self__


def test_scenarios(test_name, opts, scenarios, config_manager):
    scenario_manager = _create_scenario_manager(opts)
    for journey_spec, datapool, volumemodel in scenarios:
        scenario_manager.add_scenario(journey_spec, datapool, volumemodel)
    controller = Controller(test_name, scenario_manager, config_manager)
    transport = DirectRunnerTransport(controller)
    receiver = DirectReciever()
    _setup_msg_processors(receiver, opts)
    http_stats_output = _get_http_stats_output(receiver)
    loop = asyncio.get_event_loop()

    async def controller_report():
        while True:
            await asyncio.sleep(1)
            controller.report(receiver.recieve)
            if controller.should_stop():
                if http_stats_output.error_total > 0:
                    sys.exit(1)
                return

    loop.run_until_complete(
        asyncio.gather(
            controller_report(), _create_runner(opts, transport, receiver.recieve).run()
        )
    )


def scenario_test_cmd(opts):
    scenario_spec = opts['SCENARIO_SPEC']
    scenarios_fn = spec_import(scenario_spec)
    config_manager = _create_config_manager(opts)
    try:
        scenarios = scenarios_fn(config_manager)
    except TypeError:
        scenarios = scenarios_fn()
    test_scenarios(scenario_spec, opts, scenarios, config_manager)


def journey_test_cmd(opts):
    journey_spec = opts['JOURNEY_SPEC']
    datapool_spec = opts['DATAPOOL_SPEC']
    if datapool_spec:
        datapool = spec_import(datapool_spec)
    else:
        datapool = None
    volumemodel = lambda start, end: int(opts['--volume'])
    test_scenarios(
        journey_spec,
        opts,
        [(journey_spec, datapool, volumemodel)],
        _create_config_manager(opts),
    )


def scenario_cmd(opts):
    if opts['test']:
        scenario_test_cmd(opts)


def journey_cmd(opts):
    if opts['test']:
        journey_test_cmd(opts)
