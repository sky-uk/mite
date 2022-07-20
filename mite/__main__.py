"""\
Mite Load Test Framework.

Usage:
    mite [options] scenario test [--add-to-config=NEW_VALUE]... [--message-processors=PROCESSORS] [--memory-tracing] SCENARIO_SPEC
    mite [options] journey test [--add-to-config=NEW_VALUE]... [--message-processors=PROCESSORS] [--memory-tracing] JOURNEY_SPEC [DATAPOOL_SPEC]
    mite [options] journey run [--add-to-config=NEW_VALUE]... [--message-processors=PROCESSORS] JOURNEY_SPEC [DATAPOOL_SPEC]
    mite [options] controller SCENARIO_SPEC [--message-socket=SOCKET] [--controller-socket=SOCKET] [--logging-webhook=URL] [--add-to-config=NEW_VALUE]...
    mite [options] runner [--message-socket=SOCKET] [--controller-socket=SOCKET]
    mite [options] duplicator [--message-socket=SOCKET] OUT_SOCKET...
    mite [options] collector [--collector-socket=SOCKET] [--collector-filter=SPEC] [--collector-roll=NUM_LINES] [--collector-dir=DIRECTORY] [--collector-use-json]
    mite [options] recorder [--recorder-socket=SOCKET]
    mite [options] stats [--stats-in-socket=SOCKET] [--stats-out-socket=SOCKET] [--stats-include-processors=PROCESSORS] [--stats-exclude-processors=PROCESSORS]
    mite [options] receiver RECEIVE_SOCKET [--processor=PROCESSOR]...
    mite [options] prometheus_exporter [--stats-out-socket=SOCKET] [--web-address=HOST_PORT]
    mite [options] har HAR_FILE_PATH CONVERTED_FILE_PATH [--sleep-time=SLEEP]
    mite [options] cat [--prettify-timestamps] MSGPACK_FILE_PATH
    mite [options] uncat

    mite --help
    mite --version

Arguments:
    SCENARIO_SPEC           Identifier for a scenario in the form package_path:callable_name
    CONFIG_SPEC             Identifier for config callable returning dict of config
    JOURNEY_SPEC            Identifier for journey async callable
    VOLUME_MODEL_SPEC       Identifier for volume model callable
    HAR_FILE_PATH           Path for the har file to convert into a mite journey
    CONVERTED_FILE_PATH     Path to write the converted mite script to when converting a har file
    PROCESSOR               Class for message handling, must have either process_message or process_raw_message methods

Examples:
    # run the example scenario called "scenario"
    mite scenario test mite.example:scenario

    # run the example journey called "journey" and set the "test_msg" config variable to "Hello from mite"
    MITE_CONF_test_msg="Hello from mite" mite journey test mite.example:journey mite.example:datapool

    # run the example journey called "journey" and set the "test_msg" config variable to "Hello from mite" using
    # the --add-to-config switch
    mite journey test mite.example:journey mite.example:datapool --add-to-config=test_msg:"Hello from mite"

    # Individual mite components can be started in the following example manner
    # start a mite runner that is controlled by a mite controller on 10.11.12.13:14301 that outputs to
    # the controller on 14302
    mite runner --controller-socket=tcp://10.11.12.13:14301 --message-socket=tcp://10.11.12.13:14302

    # start a mite controller for the above runners
    mite controller mite.example:scenario --controller-socket=tcp://0.0.0.0:14301

    # start a mite duplicator that listens on 14302 and outputs on 14303 and 14304
    mite duplicator --message-socket=tcp://0.0.0.0:14302 tcp://127.0.0.1:14303 tcp://127.0.0.1:14304

    # start mite stats
    mite stats --stats-in-socket=tcp://0.0.0.0:14303 --stats-out-socket=tcp://0.0.0.0:14305


Options:
    -h --help                               Show this screen
    --version                               Show version
    --debugging                             Drop into debugger (pdb) on journey error and exit.  Select debugger with PYTHONBREAKPOINT and PYTHONPOSTMORTEM
    --memory-tracing                        Print heap alloc diffs every 60 seconds
    --log-level=LEVEL                       Set logger level, one of DEBUG, INFO, WARNING, ERROR, CRITICAL [default: INFO]
    --config=CONFIG_SPEC                    Set a config loader to a callable loaded via a spec [default: mite.config:default_config_loader]
    --add-to-config=NEW_VALUE               Add a key:value to the config map, in addition to what's loaded from a file
    --spawn-rate=NUM_PER_SECOND             Maximum spawn rate [default: 1000]
    --max-loop-delay=SECONDS                Runner internal loop delay maximum [default: 1]
    --min-loop-delay=SECONDS                Runner internal loop delay minimum [default: 0]
    --runner-max-journeys=NUMBER            Max number of concurrent journeys a runner can run
    --controller-socket=SOCKET              Controller socket [default: tcp://127.0.0.1:14301]
    --message-socket=SOCKET                 Message socket [default: tcp://127.0.0.1:14302]
    --collector-socket=SOCKET               Socket [default: tcp://127.0.0.1:14303]
    --stats-in-socket=SOCKET                Socket [default: tcp://127.0.0.1:14304]
    --stats-out-socket=SOCKET               Socket [default: tcp://127.0.0.1:14305]
    --stats-include-processors=PROCESSORS   Stats processor names to include, as a comma separated list (no spaces)
    --stats-exclude-processors=PROCESSORS   Stats processor names to exclude, as a comma separated list (no spaces)
    --recorder-socket=SOCKET                Socket [default: tcp://127.0.0.1:14306]
    --delay-start-seconds=DELAY             Delay start allowing others to connect [default: 0]
    --volume=VOLUME                         Volume to run journey at [default: 1]
    --web-address=HOST_PORT                 Web bind address [default: 127.0.0.1:9301]
    --message-backend=BACKEND               Backend to transport messages over [default: ZMQ]
    --exclude-working-directory             By default mite puts the current directory on the python path
    --collector-dir=DIRECTORY               Set the collectors output directory [default: collector_data]
    --collector-filter=SPEC                 Function spec to filter messages collected by the collector
    --collector-roll=NUM_LINES              How many lines per collector output file [default: 100000]
    --collector-use-json                    Output in json format rather than msgpack
    --recorder-dir=DIRECTORY                Set the recorders output directory [default: recorder_data]
    --sleep-time=SLEEP                      Set the second to await between each request [default: 1]
    --logging-webhook=URL                   URL of an HTTP server to log test runs to
    --message-processors=PROCESSORS         Classes to connect to the message bus for local testing [default: mite.logoutput:HttpStatsOutput,mite.logoutput:MsgOutput]
    --prettify-timestamps                   Reformat unix timestamps to human readable dates
    --journey-logging                       Log errors on a per journey basis
    --max-errors-threshold=THRESHOLD        Set the maximum number of errors accepted before setting exit status to 1 [default: 0]
"""
import asyncio
import logging
import os
import sys
import threading
from urllib.request import Request as UrlLibRequest
from urllib.request import urlopen

