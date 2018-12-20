import asyncio
from itertools import count
import logging

from .context import Context
from .utils import spec_import

logger = logging.getLogger(__name__)


class RunnerControllerTransportExample:
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


class RunnerConfig:
    def __init__(self):
        self._config = {}

    def __repr__(self):
        return "RunnerConfig({})".format(", ".join(["{}={}".format(k, v) for k, v in self._config.items()]))

    def _update(self, kv_list):
        for k, v in kv_list:
            self._config[k] = v

    def get(self, key, default=None):
        try:
            return self._config[key]
        except KeyError:
            if default is not None:
                return default
            else:
                raise

    def get_fallback(self, *keys, default=None):
        for key in keys:
            try:
                return self._config[key]
            except KeyError:
                pass
        if default is not None:
            return default
        raise KeyError("None of {} found".format(keys))


class Runner:
    def __init__(self, transport, msg_sender, loop_wait_min=0.01, loop_wait_max=0.5, max_work=None, loop=None,
                 debug=False):
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
        config = RunnerConfig()
        runner_id, test_name, config_list = await self._transport.hello()
        config._update(config_list)
        logger.debug("Entering run loop")
        _completed = []

        def on_completion(f):
            nonlocal waiter, _completed
            _completed.append(f)
            if not waiter.done():
                waiter.set_result(None)

        def stop_waiting():
            nonlocal waiter
            if not waiter.done():
                waiter.set_result(None)

        async def wait():
            nonlocal waiter, timeout_handle, _completed
            await waiter
            timeout_handle.cancel()
            timeout_handle = self._loop.call_later(self._loop_wait_max, stop_waiting)
            waiter = self._loop.create_future()
            c = []
            for f in _completed:
                scenario_id, scenario_data_id = f.result()
                self._dec_work(scenario_id)
                if scenario_data_id is not None:
                    c.append((scenario_id, scenario_data_id))
            del _completed[:]
            return c

        timeout_handle = self._loop.call_later(self._loop_wait_max, stop_waiting)
        waiter = self._loop.create_future()
        completed_data_ids = []
        while not self._stop:
            work, config_list, self._stop = await self._transport.request_work(runner_id, self._current_work(),
                                                                               completed_data_ids, self._max_work)
            config._update(config_list)
            for num, (scenario_id, scenario_data_id, journey_spec, args) in enumerate(work):
                id_data = {
                    'test': test_name,
                    'runner_id': runner_id,
                    'journey': journey_spec,
                    'context_id': next(context_id_gen),
                    'scenario_id': scenario_id,
                    'scenario_data_id': scenario_data_id
                }
                context = Context(self._msg_sender, config, id_data=id_data, should_stop_func=self.should_stop,
                                  debug=self._debug)
                self._inc_work(scenario_id)
                future = asyncio.ensure_future(
                    self._execute(context, scenario_id, scenario_data_id, journey_spec, args))
                future.add_done_callback(on_completion)
            completed_data_ids = await wait()
        while self._current_work():
            _, config_list, _ = await self._transport.request_work(runner_id, self._current_work(),
                                                                   completed_data_ids, 0)
            config._update(config_list)
            completed_data_ids = await wait()
        await self._transport.request_work(runner_id, self._current_work(), completed_data_ids, 0)
        await self._transport.bye(runner_id)

    async def _execute(self, context, scenario_id, scenario_data_id, journey_spec, args):
        logger.debug('Runner._execute starting scenario_id=%r scenario_data_id=%r journey_spec=%r args=%r',
                     scenario_id, scenario_data_id, journey_spec, args)
        async with context._exception_handler():
            async with context.transaction('__root__'):
                journey = spec_import(journey_spec)
                if args is None:
                    await journey(context)
                else:
                    await journey(context, *args)
        return scenario_id, scenario_data_id
