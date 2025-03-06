import asyncio
import gc
import logging
import sys
import time
import tracemalloc

from prettytable import PrettyTable

from mite.datapools import SingleRunDataPoolWrapper
from mite.logoutput import DebugMessageOutput, HttpStatsOutput

from ..collector import Collector
from ..controller import Controller
from ..recorder import Recorder
from ..utils import pack_msg, spec_import
from ..volume_model import oneshot_vm
from .common import (
    _create_config_manager,
    _create_runner,
    _create_scenario_manager,
    _create_sender,
    _get_scenario_with_kwargs,
)


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
                lambda listener: isinstance(listener.__self__, clazz),
                self._listeners,
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
    collector = Collector(opts["--collector-dir"], int(opts["--collector-roll"]))
    recorder = Recorder(opts["--recorder-dir"])
    receiver.add_listener(recorder.process_message)
    receiver.add_raw_listener(collector.process_raw_message)

    extra_processors = [
        spec_import(x)(opts) for x in opts["--message-processors"].split(",") if x
    ]
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
    return listeners[0].__self__ if len(listeners) == 1 else None


def print_diff(snapshot1, snapshot2):
    top_stats = snapshot2.compare_to(snapshot1, "lineno")
    printed = 0
    for stat in top_stats:
        if any(
            x in stat.traceback._frames[0][0]
            for x in ("linecache.py", "traceback.py", "tracemalloc.py")
        ):
            continue
        print(stat)
        printed += 1
        if printed > 10:
            break


async def mem_snapshot(initial_snapshot, interval=60):
    last_snapshot = None
    snapshot = None
    while True:
        await asyncio.sleep(interval)
        last_snapshot = snapshot
        gc.collect()
        snapshot = tracemalloc.take_snapshot()
        print("Differences from initial:")
        print_diff(initial_snapshot, snapshot)
        if last_snapshot is not None:
            print("Differences from last:")
            print_diff(last_snapshot, snapshot)


async def controller_report(controller, receiver):
    while True:
        await asyncio.sleep(1)
        controller.report(receiver.recieve)


def time_unit_format(number):
    return f"{number * 1000:.2f}ms" if number < 1 else f"{number:.3f}s"


def test_scenarios(test_name, opts, scenarios, config_manager):
    scenario_manager = _create_scenario_manager(opts)
    for journey_spec, datapool, volumemodel in scenarios:
        scenario_manager.add_scenario(journey_spec, datapool, volumemodel)
    controller = Controller(test_name, scenario_manager, config_manager)
    transport = DirectRunnerTransport(controller)
    receiver = DirectReciever()
    debug_message_output = DebugMessageOutput(opts)
    receiver.add_listener(debug_message_output.process_message)
    _setup_msg_processors(receiver, opts)
    http_stats_output = _get_http_stats_output(receiver)
    loop = asyncio.get_event_loop()
    if opts["--debugging"]:
        loop.set_debug(True)

    tasks = [
        loop.create_task(controller_report(controller, receiver)),
        loop.create_task(_create_runner(opts, transport, receiver.recieve).run()),
    ]

    if opts["--memory-tracing"]:
        tracemalloc.start()
        initial_snapshot = tracemalloc.take_snapshot()
        tasks.append(loop.create_task(mem_snapshot(initial_snapshot)))

    loop.run_until_complete(asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED))

    http_stats_output._scenarios_completed_time = time.time()

    # Run one last report before exiting
    controller.report(receiver.recieve)
    has_error = False

    if int(opts.get("--max-errors-threshold")) < http_stats_output.error_total:
        has_error = True
        logging.error("Error count exceeded: %s", http_stats_output.error_total)

    if opts.get("--max-response-time-threshold") != "0":
        max_response_time = http_stats_output._resp_time_max * 1000
        if max_response_time > int(opts["--max-response-time-threshold"]):
            has_error = True
            logging.error("Max response time exceeded: %sms", max_response_time)

    if opts.get("--mean-response-time-threshold") != "0":
        mean_response_time = http_stats_output.mean_resp_time * 1000
        if mean_response_time > int(opts["--mean-response-time-threshold"]):
            has_error = True
            logging.error("Mean response time exceeded: %sms", mean_response_time)

    if opts.get("--standard-deviation-response-time-threshold") != "0":
        resp_time_stddev = http_stats_output.resp_time_standard_deviation * 1000
        if resp_time_stddev > int(opts["--standard-deviation-response-time-threshold"]):
            has_error = True
            logging.error(
                "Response time standard deviation exceeded: %sms", resp_time_stddev
            )

    if opts.get("--standard-deviation-req-sec-threshold") != "0":
        req_sec_stddev = http_stats_output.req_sec_standard_deviation
        if req_sec_stddev > int(opts["--standard-deviation-req-sec-threshold"]):
            has_error = True
            logging.error("Request per second exceeded: %s", req_sec_stddev)

    if opts.get("--report"):
        benchmark_report(http_stats_output)
        for (
            percentile,
            threshold,
            result,
        ) in http_stats_output.percentiles_list_resp_time_store:
            if threshold != 0 and result * 1000 >= threshold:
                has_error = True
                logging.error(
                    f"Response time at {percentile}th percentile exceeded {threshold}ms: {time_unit_format(result)}"
                )

    # Ensure any open files get closed
    del receiver._raw_listeners
    del receiver._listeners

    sys.exit(int(has_error))