import docopt
import ujson
import uvloop

from .cli import receiver, stats
from .cli.cat import cat, uncat
from .cli.collector import collector
from .cli.common import (
    _create_config_manager,
    _create_runner,
    _create_scenario_manager,
    _create_sender,
    _get_scenario_with_kwargs,
)
from .cli.duplicator import duplicator
from .cli.test import journey_cmd, scenario_cmd
from .controller import Controller
from .har_to_mite import har_convert_to_mite
from .recorder import Recorder
from .utils import _msg_backend_module
from .web import app, prometheus_metrics


def _recorder_receiver(opts):
    socket = opts["--recorder-socket"]
    receiver = _msg_backend_module(opts).Receiver()
    receiver.connect(socket)
    return receiver


def _create_prometheus_exporter_receiver(opts):
    socket = opts["--stats-out-socket"]
    receiver = _msg_backend_module(opts).Receiver()
    receiver.bind(socket)
    return receiver


def _create_runner_transport(opts):
    socket = opts["--controller-socket"]
    return _msg_backend_module(opts).RunnerTransport(socket)


def _create_controller_server(opts):
    socket = opts["--controller-socket"]
    return _msg_backend_module(opts).ControllerServer(socket)


logger = logging.getLogger(__name__)


def _start_web_in_thread(opts):
    address = opts["--web-address"]
    kwargs = {"port": 9301}
    if address.startswith("["):
        # IPV6 [host]:port
        if "]:" in address:
            host, port = address.split("]:")
            kwargs["host"] = host[1:]
            kwargs["port"] = int(port)
        else:
            kwargs["host"] = address[1:-1]
    elif address.count(":") == 1:
        host, port = address.split(":")
        kwargs["host"] = host
        kwargs["port"] = int(port)
    else:
        kwargs["host"] = address
    t = threading.Thread(target=app.run, name="mite.web", kwargs=kwargs)
    t.daemon = True
    t.start()


def _controller_log_start(scenario_spec, logging_url):
    if not logging_url.endswith("/"):
        logging_url += "/"

    # The design decision has been made to do this logging synchronously
    # rather than using the usual mite data pipeline, because we want to make
    # sure the log is nailed down before we start doing any test activity.
    url = f"{logging_url}start"
    logger.info(f"Logging test start to {url}")
    resp = urlopen(
        UrlLibRequest(
            url,
            data=ujson.dumps(
                {
                    "testname": scenario_spec,
                    # TODO: log other properties as well,
                    # like the endpoint URLs we are
                    # hitting.
                }
            ).encode(),
            method="POST",
        )
    )
    logger.debug("Logging test start complete")
    if resp.status == 200:
        return ujson.loads(resp.read())["newid"]
    else:
        logger.warning(
            f"Could not complete test start logging; status was {resp.status_code}"
        )


