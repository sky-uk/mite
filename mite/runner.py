import asyncio
import functools
import logging
import inspect
from itertools import count

import ipdb

from .context import Context
from .utils import spec_import

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=None)
def spec_import_cached(journey_spec):
    return spec_import(journey_spec)


class RunnerControllerTransportExample:  # pragma: nocover
    async def hello(self):
        """Returns:
            runner_id
            test_name
            config_list - k, v pairs
            """
        pass

    async def request_work(self, runner_id, current_work, completed_data_ids, max_work):
        """\
        Takes:
            runner_id
            current_work - dict of scenario_id, current volume
            completed_data_ids - list of scenario_id, scenario_data_id pairs
            max_work - may be None to indicate no limit
        Returns:
            work - list of (scenario_id, scenario_data_id,
                            journey_spec, args) - args and scenario_data_id may be None together
            config_list - k, v pairs
            stop
        """
        pass

    async def bye(self, runner_id):
        """\
        Takes:
            runner_id
        """
        pass


class RunLoopLogger:

    def __init__(self):
        self._enabled = False
        self._condition = None
        # Add an index to the log lines, allowing some manual
        # ordering of the output in kibana
        self._idx = count(1)

    def enable(self, condition):
        self._enabled = True
        self._condition = condition

    def __call__(self):
        if self._enabled and self._condition():
            caller = inspect.stack()[1]
            logger.info(f"{next(self._idx)}: {caller.function}:{caller.lineno}")


class Runner:
    def __init__(
        self,
        transport,
        msg_sender,
        loop_wait_min=0.01,
        loop_wait_max=0.5,
        max_work=None,
        loop=None,
        debug=False,
    ):
        self._transport = transport
        self._msg_sender = msg_sender
        self._work = {}
        self._datapool_proxies = {}
        self._stop = False
        self._loop_wait_min = loop_wait_min
        self._loop_wait_max = loop_wait_max
        self._max_work = max_work
        if loop is None:
            loop = asyncio.get_event_loop()
        self._loop = loop
        self._debug = debug

    def _inc_work(self, id):
        if id in self._work:
            self._work[id] += 1
        else:
            self._work[id] = 1

    def _dec_work(self, id):
        self._work[id] -= 1
        if self._work[id] == 0:
            del self._work[id]

    def _current_work(self):
        return self._work

    def should_stop(self):
        return self._stop

    async def run(self):
        context_id_gen = count(1)
        config = {}
        runner_id, test_name, config_list = await self._transport.hello()
        config.update(config_list)
        logger.debug("Entering run loop")
        _completed = []
        journey_specs_by_scenario_id = {}
        __RUN_LOOP_LOG = RunLoopLogger()

        def on_completion(f):
            nonlocal waiter, _completed
            # logger.info("Received completion notice for scenario_id " + str(f.result()[0]))
            _completed.append(f)
            __RUN_LOOP_LOG()
            if not waiter.done():
                __RUN_LOOP_LOG()
                waiter.set_result(None)
            __RUN_LOOP_LOG()

        def stop_waiting():
            nonlocal waiter
            __RUN_LOOP_LOG()
            if not waiter.done():
                __RUN_LOOP_LOG()
                waiter.set_result(None)
            __RUN_LOOP_LOG()

        async def wait():
            nonlocal waiter, timeout_handle, _completed
            __RUN_LOOP_LOG()
            await waiter
            __RUN_LOOP_LOG()
            timeout_handle.cancel()
            __RUN_LOOP_LOG()
            timeout_handle = self._loop.call_later(self._loop_wait_max, stop_waiting)
            __RUN_LOOP_LOG()
            waiter = self._loop.create_future()
            c = []
            __RUN_LOOP_LOG()
            for f in _completed:
                __RUN_LOOP_LOG()
                scenario_id, scenario_data_id = f.result()
                __RUN_LOOP_LOG()
                self._dec_work(scenario_id)
                if scenario_data_id is not None:
                    c.append((scenario_id, scenario_data_id))
            del _completed[:]
            return c

        timeout_handle = self._loop.call_later(self._loop_wait_max, stop_waiting)
        waiter = self._loop.create_future()
        completed_data_ids = []
        while not self._stop:
            work, config_list, self._stop = await self._transport.request_work(
                runner_id, self._current_work(), completed_data_ids, self._max_work
            )
            config.update(config_list)
            for num, (scenario_id, scenario_data_id, journey_spec, args) in enumerate(
                work
            ):
                id_data = {
                    'test': test_name,
                    'runner_id': runner_id,
                    'journey': journey_spec,
                    'context_id': next(context_id_gen),
                    'scenario_id': scenario_id,
                    'scenario_data_id': scenario_data_id,
                }
                context = Context(
                    self._msg_sender,
                    config,
                    id_data=id_data,
                    should_stop_func=self.should_stop,
                    debug=self._debug,
                )
                journey_specs_by_scenario_id[scenario_id] = journey_spec
                # logger.info("Starting scenario_id " + str(scenario_id))
                self._inc_work(scenario_id)
                future = asyncio.ensure_future(
                    self._execute(
                        context, scenario_id, scenario_data_id, journey_spec, args
                    )
                )
                future.add_done_callback(on_completion)
            completed_data_ids = await wait()
        logger.info("Waiting for work completion")
        __RUN_LOOP_LOG.enable(lambda: sum(self._current_work().values()) < 4)
        self._loop.set_debug(True)
        while self._current_work():
            logger.info(
                "Waiting on "
                + ", ".join(
                    [
                        "|".join(
                            (
                                str(journey_specs_by_scenario_id[sc_id]),
                                str(sc_id),
                                str(count),
                            )
                        )
                        for sc_id, count in self._current_work().items()
                    ]
                )
            )
            __RUN_LOOP_LOG()
            _, config_list, _ = await self._transport.request_work(
                runner_id, self._current_work(), completed_data_ids, 0
            )
            __RUN_LOOP_LOG()
            config.update(config_list)
            completed_data_ids = await wait()
            __RUN_LOOP_LOG()
        logger.info("All work completed")
        __RUN_LOOP_LOG()
        await self._transport.request_work(
            runner_id, self._current_work(), completed_data_ids, 0
        )
        __RUN_LOOP_LOG()
        await self._transport.bye(runner_id)
        __RUN_LOOP_LOG()

    async def _execute(self, context, scenario_id, scenario_data_id, journey_spec, args):
        logger.debug(
            'Runner._execute starting scenario_id=%r scenario_data_id=%r journey_spec=%r args=%r',
            scenario_id,
            scenario_data_id,
            journey_spec,
            args,
        )
        journey = spec_import_cached(journey_spec)
        try:
            async with context.transaction('__root__'):
                if args is None:
                    await journey(context)
                else:
                    await journey(context, *args)
        except Exception as e:
            if not getattr(e, "handled", False):
                if self._debug:
                    ipdb.set_trace()
                    raise
        return scenario_id, scenario_data_id
