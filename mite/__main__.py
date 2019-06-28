"""\
Mite Load Test Framewwork.

Usage:
    mite [options] scenario test SCENARIO_SPEC
    mite [options] journey test JOURNEY_SPEC [DATAPOOL_SPEC]
    mite [options] controller SCENARIO_SPEC [--message-socket=SOCKET] [--controller-socket=SOCKET]
    mite [options] runner [--message-socket=SOCKET] [--controller-socket=SOCKET]
    mite [options] duplicator [--message-socket=SOCKET] OUT_SOCKET...
    mite [options] collector [--collector-socket=SOCKET]
    mite [options] recorder [--recorder-socket=SOCKET]
    mite [options] stats [--stats-in-socket=SOCKET] [--stats-out-socket=SOCKET]
    mite [options] prometheus_exporter [--stats-out-socket=SOCKET] [--web-address=HOST_PORT]
    mite [options] har HAR_FILE_PATH CONVERTED_FILE_PATH [--sleep-time=SLEEP]
    mite --help
    mite --version

Arguments:
    SCENARIO_SPEC           Identifier for a scenario in the form package_path:callable_name
    CONFIG_SPEC             Identifier for config callable returning dict of config
    JOURNEY_SPEC            Identifier for journey async callable
    VOLUME_MODEL_SPEC       Identifier for volume model callable
    HAR_FILE_PATH           Path for the har file to convert into a mite journey
    CONVERTED_FILE_PATH     Path for the file where will be saved the conversion from har file to mite journey

Examples:
    mite scenario test mite.example:scenario

Options:
    -h --help                       Show this screen
    --version                       Show version
    --debugging                     Drop into IPDB on journey error and exit
    --log-level=LEVEL               Set logger level, one of DEBUG, INFO, WARNING, ERROR, CRITICAL [default: INFO]
    --config=CONFIG_SPEC            Set a config loader to a callable loaded via a spec""" \
""" [default: mite.config:default_config_loader]
    --spawn-rate=NUM_PER_SECOND     Maximum spawn rate [default: 1000]
    --max-loop-delay=SECONDS        Runner internal loop delay maximum [default: 1]
    --runner-max-journeys=NUMBER    Max number of concurrent journeys a runner can run
    --controller-socket=SOCKET      Controller socket [default: tcp://127.0.0.1:14301]
    --message-socket=SOCKET         Message socket [default: tcp://127.0.0.1:14302]
    --collector-socket=SOCKET       Socket [default: tcp://127.0.0.1:14303]
    --stats-in-socket=SOCKET        Socket [default: tcp://127.0.0.1:14304]
    --stats-out-socket=SOCKET       Socket [default: tcp://127.0.0.1:14305]
    --recorder-socket=SOCKET        Socket [default: tcp://127.0.0.1:14306]
    --delay-start-seconds=DELAY     Delay start allowing others to connect [default: 0]
    --volume=VOLUME                 Volume to run journey at [default: 1]
    --web-address=HOST_PORT         Web bind address [default: 127.0.0.1:9301]
    --message-backend=BACKEND       Backend to transport messages over [default: ZMQ]
    --exclude-working-directory     By default mite puts the current directory on the python path
    --collector-dir=DIRECTORY       Set the collectors output directory [default: collector_data]
    --collector-roll=NUM_LINES      How many lines per collector output file [default: 100000]
    --recorder-dir=DIRECTORY        Set the recorders output directory [default: recorder_data]
    --sleep-time=SLEEP              Set the second to await between each request [default: 1]
"""
import sys
import os
import asyncio
import docopt
import threading
import logging
import uvloop

from .scenario import ScenarioManager
from .config import ConfigManager
from .controller import Controller
from .runner import Runner
from .collector import Collector
from .recorder import Recorder
from .utils import spec_import, pack_msg
from .web import app, prometheus_metrics
from .logoutput import MsgOutput, HttpStatsOutput
from .stats import Stats
from .har_to_mite import har_convert_to_mite


def _msg_backend_module(opts):
    msg_backend = opts['--message-backend']
    if msg_backend == 'nanomsg':
        from . import nanomsg
        return nanomsg
    elif msg_backend == 'ZMQ':
        from . import zmq
        return zmq
    else:
        raise ValueError('Unsupported backend %r' % (msg_backend,))


