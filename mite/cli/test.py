import asyncio
import logging

from ..collector import Collector
from ..controller import Controller
from ..recorder import Recorder
from ..utils import pack_msg, spec_import
from .common import _create_runner
from .controller import _run as _run_controller


class DirectRunnerTransport:
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

    def add_raw_listener(self, raw_listener):
        self._raw_listeners.append(raw_listener)

    def recieve(self, msg):
        for listener in self._listeners:
            listener(msg)
        packed_msg = pack_msg(msg)
        for raw_listener in self._raw_listeners:
            raw_listener(packed_msg)


class DummyServer:
    async def run(controller, stop_func):
        while stop_func is None or not stop_func():
            await asyncio.sleep(5)


def _setup_msg_processors(receiver, opts):
    collector = Collector(opts['--collector-dir'], int(opts['--collector-roll']))
    recorder = Recorder(opts['--recorder-dir'])
    receiver.add_listener(recorder.process_message)
    receiver.add_raw_listener(collector.process_raw_message)

    extra_processors = [
        spec_import(x)()
        for x in opts["--message-processors"].split(",")
    ]
    for processor in extra_processors:
        if hasattr(processor, "process_message"):
            receiver.add_listener(processor.process_message)
        elif hasattr(processor, "process_raw_message"):
            receiver.add_raw_listener(processor.process_raw_message)
        else:
            logging.error(f"Class {processor.__name__} does not have a process(_raw)_message method!")


def test_scenarios(scenario_spec, opts, scenario_fn):
    server = DummyServer()
    sender = DirectReciever()
    transport = DirectRunnerTransport()

    def get_controller(*args, **kwargs):
        c = Controller(*args, **kwargs)
        transport._controller = c
        return c

    _setup_msg_processors(sender, opts)
    _run_controller(
        scenario_spec,
        opts,
        server,
        sender,
        get_controller=get_controller,
        extra_tasks=(_create_runner(opts, transport, sender.recieve).run(),)
    )


def scenario_test_cmd(opts):
    scenario_spec = opts['SCENARIO_SPEC']
    scenarios_fn = spec_import(scenario_spec)
    test_scenarios(scenario_spec, opts, scenarios_fn)


def journey_test_cmd(opts):
    journey_spec = opts['JOURNEY_SPEC']
    datapool_spec = opts['DATAPOOL_SPEC']
    if datapool_spec:
        datapool = spec_import(datapool_spec)
    else:
        datapool = None
    volumemodel = lambda start, end: int(opts['--volume'])

    def dummy_scenario():
        return [(journey_spec, datapool, volumemodel)]

    test_scenarios(
        journey_spec,
        opts,
        dummy_scenario,
    )


def scenario_cmd(opts):
    if opts['test']:
        scenario_test_cmd(opts)


def journey_cmd(opts):
    if opts['test']:
        journey_test_cmd(opts)