def _controller_log_end(logging_id, logging_url):
    if logging_id is None:
        return

    if not logging_url.endswith("/"):
        logging_url += "/"

    url = f"{logging_url}end"
    logger.info(f"Logging test end to {url}")
    resp = urlopen(UrlLibRequest(url, data=ujson.dumps({"id": logging_id}).encode()))
    if resp.status != 204:
        logger.warning(
            f"Could not complete test end logging; status was {resp.status_code}"
        )
    logger.debug("Logging test end complete")


def controller(opts):
    config_manager = _create_config_manager(opts)
    scenario_spec = opts["SCENARIO_SPEC"]
    scenario_manager = _create_scenario_manager(opts)
    sender = _create_sender(opts)
    scenarios = _get_scenario_with_kwargs(scenario_spec, config_manager, sender)
    for journey_spec, datapool, volumemodel in scenarios:
        scenario_manager.add_scenario(journey_spec, datapool, volumemodel)
    # Done setting up scenarios
    controller = Controller(scenario_spec, scenario_manager, config_manager)
    server = _create_controller_server(opts)
    loop = asyncio.get_event_loop()
    logging_id = None
    logging_url = opts["--logging-webhook"]
    if logging_url is None:
        try:
            logging_url = os.environ["MITE_LOGGING_URL"]
        except KeyError:
            pass
    if logging_url is not None:
        logging_id = _controller_log_start(scenario_spec, logging_url)

    async def controller_report():
        while True:
            if controller.should_stop():
                return
            await asyncio.sleep(1)
            controller.report(sender.send)

    try:
        loop.run_until_complete(
            asyncio.gather(
                controller_report(), server.run(controller, controller.should_stop)
            )
        )
    except KeyboardInterrupt:
        # TODO: kill runners, do other shutdown tasks
        logging.info("Received interrupt signal, shutting down")
    finally:
        _controller_log_end(logging_id, logging_url)
        # TODO: cancel all loop tasks?  Something must be done to stop this
        # from hanging
        loop.close()


def runner(opts):
    transport = _create_runner_transport(opts)
    sender = _create_sender(opts)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_create_runner(opts, transport, sender.send).run())
    # Under rare conditions, we've seen a race condition on the runner's exit
    # that leads to an exception like:
    # RuntimeError: Event loop stopped before Future completed.
    # I think this comes about becasue of a race where the callback scheduled
    # by RunnerTransport.bye does not get serviced before the above
    # run_until_complete returns.  I'm mystified as to how this can occur
    # (because bye awaits the callback, so it should complete....)
    # Nonetheless, the exception happens, and I believe that this is the
    # cause.  So, this is an attempt to defend against that error case.  We
    # give the loop 5 seconds to complete any network ops that are outstanding
    # before calling the close method which will cancel any scheduled
    # callbacks and should ensure that the porgrma exits cleanly.
    loop.run_until_complete(asyncio.sleep(5))
    loop.close()


def recorder(opts):
    receiver = _recorder_receiver(opts)
    recorder = Recorder(opts["--recorder-dir"])
    receiver.add_listener(recorder.process_message)
    asyncio.get_event_loop().run_until_complete(receiver.run())


def prometheus_exporter(opts):
    receiver = _create_prometheus_exporter_receiver(opts)
    receiver.add_listener(prometheus_metrics.process)
    _start_web_in_thread(opts)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(receiver.run())


def setup_logging(opts):
    logging.basicConfig(
        level=opts["--log-level"],
        format="[%(asctime)s] <%(levelname)s> [%(name)s] [%(pathname)s:%(lineno)d %(funcName)s] %(message)s",
    )


def configure_python_path(opts):
    if not opts["--exclude-working-directory"]:
        sys.path.insert(0, os.getcwd())


def har_converter(opts):
    har_convert_to_mite(
        opts["HAR_FILE_PATH"], opts["CONVERTED_FILE_PATH"], opts["--sleep-time"]
    )


def main():
    if os.environ.get("MITE_PROFILE", "0") != "1":
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    opts = docopt.docopt(__doc__)
    setup_logging(opts)
    configure_python_path(opts)
    if opts["scenario"]:
        scenario_cmd(opts)
    elif opts["journey"]:
        journey_cmd(opts)
    elif opts["controller"]:
        controller(opts)
    elif opts["runner"]:
        runner(opts)
    elif opts["collector"]:
        collector(opts)
    elif opts["duplicator"]:
        duplicator(opts)
    elif opts["stats"]:
        stats.stats(opts)
    elif opts["receiver"]:
        receiver.generic_receiver(opts)
    elif opts["prometheus_exporter"]:
        prometheus_exporter(opts)
    elif opts["recorder"]:
        recorder(opts)
    elif opts["har"]:
        har_converter(opts)
    elif opts["cat"]:
        cat(opts)
    elif opts["uncat"]:
        uncat(opts)


if __name__ == "__main__":
    main()