def _collector_receiver(opts):
    socket = opts['--collector-socket']
    receiver = _msg_backend_module(opts).Receiver()
    receiver.connect(socket)
    return receiver


def _recorder_receiver(opts):
    socket = opts['--recorder-socket']
    receiver = _msg_backend_module(opts).Receiver()
    receiver.connect(socket)
    return receiver


def _create_sender(opts):
    socket = opts['--message-socket']
    sender = _msg_backend_module(opts).Sender()
    sender.connect(socket)
    return sender


def _create_stats_sender(opts):
    socket = opts['--stats-out-socket']
    sender = _msg_backend_module(opts).Sender()
    sender.connect(socket)
    return sender


def _create_stats_receiver(opts):
    socket = opts['--stats-in-socket']
    receiver = _msg_backend_module(opts).Receiver()
    receiver.connect(socket)
    return receiver


def _create_prometheus_exporter_receiver(opts):
    socket = opts['--stats-out-socket']
    receiver = _msg_backend_module(opts).Receiver()
    receiver.bind(socket)
    return receiver


def _create_runner_transport(opts):
    socket = opts['--controller-socket']
    return _msg_backend_module(opts).RunnerTransport(socket)


def _create_controller_server(opts):
    socket = opts['--controller-socket']
    return _msg_backend_module(opts).ControllerServer(socket)


def _create_duplicator(opts):
    return _msg_backend_module(opts).Duplicator(opts['--message-socket'], opts['OUT_SOCKET'])


logger = logging.getLogger(__name__)


class DirectRunnerTransport:
    def __init__(self, controller):
        self._controller = controller

    async def hello(self):
        return self._controller.hello()

    async def request_work(self, runner_id, current_work, completed_data_ids, max_work):
        return self._controller.request_work(runner_id, current_work, completed_data_ids, max_work)

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


def _setup_msg_processors(receiver, opts):
    collector = Collector(opts['--collector-dir'], int(opts['--collector-roll']))
    recorder = Recorder(opts['--recorder-dir'])
    msg_output = MsgOutput()
    http_stats_output = HttpStatsOutput()
    receiver.add_listener(http_stats_output.process_message)
    receiver.add_listener(msg_output.process_message)
    receiver.add_listener(recorder.process_message)
    receiver.add_raw_listener(collector.process_raw_message)


def _start_web_in_thread(opts):
    address = opts['--web-address']
    kwargs = {'port': 9301}
    if address.startswith('['):
            # IPV6 [host]:port
        if ']:' in address:
            host, port = address.split(']:')
            kwargs['host'] = host[1:]
            kwargs['port'] = int(port)
        else:
            kwargs['host'] = address[1:-1]
    elif address.count(':') == 1:
        host, port = address.split(':')
        kwargs['host'] = host
        kwargs['port'] = int(port)
    else:
        kwargs['host'] = address
    t = threading.Thread(target=app.run, name='mite.web', kwargs=kwargs)
    t.daemon = True
    t.start()


def _create_config_manager(opts):
    config_manager = ConfigManager()
    config = spec_import(opts['--config'])()
    for k, v in config.items():
        config_manager.set(k, v)
    return config_manager


def _create_runner(opts, transport, msg_senders):
    loop_wait_max = float(opts['--max-loop-delay'])
    max_work = None
    if opts['--runner-max-journeys']:
        max_work = int(opts['--runner-max-journeys'])
    return Runner(transport, msg_senders, loop_wait_max=loop_wait_max,
                  max_work=max_work, debug=opts['--debugging'])


def _create_scenario_manager(opts):
    return ScenarioManager(start_delay=float(opts['--delay-start-seconds']), period=float(opts['--max-loop-delay']),
                           spawn_rate=int(opts['--spawn-rate']))


def test_scenarios(test_name, opts, scenarios):
    scenario_manager = _create_scenario_manager(opts)
    for journey_spec, datapool, volumemodel in scenarios:
        scenario_manager.add_scenario(journey_spec, datapool, volumemodel)
    config_manager = _create_config_manager(opts)
    controller = Controller(test_name, scenario_manager, config_manager)
    transport = DirectRunnerTransport(controller)
    receiver = DirectReciever()
    _setup_msg_processors(receiver, opts)
    loop = asyncio.get_event_loop()

    def controller_report():
        controller.report(receiver.recieve)
        loop.call_later(1, controller_report)
    loop.call_later(1, controller_report)
    loop.run_until_complete(_create_runner(opts, transport, receiver.recieve).run())