def human_readable_bytes(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return size, unit
        size /= 1024.0
    return size, "PB"


def colorise_result(result, threshold):
    formatted_result = time_unit_format(result)
    if threshold != 0:
        result_ms = result * 1000
        if result_ms >= threshold:
            return f"\033[91m{formatted_result}\033[0m"  # red
        else:
            return f"\033[92m{formatted_result}\033[0m"  # green
    return formatted_result


def benchmark_report(http_stats_output):
    perctile_thresh_results_list = http_stats_output.percentiles_list_resp_time_store

    percentiles_headers = [
        f"{int(percentile[0])} %tile" for percentile in perctile_thresh_results_list
    ]
    standard_headers = ["", "Avg", "Min", "Max", "Std Dev", "+/- Std Dev"]

    latency_table = PrettyTable()
    latency_table.field_names = standard_headers + percentiles_headers

    latency_table.add_row(
        [
            "Latency",
            time_unit_format(http_stats_output.mean_resp_time),
            time_unit_format(http_stats_output._resp_time_min),
            time_unit_format(http_stats_output._resp_time_max),
            time_unit_format(http_stats_output.resp_time_standard_deviation),
            f"{http_stats_output.resp_time_within_standard_deviation:.2f}%",
            *[
                colorise_result(result, threshold)
                for _, threshold, result in perctile_thresh_results_list
            ],
        ],
        divider=True,
    )

    if any(threshold[1] != 0 for threshold in perctile_thresh_results_list):
        latency_table.add_row(
            [
                "Test Thresholds",
                *["-" for _ in range(len(standard_headers) - 1)],
                *[
                    f"{threshold[1]}ms" if threshold[1] != 0 else "-"
                    for threshold in perctile_thresh_results_list
                ],
            ],
        )

    requests_table = PrettyTable()
    requests_table.field_names = standard_headers
    number_format = (
        lambda number: f"{number / 1000:.2f}K" if number >= 1000 else f"{number:.2f}"
    )
    requests_table.add_row(
        [
            "Req/Sec",
            number_format(http_stats_output.req_sec_mean),
            number_format(http_stats_output._req_sec_min),
            number_format(http_stats_output._req_sec_max),
            number_format(http_stats_output.req_sec_standard_deviation),
            f"{http_stats_output.req_sec_within_standard_deviation:.2f}%",
        ]
    )

    data_transfer, data_unit = human_readable_bytes(http_stats_output._data_transferred)
    print("\n" + "=" * 20 + " MITE Benchmark Report " + "=" * 20, end="\n\n")
    print(latency_table, end="\n\n")
    print(requests_table, end="\n\n")
    print("=" * 27 + " Summary " + "=" * 27)
    print(
        f"{http_stats_output._req_total} requests in {http_stats_output._scenarios_completed_time - http_stats_output._init_time:.2f}s, {data_transfer:.2f} {data_unit} data transferred",
        end="\n\n",
    )


def scenario_test_cmd(opts):
    scenario_spec = opts["SCENARIO_SPEC"]
    config_manager = _create_config_manager(opts)
    sender = _create_sender(opts)
    scenarios = _get_scenario_with_kwargs(scenario_spec, config_manager, sender)
    test_scenarios(scenario_spec, opts, scenarios, config_manager)


def journey_test_cmd(opts):
    journey_spec = opts["JOURNEY_SPEC"]
    if datapool_spec := opts["DATAPOOL_SPEC"]:
        datapool = spec_import(datapool_spec)
    else:
        datapool = None
    volumemodel = lambda start, end: int(opts["--volume"])
    test_scenarios(
        journey_spec,
        opts,
        [(journey_spec, datapool, volumemodel)],
        _create_config_manager(opts),
    )


def journey_run_cmd(opts):
    journey_spec = opts["JOURNEY_SPEC"]
    if datapool_spec := opts["DATAPOOL_SPEC"]:
        datapool = SingleRunDataPoolWrapper(spec_import(datapool_spec))
    else:
        datapool = None
    volume_model = oneshot_vm(stop_scenario=True)
    test_scenarios(
        journey_spec,
        opts,
        [(journey_spec, datapool, volume_model)],
        _create_config_manager(opts),
    )


def scenario_cmd(opts):
    if opts["test"]:
        scenario_test_cmd(opts)


def journey_cmd(opts):
    if opts["test"]:
        journey_test_cmd(opts)
    elif opts["run"]:
        journey_run_cmd(opts)
