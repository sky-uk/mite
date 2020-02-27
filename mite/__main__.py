"""\
Mite Load Test Framework.

Usage:
    mite [options] scenario test [--add-to-config=NEW_VALUE]... [--message-processors=PROCESSORS] SCENARIO_SPEC
    mite [options] journey test [--add-to-config=NEW_VALUE]... [--message-processors=PROCESSORS] JOURNEY_SPEC [DATAPOOL_SPEC]
    mite [options] controller SCENARIO_SPEC [--message-socket=SOCKET] [--controller-socket=SOCKET] [--logging-webhook=URL] [--add-to-config=NEW_VALUE]...
    mite [options] runner [--message-socket=SOCKET] [--controller-socket=SOCKET]
    mite [options] duplicator [--message-socket=SOCKET] OUT_SOCKET...
    mite [options] collector [--collector-socket=SOCKET]
    mite [options] recorder [--recorder-socket=SOCKET]
    mite [options] stats [--stats-in-socket=SOCKET] [--stats-out-socket=SOCKET]
    mite [options] prometheus_exporter [--stats-out-socket=SOCKET] [--web-address=HOST_PORT]
    mite [options] har HAR_FILE_PATH CONVERTED_FILE_PATH [--sleep-time=SLEEP]
    mite [options] cat MSGPACK_FILE_PATH

    mite --help
    mite --version

Arguments:
    SCENARIO_SPEC           Identifier for a scenario in the form package_path:callable_name
    CONFIG_SPEC             Identifier for config callable returning dict of config
    JOURNEY_SPEC            Identifier for journey async callable
    VOLUME_MODEL_SPEC       Identifier for volume model callable
    HAR_FILE_PATH           Path for the har file to convert into a mite journey
    CONVERTED_FILE_PATH     Path to write the converted mite script to when coverting a har file

Examples:
    mite scenario test mite.example:scenario

Options:
    -h --help                         Show this screen
    --version                         Show version
    --debugging                       Drop into IPDB on journey error and exit
    --log-level=LEVEL                 Set logger level, one of DEBUG, INFO, WARNING, ERROR, CRITICAL [default: INFO]
    --config=CONFIG_SPEC              Set a config loader to a callable loaded via a spec [default: mite.config:default_config_loader]
    --add-to-config=NEW_VALUE         Add a key:value to the config map, in addition to what's loaded from a file
    --spawn-rate=NUM_PER_SECOND       Maximum spawn rate [default: 1000]
    --max-loop-delay=SECONDS          Runner internal loop delay maximum [default: 1]
    --min-loop-delay=SECONDS          Runner internal loop delay minimum [default: 0]
    --runner-max-journeys=NUMBER      Max number of concurrent journeys a runner can run
    --controller-socket=SOCKET        Controller socket [default: tcp://127.0.0.1:14301]
    --message-socket=SOCKET           Message socket [default: tcp://127.0.0.1:14302]
    --collector-socket=SOCKET         Socket [default: tcp://127.0.0.1:14303]
    --stats-in-socket=SOCKET          Socket [default: tcp://127.0.0.1:14304]
    --stats-out-socket=SOCKET         Socket [default: tcp://127.0.0.1:14305]
    --recorder-socket=SOCKET          Socket [default: tcp://127.0.0.1:14306]
    --delay-start-seconds=DELAY       Delay start allowing others to connect [default: 0]
    --volume=VOLUME                   Volume to run journey at [default: 1]
    --web-address=HOST_PORT           Web bind address [default: 127.0.0.1:9301]
    --message-backend=BACKEND         Backend to transport messages over [default: ZMQ]
    --exclude-working-directory       By default mite puts the current directory on the python path
    --collector-dir=DIRECTORY         Set the collectors output directory [default: collector_data]
    --collector-roll=NUM_LINES        How many lines per collector output file [default: 100000]
    --recorder-dir=DIRECTORY          Set the recorders output directory [default: recorder_data]
    --sleep-time=SLEEP                Set the second to await between each request [default: 1]
    --logging-webhook=URL             URL of an HTTP server to log test runs to
    --message-processors=PROCESSORS   Classes to connect to the message bus for local testing [default: mite.logoutput:HttpStatsOutput,mite.logoutput:MsgOutput]
"""
import asyncio
import logging
import os
import sys
import threading

import docopt
import msgpack

import uvloop

from .cli.common import _create_runner, _create_sender
from .cli.controller import controller
from .cli.duplicator import duplicator
from .cli.stats import stats
from .cli.test import journey_cmd, scenario_cmd
from .collector import Collector
from .har_to_mite import har_convert_to_mite
from .recorder import Recorder
from .utils import _msg_backend_module
from .web import app, prometheus_metrics


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


def _create_prometheus_exporter_receiver(opts):
    socket = opts['--stats-out-socket']
    receiver = _msg_backend_module(opts).Receiver()
    receiver.bind(socket)
    return receiver


def _create_runner_transport(opts):
    socket = opts['--controller-socket']
    return _msg_backend_module(opts).RunnerTransport(socket)


logger = logging.getLogger(__name__)


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


def runner(opts):
    transport = _create_runner_transport(opts)
    sender = _create_sender(opts)
    asyncio.get_event_loop().run_until_complete(
        _create_runner(opts, transport, sender.send).run()
    )


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


def cat(opts):
    with open(opts['MSGPACK_FILE_PATH'], 'rb') as file_in:
        unpacker = msgpack.Unpacker(file_in, encoding='utf-8', use_list=False)
        for row in unpacker:
            print(row)


def prometheus_exporter(opts):
    receiver = _create_prometheus_exporter_receiver(opts)
    receiver.add_listener(prometheus_metrics.process)
    _start_web_in_thread(opts)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(receiver.run())


def setup_logging(opts):
    logging.basicConfig(
        level=opts['--log-level'],
        format='[%(asctime)s] <%(levelname)s> [%(name)s] [%(pathname)s:%(lineno)d %(funcName)s] %(message)s',
    )


def configure_python_path(opts):
    if not opts['--exclude-working-directory']:
        sys.path.insert(0, os.getcwd())


def har_converter(opts):
    har_convert_to_mite(
        opts['HAR_FILE_PATH'], opts['CONVERTED_FILE_PATH'], opts['--sleep-time']
    )


def main():
    if os.environ.get("MITE_PROFILE", "0") != "1":
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
    elif opts['cat']:
        cat(opts)


if __name__ == '__main__':
    main()