def scenario_test_cmd(opts):
    scenario_spec = opts['SCENARIO_SPEC']
    scenarios = spec_import(scenario_spec)()
    test_scenarios(scenario_spec, opts, scenarios)


def journey_test_cmd(opts):
    journey_spec = opts['JOURNEY_SPEC']
    datapool_spec = opts['DATAPOOL_SPEC']
    if datapool_spec:
        datapool = spec_import(datapool_spec)
    else:
        datapool = None
    volumemodel = lambda start, end: int(opts['--volume'])
    test_scenarios(journey_spec, opts, [(journey_spec, datapool, volumemodel)])


def scenario_cmd(opts):
    if opts['test']:
        scenario_test_cmd(opts)


def journey_cmd(opts):
    if opts['test']:
        journey_test_cmd(opts)


def controller(opts):
    scenario_spec = opts['SCENARIO_SPEC']
    scenarios = spec_import(scenario_spec)()
    scenario_manager = _create_scenario_manager(opts)
    for journey_spec, datapool, volumemodel in scenarios:
        scenario_manager.add_scenario(journey_spec, datapool, volumemodel)
    config_manager = _create_config_manager(opts)
    controller = Controller(scenario_spec, scenario_manager, config_manager)
    server = _create_controller_server(opts)
    sender = _create_sender(opts)
    loop = asyncio.get_event_loop()

    def controller_report():
        controller.report(sender.send)
        loop.call_later(1, controller_report)
    loop.call_later(1, controller_report)
    loop.run_until_complete(server.run(controller, controller.should_stop))


def runner(opts):
    transport = _create_runner_transport(opts)
    sender = _create_sender(opts)
    asyncio.get_event_loop().run_until_complete(_create_runner(opts, transport, sender.send).run())


def collector(opts):
    receiver = _collector_receiver(opts)
    collector = Collector(opts['--collector-dir'], int(opts['--collector-roll']))
    receiver.add_raw_listener(collector.process_raw_message)
    asyncio.get_event_loop().run_until_complete(receiver.run())


def recorder(opts):
    receiver = _recorder_receiver(opts)
    recorder = Recorder(opts['--recorder-dir'])
    receiver.add_listener(recorder.process_message)
    asyncio.get_event_loop().run_until_complete(receiver.run())


def duplicator(opts):
    duplicator = _create_duplicator(opts)
    asyncio.get_event_loop().run_until_complete(duplicator.run())


def stats(opts):
    receiver = _create_stats_receiver(opts)
    agg_sender = _create_stats_sender(opts)
    stats = Stats(sender=agg_sender.send)
    receiver.add_listener(stats.process)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(receiver.run())


def prometheus_exporter(opts):
    receiver = _create_prometheus_exporter_receiver(opts)
    receiver.add_listener(prometheus_metrics.process)
    _start_web_in_thread(opts)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(receiver.run())


def setup_logging(opts):
    logging.basicConfig(
        level=opts['--log-level'],
        format='[%(asctime)s] <%(levelname)s> [%(name)s] [%(pathname)s:%(lineno)d %(funcName)s] %(message)s')


def configure_python_path(opts):
    if not opts['--exclude-working-directory']:
        sys.path.insert(0, os.getcwd())


def har_converter(opts):
    har_convert_to_mite(opts['HAR_FILE_PATH'], opts['CONVERTED_FILE_PATH'], opts['--sleep-time'])


def main():
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    opts = docopt.docopt(__doc__)
    setup_logging(opts)
    configure_python_path(opts)
    if opts['scenario']:
        scenario_cmd(opts)
    elif opts['journey']:
        journey_cmd(opts)
    elif opts['controller']:
        controller(opts)
    elif opts['runner']:
        runner(opts)
    elif opts['collector']:
        collector(opts)
    elif opts['duplicator']:
        duplicator(opts)
    elif opts['stats']:
        stats(opts)
    elif opts['prometheus_exporter']:
        prometheus_exporter(opts)
    elif opts['recorder']:
        recorder(opts)
    elif opts['har']:
        har_converter(opts)


if __name__ == '__main__':
    main()
