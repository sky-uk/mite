import asyncio
import functools
import logging
from itertools import count

from .context import Context
from .utils import spec_import

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=None)
def spec_import_cached(journey_spec):
    return spec_import(journey_spec)


async def _sleep_loop(delay):
    while True:
        await asyncio.sleep(delay)


class RunnerControllerTransportExample:  # pragma: no cover
    async def hello(self):
        """Returns:
        runner_id
        test_name
        config_list - k, v pairs
        """
        pass

    async def request_work(self, runner_id, current_work, completed_data_ids, max_work):
        """Takes:
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
        """Takes:
        runner_id
        """
        pass


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
        # This is a hack for the problems we get with the runner failing to
        # exit cleanly.  331 and 337 are both prime and a fortiori relatively
        # prime, which means it will take ~30 hours for them to ever
        # simultaneously be done at the same time (modulo rescheduling jitter).
        sleep1 = asyncio.create_task(_sleep_loop(331))
        sleep2 = asyncio.create_task(_sleep_loop(337))
        run = asyncio.create_task(self._run())
        done, pending = await asyncio.wait(
            (sleep1, sleep2, run), return_when=asyncio.FIRST_COMPLETED
        )
        if run not in done:
            logger.error(
                "Runner.run finished waiting on tasks, but the run loop wasn't complete!"
            )
        sleep1.cancel()
        sleep2.cancel()

    async def _run(self):
        context_id_gen = count(1)
        config = {}
        runner_id, test_name, config_list = await self._transport.hello()
        config.update(config_list)
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
            work, config_list, self._stop = await self._transport.request_work(
                runner_id, self._current_work(), completed_data_ids, self._max_work
            )
            config.update(config_list)
            for num, (scenario_id, scenario_data_id, journey_spec, args) in enumerate(
                work
            ):
                id_data = {
                    "test": test_name,
                    "runner_id": runner_id,
                    "journey": journey_spec,
                    "context_id": next(context_id_gen),
                    "scenario_id": scenario_id,
                    "scenario_data_id": scenario_data_id,
                }
                context = Context(
                    self._msg_sender,
                    config,
                    id_data=id_data,
                    should_stop_func=self.should_stop,
                    debug=self._debug,
                )
                self._inc_work(scenario_id)
                future = asyncio.create_task(
                    self._execute(
                        context, scenario_id, scenario_data_id, journey_spec, args
                    ),
                    name="{}_{}_{}".format(scenario_id, scenario_data_id, journey_spec),
                )
                future.add_done_callback(on_completion)
            completed_data_ids = await wait()
        while self._current_work():
            _, config_list, _ = await self._transport.request_work(
                runner_id, self._current_work(), completed_data_ids, 0
            )
            config.update(config_list)
            completed_data_ids = await wait()
        await self._transport.request_work(
            runner_id, self._current_work(), completed_data_ids, 0
        )
        await self._transport.bye(runner_id)

    async def _execute(self, context, scenario_id, scenario_data_id, journey_spec, args):
        logger.debug(
            "Runner._execute starting scenario_id=%r scenario_data_id=%r journey_spec=%r args=%r",
            scenario_id,
            scenario_data_id,
            journey_spec,
            args,
        )
        journey = spec_import_cached(journey_spec)
        try:
            async with context.transaction("__root__"):
                if args is None:
                    await journey(context)
                else:
                    await journey(context, *args)
        except Exception as e:
            if self._debug and not getattr(e, "handled", False):
                breakpoint()
                raise
        return scenario_id, scenario_data_id
